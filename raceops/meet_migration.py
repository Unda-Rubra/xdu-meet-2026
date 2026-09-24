"""One-time retirement of manual scoring; persistent formulas compute all scores in Base."""
from __future__ import annotations

import json
from pathlib import Path
import time

from .assets import ROOT
from .feishu import text
from .meet import PARTICIPATION_FIELD
from .meet_results import BATCH_FIELDS, CONTROL_FIELDS, SCORE_FIELDS, TRACK_FIELDS, Results, attempt_key


def delete_records(remote, table, ids):
    for start in range(0, len(ids), 500):
        remote.request('POST', f'/tables/{table}/records/batch_delete', {'records': ids[start:start + 500]})


def migrate(meet):
    remote, store, tables = meet.remote, meet.store, dict(meet.tables)
    user_fields = {f['field_name']: f for f in remote.fields(tables['users'])}
    if PARTICIPATION_FIELD not in user_fields:
        raise ValueError('缺少用户维护的最终参赛结果列：' + PARTICIPATION_FIELD)
    control_fields = {f['field_name']: f for f in remote.fields(tables['control'])}
    if '当前轮次' not in control_fields or control_fields['当前轮次']['type'] != 3:
        raise ValueError('先在比赛控制创建单选字段“当前轮次”，选项引用 SprintRacer积分倍率／轮次，再运行迁移')
    tables['raw'] = store.get('raw_table') or remote.ensure_table('比赛原始成绩', TRACK_FIELDS)
    tables['batch'] = store.get('result_table') or remote.ensure_table('轮次上传记录', BATCH_FIELDS)
    store.put('raw_table', tables['raw'])
    store.put('result_table', tables['batch'])
    if not store.get('round_schema_backup'):
        backup = {k: {'fields': remote.fields(v), 'records': remote.records(v)} for k, v in tables.items()}
        path = ROOT / 'volumes/control/service-only-score-backup.json'
        if path.exists():
            raise ValueError('Backup already exists without migration marker; inspect before retry')
        path.write_text(json.dumps(backup, ensure_ascii=False, indent=2))
        store.put('round_schema_backup', str(path))
    if not store.get('legacy_score_rows_removed'):
        # This explicitly authorized cutover removes old manual input and unbound rehearsal imports.
        for name in ('scores', 'raw', 'batch'):
            delete_records(remote, tables[name], [r['record_id'] for r in remote.records(tables[name])])
        scan = Results(meet).scan()
        if scan['errors']:
            raise ValueError('Archive quarantine failed: ' + str(scan['errors']))
        store.put('ignored_attempts', sorted({attempt_key(s) for s, _ in store.snapshots()}))
        store.put('legacy_score_rows_removed', True)
    for name, definitions in [('control', CONTROL_FIELDS), ('raw', TRACK_FIELDS), ('batch', BATCH_FIELDS), ('scores', SCORE_FIELDS),
                              ('multipliers', [{'field_name': '已发布批次', 'type': 1}])]:
        remote.ensure_fields(tables[name], definitions)
    remote.request('PATCH', '/tables/' + tables['batch'], {'name': '轮次上传记录'})
    formula_names = {
        'scores': ['名次', '排名百分位', '本轮基础得分', '本轮最终得分', '轮次倍率', '计分状态', '本轮排名'],
        'users': ['累计总得分', '最低轮得分', '最终总得分', '参与轮次', '参与轮次（计数）', '总排名', '最终排名', '当前轮得分', '当前轮排名'],
        'preparation': ['分组状态'],
        'groups': ['启用状态', '人数'],
    }
    for name, names in formula_names.items():
        actual = {f['field_name']: f for f in remote.fields(tables[name])}
        for field in names:
            if field not in actual:
                remote.request('POST', f'/tables/{tables[name]}/fields',
                               {'field_name': field, 'type': 20, 'property': {'formula_expression': '0'}})
    schemas = {k: {f['field_name']: f for f in remote.fields(v)} for k, v in tables.items()}
    def table(name):
        return f'bitable::$table[{tables[name]}]'
    def ref(name, field):
        return table(name) + '.$field[' + schemas[name][field]['field_id'] + ']'
    def col(name, field):
        return '.$column[' + schemas[name][field]['field_id'] + ']'
    def cv(name, field):
        return 'CurrentValue' + col(name, field)
    def formula(name, field, expression):
        current = schemas[name][field]
        if current['type'] == 20 and current.get('property', {}).get('formula_expression') == expression:
            return
        remote.update_field(tables[name], current, formula=expression)
        time.sleep(0.3)
    s = lambda field: ref('scores', field)
    u = lambda field: ref('users', field)
    peer = lambda field: cv('scores', field)
    selected = table('multipliers') + f'.FILTER({cv("multipliers", "轮次")}={s("轮次")})'
    published = selected + col('multipliers', '已发布批次') + '.FIRST()'
    excluded = table('users') + f'.COUNTIF(AND(NOT({cv("users", PARTICIPATION_FIELD)}),{s("关联用户")}.CONTAIN({cv("users", "用户ID")})))>0'
    formula('scores', '计分状态', f'IFS(ISBLANK({s("导入键")}),"非服务记录",{excluded},"不参与比赛",'
            f'OR({s("上传批次")}!={published},ISBLANK({s("上传批次")})),"未发布",'
            f'NOT(ISBLANK({s("数据原因")})),"数据异常",{s("结果状态")}="FINISHED","有效",'
            f'OR({s("结果状态")}="DNS",{s("结果状态")}="DNF"),"有效",TRUE(),"数据异常")')
    same = f'AND({peer("上传批次")}={s("上传批次")},{peer("组别")}={s("组别")},{peer("结果状态")}="FINISHED",{peer("原生总分")}>{s("原生总分")})'
    formula('scores', '名次', f'IF({s("结果状态")}="FINISHED",1+{table("scores")}.COUNTIF({same}),"")')
    formula('scores', '排名百分位', f'IF({s("结果状态")}!="FINISHED",0,IF({s("参赛人数快照")}<=1,1,({s("参赛人数快照")}-{s("名次")})/({s("参赛人数快照")}-1)))')
    formula('scores', '本轮基础得分', f'IF({s("计分状态")}!="有效","",IF({s("结果状态")}!="FINISHED",0,10+90*POWER({s("排名百分位")},1.5)))')
    formula('scores', '轮次倍率', selected + col('multipliers', '积分倍率') + '.FIRST()')
    formula('scores', '本轮最终得分', f'IF(OR({s("计分状态")}!="有效",NOT(ISNUMBER({s("轮次倍率")})),{s("轮次倍率")}<=0),"",{s("本轮基础得分")}*{s("轮次倍率")})')
    formula('scores', '本轮排名', f'IF({s("计分状态")}!="有效","",1+{table("scores")}.COUNTIF(AND({peer("轮次")}={s("轮次")},{peer("计分状态")}="有效",{peer("本轮最终得分")}>{s("本轮最终得分")})))')
    owned = f'AND({peer("关联用户")}.CONTAIN({u("用户ID")}),{peer("计分状态")}="有效")'
    own_rows = table('scores') + '.FILTER(' + owned + ')'
    formula('users', '累计总得分', own_rows + col('scores', '本轮最终得分') + '.SUM()')
    formula('users', '最低轮得分', own_rows + col('scores', '本轮最终得分') + '.MIN()')
    formula('users', '参与轮次', own_rows + col('scores', '轮次') + '.UNIQUE()')
    formula('users', '参与轮次（计数）', own_rows + col('scores', '轮次') + '.UNIQUE().COUNTA()')
    formula('users', '最终总得分', f'IF(NOT({u(PARTICIPATION_FIELD)}),"",{u("累计总得分")}-IF(ISBLANK({u("最低轮得分")}),0,{u("最低轮得分")}))')
    formula('users', '总排名', f'IF(OR(NOT({u(PARTICIPATION_FIELD)}),{u("参与轮次（计数）")}=0),"",1+{table("users")}.COUNTIF(AND({cv("users", PARTICIPATION_FIELD)},{cv("users", "累计总得分")}>{u("累计总得分")})))')
    formula('users', '最终排名', f'IF(OR(NOT({u(PARTICIPATION_FIELD)}),{u("参与轮次（计数）")}=0),"",1+{table("users")}.COUNTIF(AND({cv("users", PARTICIPATION_FIELD)},{cv("users", "参与轮次（计数）")}>0,{cv("users", "最终总得分")}>{u("最终总得分")})))')
    current_round = table('control') + col('control', '当前轮次') + '.FIRST()'
    current_score = own_rows + f'.FILTER({peer("轮次")}=({current_round}))' + col('scores', '本轮最终得分')
    formula('users', '当前轮得分', f'IF({current_score}.COUNTA()=0,"",{current_score}.SUM())')
    formula('users', '当前轮排名', f'IF(ISBLANK({u("当前轮得分")}),"",1+{table("users")}.COUNTIF(AND({cv("users", PARTICIPATION_FIELD)},NOT(ISBLANK({cv("users", "当前轮得分")})),{cv("users", "当前轮得分")}>{u("当前轮得分")})))')
    formula('groups', '启用状态', f'IF(AND({ref("groups", "组别")}="C",{table("control")}{col("control", "本批组数")}.SUM()!=3),"未启用","启用")')
    formula('groups', '人数', f'IF({ref("groups", "启用状态")}="未启用",0,{table("users")}.COUNTIF(AND({cv("users", PARTICIPATION_FIELD)},{ref("groups", "成员")}.CONTAIN({cv("users", "用户ID")}))))')
    # Existing validation wording/round references are user-maintained: replace only the retired predicate.
    validation = schemas['users']['分组校验']['property']['formula_expression']
    formula('users', '分组校验', validation.replace(u('不参与比赛'), f'NOT({u(PARTICIPATION_FIELD)})'))
    complete = ','.join(f'{ref("preparation", f"第{n}轮组别")}.COUNTA()=1' for n in range(1, 8))
    linked_validation = ref('preparation', '关联用户') + col('users', '分组校验') + '.ARRAYJOIN("")'
    # The owner's 参赛状态 lookup is display-only; evaluate the final source directly.
    eligible_preparation = table('users') + f'.COUNTIF(AND({cv("users", PARTICIPATION_FIELD)},{ref("preparation", "关联用户")}.CONTAIN({cv("users", "用户ID")})))>0'
    formula('preparation', '分组状态', f'IFS({ref("preparation", "关联校验")}!="正常","关联异常",NOT({eligible_preparation}),"不参赛",AND({complete},{linked_validation}=""),"七轮已分配",TRUE(),"未分组或需检查")')
    # Only audited, explicitly obsolete columns are retired. Never delete user columns via an allowlist.
    retire = {'preparation': {'纳入首批', '已保存', '用户序号'}, 'scores': {'参赛人数'}}
    for name, names in retire.items():
        for field in remote.fields(tables[name]):
            if field['field_name'] in names:
                remote.request('DELETE', f"/tables/{tables[name]}/fields/{field['field_id']}")
                time.sleep(0.8)
    control = meet.control()
    if control['fields'].get('当前轮次') is None:
        meet.update('control', [{'record_id': control['record_id'], 'fields': {'操作': '比赛轮次控制', '当前轮次': '第1轮', '上传状态': '等待新的完整比赛结果'}}])
    store.put('round_upload_ready', True)
    from .meet_field_notes import apply_field_notes
    apply_field_notes(meet)
