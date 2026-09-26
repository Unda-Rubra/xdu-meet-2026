"""Manual, backed-up cutover to QQ-linked post-race publication. No schedule tables."""
import json
from datetime import datetime, timezone
from .assets import ROOT
from .meet_results import SCORE_FIELDS, BATCH_FIELDS
from .feishu import FeishuError


def delete_records(remote, table, ids):
    for offset in range(0, len(ids), 200):
        remote.request('POST', f'/tables/{table}/records/batch_delete', {'records': ids[offset:offset + 200]})


def migrate(meet):
    remote, tables = meet.remote, meet.tables
    if not meet.store.get('manual_schema_backup'):
        snapshot = {t['table_id']: {'name': t['name'], 'fields': remote.fields(t['table_id']),
                                    'records': remote.records(t['table_id'])} for t in remote.tables()}
        path = ROOT / ('volumes/control/manual-cutover-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '.json')
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
        meet.store.put('manual_schema_backup', str(path))
    remote.ensure_fields(tables['users'], [{'field_name': '游戏昵称', 'type': 1}])
    remote.ensure_fields(tables['scores'], SCORE_FIELDS)
    remote.ensure_fields(tables['batch'], BATCH_FIELDS)
    formulas = {
        'users': ['累计总得分', '最低轮得分', '最终总得分', '参与轮次', '参与轮次（计数）', '总排名', '最终排名', '当前轮得分', '当前轮排名', '本轮参赛', '本轮组别'],
        'scores': ['名次', '排名百分位', '本轮基础得分', '本轮最终得分', '轮次倍率', '计分状态', '本轮排名'],
    }
    for name, fields in formulas.items():
        remote.ensure_fields(tables[name], [{'field_name': f, 'type': 20, 'property': {'formula_expression': '0'}} for f in fields])
    schema = {name: {f['field_name']: f for f in remote.fields(tid)} for name, tid in tables.items()}
    native_updates = []
    def table(name):
        return f'bitable::$table[{tables[name]}]'
    def ref(name, field):
        return table(name) + '.$field[' + schema[name][field]['field_id'] + ']'
    def col(name, field):
        return '.$column[' + schema[name][field]['field_id'] + ']'
    def cv(name, field):
        return 'CurrentValue' + col(name, field)
    def formula(name, field, expression):
        old = schema[name][field]
        if old.get('property', {}).get('formula_expression') != expression:
            try:
                remote.update_field(tables[name], old, formula=expression)
            except FeishuError as error:
                if not str(error).startswith('OpenAPI cannot preserve this formula display format;'):
                    raise
                native_updates.append({'table': tables[name], 'field': old['field_id'],
                                       'name': field, 'expression': expression})
    s = lambda field: ref('scores', field)
    u = lambda field: ref('users', field)
    peer = lambda field: cv('scores', field)
    round_rows = table('multipliers') + f'.FILTER({cv("multipliers", "轮次")}={s("轮次")})'
    published = round_rows + col('multipliers', '已发布批次') + '.FIRST()'
    formula('scores', '计分状态', f'IFS(ISBLANK({s("导入键")}),"非服务记录",OR(ISBLANK({published}),{s("上传批次")}!={published}),"未发布",NOT(ISBLANK({s("数据原因")})),"数据异常",{s("结果状态")}="FINISHED","有效",TRUE(),"数据异常")')
    formula('scores', '名次', f'IF({s("结果状态")}!="FINISHED","",1+{table("scores")}.COUNTIF(AND({peer("上传批次")}={s("上传批次")},{peer("组别")}={s("组别")},{peer("结果状态")}="FINISHED",{peer("原生总分")}>{s("原生总分")})))')
    formula('scores', '排名百分位', f'IF({s("结果状态")}!="FINISHED",0,IF({s("参赛人数快照")}<=1,1,({s("参赛人数快照")}-{s("名次")})/({s("参赛人数快照")}-1)))')
    formula('scores', '本轮基础得分', f'IF({s("计分状态")}!="有效","",10+90*POWER({s("排名百分位")},1.5))')
    formula('scores', '轮次倍率', round_rows + col('multipliers', '积分倍率') + '.FIRST()')
    formula('scores', '本轮最终得分', f'IF({s("计分状态")}!="有效","",{s("本轮基础得分")}*{s("轮次倍率")})')
    formula('scores', '本轮排名', f'IF({s("计分状态")}!="有效","",1+{table("scores")}.COUNTIF(AND({peer("轮次")}={s("轮次")},{peer("计分状态")}="有效",{peer("本轮最终得分")}>{s("本轮最终得分")})))')
    own = table('scores') + f'.FILTER(AND({peer("QQ号")}=({u("QQ号")}&""),{peer("计分状态")}="有效"))'
    formula('users', '累计总得分', own + col('scores', '本轮最终得分') + '.SUM()')
    formula('users', '最低轮得分', own + col('scores', '本轮最终得分') + '.MIN()')
    formula('users', '参与轮次', own + col('scores', '轮次') + '.UNIQUE()')
    formula('users', '参与轮次（计数）', own + col('scores', '轮次') + '.UNIQUE().COUNTA()')
    formula('users', '最终总得分', f'IF({u("参与轮次（计数）")}=0,"",IF({u("参与轮次（计数）")}<5,{u("累计总得分")},{u("累计总得分")}-{u("最低轮得分")}))')
    for rank, score in [('总排名', '最终总得分'), ('最终排名', '最终总得分')]:
        formula('users', rank, f'IF({u("参与轮次（计数）")}=0,"",1+{table("users")}.COUNTIF(AND({cv("users", "参与轮次（计数）")}>0,{cv("users", score)}>{u(score)})))')
    current = table('control') + col('control', '当前轮次') + '.FIRST()'
    own_current = own + f'.FILTER({peer("轮次")}={current})' + col('scores', '本轮最终得分')
    formula('users', '当前轮得分', f'IF({own_current}.COUNTA()=0,"",{own_current}.SUM())')
    formula('users', '当前轮排名', f'IF(ISBLANK({u("当前轮得分")}),"",1+{table("users")}.COUNTIF(AND(NOT(ISBLANK({cv("users", "当前轮得分")})),{cv("users", "当前轮得分")}>{u("当前轮得分")})))')
    current_batch = table('multipliers') + f'.FILTER({cv("multipliers", "轮次")}={current})' + col('multipliers', '已发布批次') + '.FIRST()'
    formula('users', '本轮参赛', f'IF(ISBLANK({current_batch}),"未上传",IF({own_current}.COUNTA()>0,"已参赛","未参赛"))')
    formula('users', '本轮组别', own + f'.FILTER({peer("轮次")}={current})' + col('scores', '组别') + '.FIRST()')
    if native_updates:
        path = ROOT / 'volumes/control/manual-ui-formulas.json'
        path.write_text(json.dumps(native_updates, ensure_ascii=False, indent=2))
        raise ValueError('Native Base editor updates required before removing dependencies: ' + str(path))
    retired = {
        'users': {'Minecraft游戏用户名', '能够参与小游戏（最终结果）', '不参与比赛', '分组校验', '分组准备校验', '分组准备记录', '所属分组', *[f'第{i}轮组别' for i in range(1, 8)]},
        'control': {'本批组数', '各组进度'}, 'multipliers': {'A人数', 'B人数', 'C人数'},
        'scores': {'UUID'}, 'batch': {'赛事', '尝试', '原游戏轮次', '逐图记录数', '完成时间'},
    }
    for name, fields in retired.items():
        for f in remote.fields(tables[name]):
            if f['field_name'] in fields:
                remote.request('DELETE', f'/tables/{tables[name]}/fields/{f["field_id"]}')
    for t in remote.tables():
        if t['name'] in ('SprintRacer分组', '分组准备名单', '比赛原始成绩'):
            remote.request('DELETE', '/tables/' + t['table_id'])
    meet.store.put('manual_schema_ready', True)
    return {'mode': 'manual-token-upload', 'backup': meet.store.get('manual_schema_backup')}
