"""Only an explicit token upload may read or write Feishu; capture stays offline."""
from pathlib import Path
import json
from .assets import digest
from .feishu import text, equivalent
from .model import canonical_hash
from .qq_identity import validate_qq

SCORE_FIELDS = [{'field_name': n, 'type': 1} for n in
                ['导入键', '上传批次', 'QQ号', '游戏名', '组别', '结果状态', '数据原因']]
SCORE_FIELDS += [{'field_name': n, 'type': 2} for n in ['原生总分', '参赛人数快照']]
BATCH_FIELDS = [{'field_name': n, 'type': 1} for n in ['导入键', '成绩token', '数据状态', '来源归档', '原因']]
BATCH_FIELDS += [{'field_name': n, 'type': 2} for n in ['轮次', '人数', '组数']]


def read_archive(path):
    manifest = json.loads((path / 'manifest.json').read_text())
    if not manifest.get('complete') or not manifest.get('coherent_attempt'):
        raise ValueError('Incomplete or incoherent result archive')
    for name, checksum in manifest['files'].items():
        if Path(name).name != name or (path / name).is_symlink() or digest(path / name) != checksum:
            raise ValueError('Archive checksum mismatch')
    snapshots = []
    for receipt in manifest['servers'].values():
        filename = receipt['snapshot_file']
        if filename not in manifest['files']:
            raise ValueError('Snapshot is not covered by manifest')
        s = json.loads((path / filename).read_text())['snapshot']
        if canonical_hash(s) != receipt['snapshot_hash'] or s.get('state') != 'GP_FINISHED' or not s.get('frozen'):
            raise ValueError('Result is not a verified post-ceremony snapshot')
        snapshots.append(s)
    active = set(snapshots[0]['active_groups'])
    if {s['group'] for s in snapshots} != active or len(active) != len(snapshots):
        raise ValueError('Missing or duplicate race group')
    if len({(s['event_id'], s['attempt_id'], s['settings_hash']) for s in snapshots}) != 1:
        raise ValueError('Race snapshots disagree')
    return snapshots


class Results:
    def __init__(self, meet):
        self.meet, self.store, self.remote = meet, meet.store, meet.remote

    def upload(self, token):
        receipt = self.store.receipt(token)
        path = Path(receipt['archive'])
        if digest(path / 'manifest.json') != receipt['digest']:
            raise ValueError('Token archive changed')
        snapshots = read_archive(path)
        previous = self.store.upload(token)
        if previous:
            if previous['status'] == 'done':
                return {'unchanged': True, 'round': previous['round'], 'token': token}
            return self._publish(previous['plan'])
        selected = text(self.meet.control()['fields'].get('当前轮次'))
        if selected not in {f'第{n}轮' for n in range(1, 8)}:
            raise ValueError('Select a valid Feishu round before uploading')
        number = int(selected[1:-1])
        users = self.meet.users_by_qq({validate_qq(p['qq']) for s in snapshots for p in s['roster']})
        seen, scores, nicknames, issues = set(), [], [], []
        for s in snapshots:
            roster = s['roster']
            if not roster or len(roster) > 17:
                raise ValueError('Invalid human roster size')
            for p in roster:
                qq = validate_qq(p['qq'])
                if qq in seen or p.get('admin'):
                    raise ValueError('Duplicate QQ or administrator in result roster')
                seen.add(qq)
                if qq not in users:
                    raise ValueError('Result contains an unrecognized signup QQ; correct signup data before upload')
                result = s['results'].get(p['uuid'])
                if not result or type(result.get('total')) is not int:
                    raise ValueError('Missing native GP score observation')
                reason = '' if result.get('status') == 'FINISHED' else '本次比赛有缺席、断线或未完成记录'
                if reason:
                    issues.append(reason)
                scores.append({'导入键': token + '/' + qq, '上传批次': token, 'QQ号': qq,
                               '游戏名': p['name'], '组别': s['group'], '轮次': selected,
                               '关联用户': [users[qq]['record_id']], '原生总分': result['total'],
                               '参赛人数快照': len(roster), '结果状态': result['status'], '数据原因': reason})
                nicknames.append({'record_id': users[qq]['record_id'], 'fields': {'游戏昵称': p['name']}})
        plan = {'token': token, 'round': number, 'scores': scores, 'nicknames': nicknames,
                'batch': {'导入键': token, '成绩token': token, '轮次': number, '人数': len(scores),
                          '组数': len(snapshots), '数据状态': '数据异常' if issues else '完整',
                          '原因': '；'.join(sorted(set(issues))), '来源归档': path.name}}
        # Durable binding precedes every cloud write, including nickname updates.
        self.store.bind_upload(token, number, plan)
        return self._publish(plan)

    def _publish(self, plan):
        token, number = plan['token'], plan['round']
        rounds = [r for r in self.meet.read('multipliers', ['轮次', '已发布批次']) if text(r['fields'].get('轮次')) == f'第{number}轮']
        if len(rounds) != 1:
            raise ValueError('Expected exactly one target round')
        self.remote.upsert(self.meet.tables['scores'], plan['scores'], self.store)
        actual = {text(r['fields'].get('导入键')): r['fields'] for r in self.meet.read('scores')
                  if text(r['fields'].get('上传批次')) == token}
        if set(actual) != {r['导入键'] for r in plan['scores']} or any(
                not equivalent(actual[r['导入键']].get(k), v) for r in plan['scores'] for k, v in r.items()):
            raise ValueError('Score readback differs; published batch unchanged')
        self.remote.upsert(self.meet.tables['batch'], [plan['batch']], self.store)
        self.meet.update('users', plan['nicknames'])
        if plan['batch']['数据状态'] == '完整':
            self.meet.update('multipliers', [{'record_id': rounds[0]['record_id'], 'fields': {'已发布批次': token}}])
        self.meet.update('control', [{'record_id': self.meet.control()['record_id'], 'fields': {
            '上传状态': '手动上传完成', '最近上传轮次': number, '最近上传尝试': token,
            '最近上传状态': plan['batch']['数据状态']}}])
        self.store.mark_upload(token, 'done')
        return {'token': token, 'round': number, 'players': len(plan['scores']), 'status': plan['batch']['数据状态']}
