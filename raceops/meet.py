"""Local, resumable replacement for signup, seven-round publication and clearing."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from .assets import ROOT
from .cli import exclusive, statuses
from .event import load_event, pinned_groups, race_services
from .feishu import Feishu, links, text
from .identity import offline_uuid, validate_roster
from .meet_store import Store
from .model import canonical_hash
from .transport import Backend

CONTROL_FIELDS = ['当前轮次', '本批组数', '上传状态', '最近上传轮次', '最近上传尝试', '最近上传状态', '各组进度']
PARTICIPATION_FIELD = '能够参与小游戏（最终结果）'


def can_participate(fields):
    """Read the user-owned formula, never recompute its rules from input columns."""
    value = fields.get(PARTICIPATION_FIELD)
    if isinstance(value, dict):
        if 'value' not in value:
            raise ValueError(PARTICIPATION_FIELD + ' has an invalid formula response')
        value = value['value']
    if isinstance(value, list):
        if not value:
            return False
        if len(value) != 1:
            raise ValueError(PARTICIPATION_FIELD + ' must return a single boolean')
        value = value[0]
    if isinstance(value, dict):
        value = value.get('text')
    if isinstance(value, str):
        value = value.upper()
    if value in (True, 1, 'TRUE'):
        return True
    if value in (None, '', False, 0, 'FALSE'):
        return False
    raise ValueError(PARTICIPATION_FIELD + ' contains an invalid or unevaluated result')


def load_config(path=None):
    config = json.loads((path or ROOT / 'config/feishu.json').read_text())
    for key in ('credentials_file', 'admin_token_file', 'database'):
        config[key] = str((ROOT / config[key]).resolve())
    if config.get('listen') != '127.0.0.1':
        raise ValueError('Meet service must listen on IPv4 loopback')
    if not 1 <= config['port'] <= 65535 or config['results_interval'] < 5:
        raise ValueError('Invalid service port or polling interval')
    return config


def row_patch(record_id, **fields):
    return {'record_id': record_id, 'fields': fields}


def bound_users(users):
    mapping, errors, folded = {}, [], set()
    for row in users:
        fields, record_id = row['fields'], row['record_id']
        if not can_participate(fields):
            continue
        name = text(fields.get('Minecraft游戏用户名'))
        try:
            player_uuid = offline_uuid(name)
            if name.casefold() in folded:
                raise ValueError('Duplicate or case-ambiguous game name')
            folded.add(name.casefold())
            mapping[record_id] = {'name': name, 'uuid': player_uuid}
        except ValueError as error:
            errors.append({'record_id': record_id, 'reason': str(error)})
    return mapping, errors


class Meet:
    def __init__(self, config, remote=None, idle_check=None):
        self.config = config
        self.store = Store(Path(config['database']))
        self.remote = remote or Feishu(Path(config['credentials_file']), config['base_token'])
        self.tables = config['tables']
        self.idle_check = idle_check or self.require_idle

    def close(self):
        self.store.close()

    def read(self, table, fields=None):
        return self.remote.records(self.tables[table], fields)

    def update(self, table, patches):
        if patches:
            self.remote.update(self.tables[table], patches)

    def control(self):
        records = self.read('control', CONTROL_FIELDS)
        if len(records) != 1:
            raise ValueError('Exactly one grouping control record is required')
        return records[0]

    def require_idle(self):
        states, errors = statuses([Backend(s) for s in race_services(['A', 'B', 'C'])])
        if errors or any(s['state'] != 'IDLE' for s in states.values()):
            raise ValueError('Group changes require all three provisioned race worlds reachable and IDLE')

    def doctor(self):
        found = {t['table_id'] for t in self.remote.tables()}
        for name, table in self.tables.items():
            if table not in found:
                raise ValueError('Missing or inaccessible configured table: ' + name)
        users = self.read('users', ['Minecraft游戏用户名', PARTICIPATION_FIELD])
        bindings, errors = bound_users(users)
        return {'app_id': self.remote.app_id, 'tables': len(self.tables), 'users': len(users),
                'eligible': sum(can_participate(u['fields']) for u in users),
                'bound_players': len(bindings), 'identity_errors': errors,
                'active_operation': self.store.active(), 'migrated': self.store.get('migrated', False)}

    def ensure_schema(self):
        from .meet_migration import migrate
        migrate(self)
        return self.doctor()

    def sync_signups(self):
        users = self.read('users', ['用户ID'])
        preparation = self.read('preparation', ['准备记录', '关联用户'])
        by_user = {}
        for row in preparation:
            related = links(row['fields'].get('关联用户'))
            if len(related) != 1:
                raise ValueError('Preparation record must link exactly one user: ' + row['record_id'])
            if related[0] in by_user:
                raise ValueError('Duplicate preparation records for ' + related[0])
            by_user[related[0]] = row
        missing = [u for u in users if u['record_id'] not in by_user]
        for user in missing:
            fields = {'准备记录': text(user['fields'].get('用户ID')) or user['record_id'],
                      '关联用户': [user['record_id']]}
            self.remote.create(self.tables['preparation'], [fields],
                               self.store.token('signup:' + user['record_id']))
        return {'created': len(missing), 'users': len(users)}

    def _group_ids(self):
        groups = {}
        for row in self.read('groups', ['轮次', '组别', '分组标识', '成员']):
            fields = row['fields']
            key = (text(fields.get('轮次')), text(fields.get('组别')))
            if key in groups:
                raise ValueError('Duplicate round/group structure')
            groups[key] = row['record_id']
        expected = {(f'第{n}轮', g) for n in range(1, 8) for g in 'ABC'}
        if set(groups) != expected:
            raise ValueError('Preserve exactly 21 round/group structure records')
        return groups

    def group(self):
        with exclusive():
            self.idle_check()
            if self.store.active():
                raise ValueError('An unfinished plan exists; resume it before adding users')
            self.sync_signups()
            control = self.control()
            users = self.read('users', [PARTICIPATION_FIELD, '所属分组', 'Minecraft游戏用户名'])
            group_ids = self._group_ids()
            reverse = {rid: (int(n[1:-1]), g) for (n, g), rid in group_ids.items()}
            existing = {u['record_id']: links(u['fields'].get('所属分组')) for u in users}
            eligible = sorted(u['record_id'] for u in users if can_participate(u['fields']))
            has_groups = any(existing.values())
            count = control['fields'].get('本批组数') if has_groups else (3 if len(eligible) >= 21 else 2)
            if count not in (2, 3):
                raise ValueError('Existing grouping requires a preserved 本批组数 of 2 or 3')
            count = int(count)
            if not 2 <= len(eligible) <= 17 * count:
                raise ValueError('Participants exceed capacity of the fixed group count, or fewer than two')
            assignments = {rid: list(values) for rid, values in existing.items()}
            rounds = {str(n): {g: [] for g in 'ABC'[:count]} for n in range(1, 8)}
            for rid, values in existing.items():
                selected = [reverse.get(v) for v in values]
                if values and (any(v is None for v in selected)
                               or len({v[0] for v in selected}) != len(values)
                               or any(v[1] not in 'ABC'[:count] for v in selected)):
                    raise ValueError('Existing membership is duplicated or inactive; no assignments changed: ' + rid)
                if rid in eligible:
                    for number, group in selected:
                        rounds[str(number)][group].append(rid)
            seed = secrets.token_hex(32)
            new_ids = [rid for rid in eligible if len(existing[rid]) < 7]
            for number in range(1, 8):
                missing = [rid for rid in new_ids if not any(reverse[v][0] == number for v in existing[rid])]
                for rid in sorted(missing, key=lambda rid: canonical_hash([seed, number, rid])):
                    group = min(rounds[str(number)], key=lambda g: (len(rounds[str(number)][g]), g))
                    if len(rounds[str(number)][group]) >= 17:
                        raise ValueError('A group exceeds server capacity; cannot rebalance existing members')
                    rounds[str(number)][group].append(rid)
                    assignments[rid].append(group_ids[(f'第{number}轮', group)])
            plan = {'batch': secrets.token_hex(16), 'control': control['record_id'], 'count': len(eligible),
                    'groups': count, 'eligible': eligible, 'rounds': rounds, 'assignments': assignments,
                    'expected_before': existing,
                    'users': [row_patch(rid, **{'所属分组': assignments[rid]}) for rid in new_ids]}
            operation = self.store.begin('group', plan)
            return self._apply(operation, 'group', plan)

    def clear(self):
        with exclusive():
            self.idle_check()
            if self.store.active():
                raise ValueError('Resume the unfinished plan before clearing')
            control = self.control()
            users = self.read('users', ['所属分组'])
            plan = {'control': control['record_id'],
                    'users': [row_patch(u['record_id'], **{'所属分组': []}) for u in users]}
            operation = self.store.begin('clear', plan)
            return self._apply(operation, 'clear', plan)

    def resume(self):
        with exclusive():
            self.idle_check()
            operation = self.store.active()
            if not operation:
                return {'resumed': False}
            return self._apply(operation['id'], operation['kind'], operation['plan'])

    def _apply(self, operation, kind, plan):
        try:
            if kind == 'group':
                current = {r['record_id']: links(r['fields'].get('所属分组')) for r in self.read('users', ['所属分组'])}
                for rid, before in plan['expected_before'].items():
                    if rid not in current or set(current[rid]) not in (set(before), set(plan['assignments'][rid])):
                        raise ValueError('Membership changed outside the saved plan; refusing overwrite')
                self.update('control', [row_patch(plan['control'], **{'本批组数': plan['groups']})])
            self.update('users', plan['users'])
            # Compare stored associations, never formula counts. Any partial write remains resumable.
            actual = {r['record_id']: links(r['fields'].get('所属分组')) for r in self.read('users', ['所属分组'])}
            for expected in plan['users']:
                if set(actual.get(expected['record_id'], [])) != set(expected['fields']['所属分组']):
                    raise ValueError('Membership readback mismatch; retry this saved plan')
            self.store.put('batch', plan if kind == 'group' else None)
            self.store.finish(operation)
            return {'operation_id': operation, 'status': 'done', 'kind': kind,
                    'participants': plan.get('count'), 'groups': plan.get('groups')}
        except Exception as error:
            self.store.finish(operation, str(error))
            raise

    def sync(self):
        return self.resume() if self.store.active() else self.sync_signups()

    def roster(self, round_number):
        event = load_event()
        if not 1 <= round_number <= event['grand_prix_rounds']:
            raise ValueError('Round is not configured')
        batch = self.store.get('batch')
        if not batch or self.store.active():
            raise ValueError('Run the grouping script to adopt current memberships or add new users before game handoff')
        users = self.read('users', [PARTICIPATION_FIELD, '所属分组', 'Minecraft游戏用户名'])
        binding, errors = bound_users(users)
        if errors:
            raise ValueError('Fix Minecraft identity mapping for record IDs: ' + ','.join(e['record_id'] for e in errors))
        if set(binding) != set(batch['eligible']):
            raise ValueError('Participant selection changed since grouping; reconcile explicitly')
        for row in users:
            if set(links(row['fields'].get('所属分组'))) != set(batch['assignments'].get(row['record_id'], [])):
                raise ValueError('Membership was edited after publication; do not route a stale local roster')
        roster = validate_roster({'schema_version': 1, 'event_id': event['event_id'],
                                 'grand_prix_round': round_number,
                                 'groups': {g: [binding[rid] for rid in ids]
                                            for g, ids in batch['rounds'][str(round_number)].items()}}, event, round_number)
        directory = ROOT / 'config/rosters'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f'round-{round_number}.json'
        temporary = path.with_suffix('.tmp')
        with temporary.open('w') as stream:
            json.dump(roster, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        self.store.put('identity:' + canonical_hash(roster['groups']),
                       {player['uuid']: rid for rid, player in binding.items()})
        return roster

    def game_command(self, command, round_number=None, preset=None, reason=None, archive=None):
        if self.store.active():
            raise ValueError('Finish publication before controlling game servers')
        if command == 'preset':
            with exclusive():
                self.idle_check()
                self.roster(round_number)
            argv = ['scripts/racectl', 'preset', preset or f'gp{round_number}', '--round', str(round_number)]
        elif command == 'route':
            if type(round_number) is not int or not 1 <= round_number <= 7:
                raise ValueError('A valid round is required')
            argv = ['scripts/route-roster', '--round', str(round_number)]
        elif command in ('start', 'status', 'export'):
            argv = ['scripts/racectl', command]
        elif command == 'stop':
            if not reason:
                raise ValueError('A stop reason is required')
            argv = ['scripts/racectl', 'stop', '--reason', reason]
        elif command in ('reset', 'lobby'):
            if not archive:
                raise ValueError('An archive receipt is required')
            path = (ROOT / archive).resolve()
            if not path.is_relative_to((ROOT / 'exports').resolve()):
                raise ValueError('Archive must be under exports/')
            if command == 'reset':
                if not reason:
                    raise ValueError('A reset reason is required')
                argv = ['scripts/racectl', 'reset', '--archive', str(path), '--reason', reason]
            else:
                if type(round_number) is not int or not 1 <= round_number <= 7:
                    raise ValueError('A valid round is required')
                argv = ['scripts/route-roster', '--round', str(round_number), '--lobby', '--archive', str(path)]
        else:
            raise ValueError('Unsupported game command')
        result = subprocess.run([sys.executable, *argv], cwd=ROOT, capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return {'output': result.stdout}
