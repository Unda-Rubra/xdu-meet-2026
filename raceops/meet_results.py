"""Forward completed attempts once, bound to the Feishu round at first upload.

No event points or ranks are calculated here: Feishu formulas own scoring.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from .assets import ROOT, digest
from .cli import exclusive
from .event import load_event, pinned_groups, race_services
from .exporter import export
from .feishu import equivalent, text
from .identity import offline_uuid
from .meet import PARTICIPATION_FIELD, can_participate
from .model import canonical_hash
from .transport import Backend


def fields(text_names, number_names=()):
    return ([{'field_name': name, 'type': 1} for name in text_names]
            + [{'field_name': name, 'type': 2} for name in number_names])


TRACK_FIELDS = fields(['导入键', '上传批次', '赛事', '尝试', '组别', 'UUID', '游戏名', '状态', '原始JSON', '来源归档'],
                      ['轮次', '地图序号', '原始名次', '地图原生分', '累计原生分'])
BATCH_FIELDS = fields(['导入键', '赛事', '尝试', '数据状态', '原因', '来源归档', '完成时间'],
                      ['轮次', '原游戏轮次', '组数', '人数', '逐图记录数'])
SCORE_FIELDS = fields(['导入键', '上传批次', 'UUID', '游戏名', '组别', '结果状态', '数据原因'],
                      ['原生总分', '参赛人数快照'])
SCORE_FIELDS += [{'field_name': '轮次', 'type': 3, 'property': {'options': [{'name': f'第{i}轮'} for i in range(1, 8)]}}]
CONTROL_FIELDS = fields(['操作', '上传状态', '最近上传尝试', '最近上传状态', '各组进度'], ['最近上传轮次', '本批组数'])
CONTROL_FIELDS += [{'field_name': '当前轮次', 'type': 3}]
ROUND_NUMBERS = {f'第{i}轮': i for i in range(1, 8)}


def selected_round(value):
    number = ROUND_NUMBERS.get(text(value))
    if number is None:
        raise ValueError('请在比赛控制的当前轮次下拉框中选择第1轮至第7轮')
    return number


def attempt_key(snapshot):
    return f"{snapshot['event_id']}/{snapshot['attempt_id']}"


def snapshot_key(snapshot):
    return attempt_key(snapshot) + '/' + snapshot['group']


def complete_attempt(groups):
    if not groups:
        return False
    active = next(iter(groups.values())).get('active_groups', [])
    return (sorted(active) in (['A', 'B'], ['A', 'B', 'C']) and set(groups) == set(active)
            and all(s.get('state') == 'GP_FINISHED' and s.get('frozen') for s in groups.values()))


def result_facts(snapshot):
    """Validate evidence; tied totals are legitimate, disconnected is not inferred DNF."""
    errors, facts = [], {}
    roster = snapshot.get('roster', [])
    ids = [p.get('uuid') for p in roster]
    if not 1 <= len(ids) <= 17 or None in ids or len(set(ids)) != len(ids):
        errors.append('名册缺失或重复')
    if snapshot.get('ai_count') != 0 or snapshot.get('ai_master_count', 0) != 0:
        errors.append('存在AI或AI状态未知')
    if snapshot.get('identity_mode') != 'offline_trusted_private':
        errors.append('身份模式不匹配')
    for player in roster:
        try:
            if offline_uuid(player.get('name')) != player.get('uuid'):
                errors.append('UUID与游戏名不一致')
        except ValueError:
            errors.append('游戏名无效')
    tracks = snapshot.get('tracks', [])
    if len(tracks) != 6 or [t.get('track_index') for t in tracks] != list(range(1, 7)):
        errors.append('缺少完整六图')
    histories = defaultdict(list)
    for track in tracks:
        if not all(track.get(k) for k in ('started', 'closed', 'settled', 'commit_phase_reached')):
            errors.append('地图未完整结算')
        players = track.get('players', [])
        if Counter(p.get('uuid') for p in players) != Counter(ids):
            errors.append('地图名册缺失或重复')
        finishers = [p for p in players if p.get('status') == 'FINISHED']
        positions = [p.get('finish_pos_raw') for p in finishers]
        if any(type(p) is not int or not 1 <= p <= len(ids) for p in positions) or len(set(positions)) != len(positions):
            errors.append('逐图名次无效或冲突')
        for p in players:
            histories[p.get('uuid')].append(p)
    for player in roster:
        uid = player['uuid']
        history = histories[uid]
        statuses = {p.get('status') for p in history}
        reason = []
        if not statuses <= {'FINISHED', 'DNS', 'DNF'}:
            reason.append('存在断线或未知结果，不推断DNF')
        finished = all(p.get('status') == 'FINISHED' for p in history) and len(history) == 6
        if finished and any(not p.get('started') or not p.get('finished') for p in history):
            reason.append('完成标记不一致')
        if any(not p.get('native_commit_observed') for p in history):
            reason.append('缺少原生结算观测')
        if any(type(p.get('award')) is not int or p['award'] < 0 for p in history):
            reason.append('原生获分无效')
        total = history[-1].get('native_total') if history else None
        if type(total) is not int or total < 0 or (not reason and total != sum(p['award'] for p in history)):
            reason.append('累计总分与六图获分不一致')
        if finished:
            status = 'FINISHED'
        elif len(history) != 6:
            status = 'INCOMPLETE'
        elif 'DISCONNECTED' in statuses:
            status = 'DISCONNECTED'
        elif 'UNFINISHED' in statuses:
            status = 'UNFINISHED'
        elif not statuses <= {'FINISHED', 'DNS', 'DNF'}:
            status = 'UNKNOWN'
        else:
            status = 'DNS' if statuses == {'DNS'} else 'DNF'
        facts[uid] = {'total': total if type(total) is int else None,
                      'status': status,
                      'errors': reason}
        errors.extend(reason)
    return facts, sorted(set(errors))


def read_archive(path):
    manifest_path = path / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('files'), dict):
        raise ValueError('Unsupported archive manifest: ' + path.name)
    for name, checksum in manifest['files'].items():
        file = path / name
        if Path(name).name != name or file.is_symlink() or digest(file) != checksum:
            raise ValueError('Archive checksum mismatch: ' + path.name)
    result = []
    for receipt in manifest.get('servers', {}).values():
        name = receipt.get('snapshot_file')
        if name not in manifest['files'] or Path(name).name != name:
            raise ValueError('Snapshot is not covered by archive manifest')
        snapshot = json.loads((path / name).read_text())['snapshot']
        if canonical_hash(snapshot) != receipt.get('snapshot_hash'):
            raise ValueError('Snapshot hash mismatch')
        for key in ('event_id', 'grand_prix_round', 'attempt_id', 'boot_id', 'revision'):
            if key in receipt and snapshot.get(key) != receipt[key]:
                raise ValueError('Snapshot receipt identity mismatch: ' + key)
        if snapshot.get('tracks'):
            result.append(snapshot)
    return result, digest(manifest_path)


class Results:
    def __init__(self, meet):
        self.meet, self.store, self.remote = meet, meet.store, meet.remote

    def control_update(self, fields):
        row = self.meet.control()
        changed = {k: v for k, v in fields.items() if text(row['fields'].get(k)) != text(v)}
        if changed:
            self.meet.update('control', [{'record_id': row['record_id'], 'fields': changed}])

    def capture(self):
        """Export only frozen, complete attempts; persistent backend history survives missed polls."""
        by_attempt = defaultdict(dict)
        with exclusive():
            progress = []
            racing = False
            for service in race_services(pinned_groups()):
                backend = Backend(service)
                current = backend.read()
                progress.append(service + ': ' + current['state'])
                racing = racing or current['state'] in ('RUNNING', 'BETWEEN_TRACKS')
                history = backend.read('attempts', 'xdu_race:results')
                for snapshot in list(history.values()) + [current]:
                    if snapshot.get('tracks') and snapshot.get('frozen') and snapshot.get('state') == 'GP_FINISHED':
                        by_attempt[attempt_key(snapshot)][snapshot['group']] = snapshot
            ignored = set(self.store.get('ignored_attempts', []))
            captured = set(self.store.get('captured_attempts', []))
            for key, groups in sorted(by_attempt.items()):
                if key in ignored or key in captured or not complete_attempt(groups):
                    continue
                first = next(iter(groups.values()))
                _, manifest = export([Backend(s) for s in race_services(first['active_groups'])], attempt_id=first['attempt_id'])
                if not manifest['complete'] or not manifest['coherent_attempt']:
                    raise ValueError('Incomplete terminal archive; no upload attempted')
                captured.add(key)
                self.store.put('captured_attempts', sorted(captured))
        fields = {'各组进度': '；'.join(progress)}
        if racing:
            fields['上传状态'] = '比赛进行中；等待全部启用组完赛'
        self.control_update(fields)

    def scan(self):
        errors, imported = [], 0
        for path in sorted((ROOT / 'exports').glob('*/manifest.json')):
            if path.parent.name.startswith('.'):
                continue
            try:
                checksum = digest(path)
                previous = self.store.db.execute('SELECT digest FROM archives WHERE path=?', (str(path.parent),)).fetchone()
                if previous:
                    if previous[0] != checksum:
                        raise ValueError('Immutable archive changed')
                    continue
                snapshots, checksum = read_archive(path.parent)
                for snapshot in snapshots:
                    if snapshot.get('event_id') != load_event()['event_id']:
                        raise ValueError('Another event archive requires a separate configuration')
                    self.store.remember_snapshot(snapshot_key(snapshot), snapshot, canonical_hash(snapshot), path.parent)
                with self.store.db:
                    self.store.db.execute('INSERT INTO archives VALUES (?,?)', (str(path.parent), checksum))
                imported += 1
            except (OSError, ValueError, KeyError, TypeError) as error:
                errors.append({'archive': path.parent.name, 'error': str(error)})
        return {'new_archives': imported, 'errors': errors}

    def _plan(self, key, groups, archives, round_number):
        first = next(iter(groups.values()))
        coherence = {(s.get('preset_hash'), s.get('roster_hash'), s.get('template_hash'), s.get('settings_hash'),
                      s.get('grand_prix_round'), tuple(s.get('active_groups', []))) for s in groups.values()}
        reasons = [] if len(coherence) == 1 else ['各组预设、名册或尝试配置不一致']
        users, duplicate = {}, set()
        for row in self.meet.read('users', ['Minecraft游戏用户名', PARTICIPATION_FIELD]):
            try:
                uid = offline_uuid(text(row['fields'].get('Minecraft游戏用户名')))
            except ValueError:
                continue
            if uid in users:
                duplicate.add(uid)
            users[uid] = row
        raw, scores, seen = [], [], set()
        for group, snapshot in sorted(groups.items()):
            facts, issues = result_facts(snapshot)
            reasons.extend(issues)
            frame = {k: v for k, v in snapshot.items() if k != 'tracks'}
            for track in snapshot['tracks']:
                for index, player in enumerate(track['players']):
                    raw.append({'导入键': f"{key}/{group}/{track['track_index']}/{index}", '上传批次': key,
                                '赛事': first['event_id'], '尝试': first['attempt_id'], '轮次': round_number,
                                '组别': group, 'UUID': player.get('uuid', ''), '游戏名': player.get('name_at_start', ''),
                                '地图序号': track['track_index'], '状态': player.get('status', 'UNKNOWN'),
                                '原始名次': player.get('finish_pos_raw'), '地图原生分': player.get('award'),
                                '累计原生分': player.get('native_total'), '来源归档': Path(archives[group]).name,
                                '原始JSON': json.dumps({'snapshot': frame, 'track': {k: v for k, v in track.items() if k != 'players'}, 'player': player}, ensure_ascii=False)})
            for player in snapshot['roster']:
                uid = player['uuid']
                user, fact = users.get(uid), facts[uid]
                errors = list(fact['errors'])
                if uid in seen:
                    errors.append('同一用户出现在多个组')
                seen.add(uid)
                if not user or uid in duplicate:
                    errors.append('飞书游戏身份未绑定或重复')
                elif not can_participate(user['fields']):
                    errors.append('用户的小游戏参与最终结果为否')
                reasons.extend(errors)
                scores.append({'导入键': key + '/' + group + '/' + uid, '上传批次': key, 'UUID': uid,
                               '游戏名': player['name'], '轮次': f'第{round_number}轮', '组别': group,
                               '关联用户': [user['record_id']] if user and uid not in duplicate else [],
                               '原生总分': fact['total'], '参赛人数快照': len(snapshot['roster']),
                               '结果状态': fact['status'], '数据原因': '；'.join(errors)})
        batch = {'导入键': key, '赛事': first['event_id'], '尝试': first['attempt_id'], '轮次': round_number,
                 '原游戏轮次': first['grand_prix_round'], '组数': len(groups), '人数': len(scores),
                 '逐图记录数': len(raw), '数据状态': '数据异常' if reasons else '完整',
                 '原因': '；'.join(sorted(set(reasons))), '来源归档': '；'.join(sorted(set(Path(a).name for a in archives.values()))),
                 '完成时间': datetime.now(timezone.utc).isoformat()}
        return {'key': key, 'round': round_number, 'raw': raw, 'scores': scores, 'batch': batch}

    def _publish(self, plan):
        key, number = plan['key'], plan['round']
        rounds = [r for r in self.meet.read('multipliers', ['轮次', '已发布批次']) if text(r['fields'].get('轮次')) == f'第{number}轮']
        if len(rounds) != 1:
            raise ValueError('Exactly one round/multiplier row required for target round')
        self.control_update({'上传状态': f'正在上传第{number}轮：{key}'})
        report = {'raw': self.remote.upsert(self.store.get('raw_table'), plan['raw'], self.store),
                  'scores': self.remote.upsert(self.meet.tables['scores'], plan['scores'], self.store)}
        # Commit pointer comes last, after all expected rows are present; old ranking stays visible on failure.
        for table, expected in [(self.store.get('raw_table'), plan['raw']), (self.meet.tables['scores'], plan['scores'])]:
            columns = list(expected[0]) if expected else ['导入键', '上传批次']
            actual = [r for r in self.remote.records(table, columns) if text(r['fields'].get('上传批次')) == key]
            if sorted(text(r['fields'].get('导入键')) for r in actual) != sorted(r['导入键'] for r in expected):
                raise ValueError('Uploaded record set mismatch; commit pointer unchanged')
            by_key = {text(r['fields'].get('导入键')): r['fields'] for r in actual}
            if any(not equivalent(by_key[r['导入键']].get(k), v) for r in expected for k, v in r.items()):
                raise ValueError('Uploaded record content mismatch; commit pointer unchanged')
        self.remote.upsert(self.store.get('result_table'), [plan['batch']], self.store)
        if plan['batch']['数据状态'] == '完整':
            self.meet.update('multipliers', [{'record_id': rounds[0]['record_id'], 'fields': {'已发布批次': key}}])
        self.control_update({'最近上传轮次': number, '最近上传尝试': key,
                             '最近上传状态': plan['batch']['数据状态'], '上传状态': '上传完成；确认后手动修改当前轮次'})
        self.store.mark_upload(key, 'done')
        return report

    def sync(self, capture=True):
        if not self.store.get('round_upload_ready'):
            raise ValueError('Round upload migration is not complete')
        report = {'published': [], 'pending': [], 'errors': []}
        if capture:
            try:
                self.capture()
            except (OSError, ValueError, RuntimeError) as error:
                report['capture_error'] = str(error)
        scan = self.scan()
        report.update(scan)
        by_attempt, locations = defaultdict(dict), defaultdict(dict)
        for snapshot, archive in self.store.snapshots():
            key = attempt_key(snapshot)
            by_attempt[key][snapshot['group']] = snapshot
            locations[key][snapshot['group']] = archive
        ignored = set(self.store.get('ignored_attempts', []))
        pending_uploads = self.store.uploads('pending')
        for upload in pending_uploads:
            self._publish(upload['plan'])
            report['published'].append({'attempt': upload['key'], 'round': upload['round']})
        # Multiple unseen terminal attempts cannot all be assigned to today's round accidentally.
        unseen = [key for key, groups in by_attempt.items() if key not in ignored
                  and not self.store.upload(key) and complete_attempt(groups)]
        if len(unseen) > 1:
            raise ValueError('Multiple unseen completed attempts: explicitly bind each with upload-attempt --attempt and --round')
        for key in unseen:
            control = self.meet.control()
            number = selected_round(control['fields'].get('当前轮次'))
            plan = self._plan(key, by_attempt[key], locations[key], number)
            self.store.bind_upload(key, number, plan)
            self._publish(plan)
            report['published'].append({'attempt': key, 'round': number})
        report['pending'] = [key for key, groups in by_attempt.items() if key not in ignored and not complete_attempt(groups)]
        self.store.put('last_import', report)
        return report

    def upload_attempt(self, key, round_number):
        if type(round_number) is not int or not 1 <= round_number <= 7:
            raise ValueError('Round must be 1–7')
        previous = self.store.upload(key)
        if previous:
            if previous['round'] != round_number:
                raise ValueError('Attempt is already bound to another round; refusing rebind')
            return self._publish(previous['plan']) if previous['status'] != 'done' else {'unchanged': True}
        self.scan()
        groups, archives = {}, {}
        for snapshot, archive in self.store.snapshots():
            if attempt_key(snapshot) == key:
                groups[snapshot['group']], archives[snapshot['group']] = snapshot, archive
        if not complete_attempt(groups):
            raise ValueError('All enabled groups must be frozen GP_FINISHED before upload')
        plan = self._plan(key, groups, archives, round_number)
        self.store.bind_upload(key, round_number, plan)
        return self._publish(plan)
