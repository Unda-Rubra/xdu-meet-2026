import copy
import json
from contextlib import nullcontext
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from raceops.assets import digest
from raceops.feishu import Feishu, FeishuError
from raceops.meet import Meet
from raceops.meet_results import Results, read_archive
from raceops.model import canonical_hash
from raceops.meet_server import advance_barrier
from raceops.manual_game import sync_operator_privileges
from raceops.qq_identity import validate_qq


class Remote:
    def __init__(self):
        self.rows = {
            'users': [{'record_id': 'u1', 'fields': {'QQ号': 900000001}}],
            'control': [{'record_id': 'control', 'fields': {'当前轮次': '第1轮'}}],
            'multipliers': [{'record_id': str(i), 'fields': {'轮次': f'第{i}轮', '已发布批次': ''}} for i in range(1, 8)],
            'scores': [], 'batch': []}
        self.fail_once = False

    def records(self, table, fields=None):
        return copy.deepcopy(self.rows[table])

    def update(self, table, patches):
        for patch_value in patches:
            row = next(r for r in self.rows[table] if r['record_id'] == patch_value['record_id'])
            row['fields'].update(patch_value['fields'])

    def upsert(self, table, fields, store):
        for value in fields:
            row = next((r for r in self.rows[table] if r['fields']['导入键'] == value['导入键']), None)
            if row is None:
                self.rows[table].append({'record_id': str(len(self.rows[table])), 'fields': copy.deepcopy(value)})
            else:
                row['fields'].update(value)
        if table == 'scores' and self.fail_once:
            self.fail_once = False
            raise ValueError('Lost response after successful score insertion')


class ManualUploadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.remote = Remote()
        self.meet = Meet({'database': str(self.path / 'state.sqlite'), 'tables': {n: n for n in self.remote.rows}}, self.remote)
        self.addCleanup(self.meet.close)
        snapshot = {'event_id': 'event', 'attempt_id': 'attempt', 'state': 'GP_FINISHED', 'frozen': 1,
                    'active_groups': ['A'], 'group': 'A', 'settings_hash': 'settings',
                    'roster': [{'uuid': 'p1', 'name': 'ArrivedPlayer', 'qq': '900000001'}],
                    'results': {'p1': {'status': 'FINISHED', 'total': 32}}}
        self.snapshot_path = self.path / 'race-a.snapshot.json'
        self.snapshot_path.write_text(json.dumps({'snapshot': snapshot}))
        self.manifest = {'complete': True, 'coherent_attempt': True,
                         'files': {self.snapshot_path.name: digest(self.snapshot_path)},
                         'servers': {'race-a': {'snapshot_file': self.snapshot_path.name, 'snapshot_hash': canonical_hash(snapshot)}}}
        (self.path / 'manifest.json').write_text(json.dumps(self.manifest))
        self.token = self.meet.store.register('attempt', self.path, digest(self.path / 'manifest.json'))['token']

    def test_archive_token_does_not_publish_until_explicit_upload(self):
        self.assertEqual(self.remote.rows['scores'], [])
        self.assertNotIn('游戏昵称', self.remote.rows['users'][0]['fields'])
        Results(self.meet).upload(self.token)
        self.assertEqual(self.remote.rows['users'][0]['fields']['游戏昵称'], 'ArrivedPlayer')
        self.assertEqual(self.remote.rows['scores'][0]['fields']['QQ号'], '900000001')
        self.assertEqual(self.remote.rows['multipliers'][0]['fields']['已发布批次'], self.token)
        Results(self.meet).upload(self.token)
        self.assertEqual(len(self.remote.rows['scores']), 1)

    def test_lost_response_retry_keeps_first_selected_round(self):
        self.remote.fail_once = True
        with self.assertRaises(ValueError):
            Results(self.meet).upload(self.token)
        self.assertEqual(self.remote.rows['multipliers'][0]['fields']['已发布批次'], '')
        self.remote.rows['control'][0]['fields']['当前轮次'] = '第2轮'
        result = Results(self.meet).upload(self.token)
        self.assertEqual(result['round'], 1)
        self.assertEqual(self.remote.rows['scores'][0]['fields']['轮次'], '第1轮')
        self.assertEqual(self.remote.rows['multipliers'][1]['fields']['已发布批次'], '')
        self.assertEqual(len(self.remote.rows['scores']), 1)

    def test_unknown_signup_does_not_bind_or_publish(self):
        self.remote.rows['users'] = []
        with self.assertRaises(ValueError):
            Results(self.meet).upload(self.token)
        self.assertIsNone(self.meet.store.upload(self.token))
        self.assertEqual(self.remote.rows['scores'], [])

    def test_archive_tampering_is_rejected_before_cloud_writes(self):
        self.snapshot_path.write_text('{}')
        with self.assertRaises(ValueError):
            Results(self.meet).upload(self.token)
        self.assertEqual(self.remote.rows['scores'], [])

    def test_duplicate_signup_qq_is_not_arbitrarily_assigned(self):
        self.remote.rows['users'].append({'record_id': 'u2', 'fields': {'QQ号': '900000001'}})
        with self.assertRaises(ValueError):
            Results(self.meet).upload(self.token)
        self.assertEqual(self.remote.rows['scores'], [])

    def test_other_bad_signups_do_not_block_a_known_racer(self):
        self.remote.rows['users'].extend([
            {'record_id': 'bad', 'fields': {'QQ号': 'not-a-qq'}},
            {'record_id': 'other-a', 'fields': {'QQ号': '900000003'}},
            {'record_id': 'other-b', 'fields': {'QQ号': '900000003'}},
        ])
        result = Results(self.meet).upload(self.token)
        self.assertEqual(result['status'], '完整')
        self.assertEqual(self.remote.rows['scores'][0]['fields']['关联用户'], ['u1'])



class AdmissionTests(unittest.TestCase):
    def test_first_pack_load_after_ninety_seconds_starts_all_groups(self):
        from raceops.manual_game import start
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'template-world').mkdir()
            (root / 'template-world/xdu-template.json').write_text('{"template_hash":"test"}')
            people = {'a': {'name': 'Alice', 'server': 'lobby'},
                      'b': {'name': 'Bob', 'server': 'lobby'}}
            identities = {'a': {'qq': '900000001'}, 'b': {'qq': '900000002'}}
            admission = {'active': False, 'admins': {}, 'admin_sessions': {}}
            states = {name: {'state': 'IDLE', 'boot_id': 1} for name in ('race-a', 'race-b', 'race-c')}
            clock = [0.0]

            class Backend:
                def __init__(self, name): self.service = name
                def read(self): return states[self.service].copy()
                def stage(self, *_): pass
                def command(self, command):
                    if command.startswith('data modify storage xdu_race:state current set '):
                        states[self.service]['state'] = 'PREPARED'
                    elif command == 'function xdu_race:start':
                        states[self.service]['state'] = 'RUNNING'
                    return 'Done'
                def commands(self, commands):
                    if commands[0].startswith('execute if entity '):
                        return ['Test passed' if clock[0] >= 120 else 'Test failed' for _ in commands]
                    return ['Done' for _ in commands]

            def route(command):
                _, name, server = command.split()
                next(p for p in people.values() if p['name'] == name)['server'] = server

            with patch('raceops.manual_game.ROOT', root), \
                 patch('raceops.manual_game.exclusive', return_value=nullcontext()), \
                 patch('raceops.manual_game.sync_admins'), \
                 patch('raceops.manual_game.policy', return_value=admission), \
                 patch('raceops.manual_game.save_policy'), \
                 patch('raceops.manual_game.connected', return_value=people), \
                 patch('raceops.manual_game.load_identities', return_value=identities), \
                 patch('raceops.manual_game.settings', return_value={'track_count': 1}), \
                 patch('raceops.manual_game.apply_settings'), \
                 patch('raceops.manual_game.Backend', Backend), \
                 patch('raceops.manual_game.scoreboard', return_value={'gameState': 1}), \
                 patch('raceops.manual_game.proxy_command', side_effect=route), \
                 patch('raceops.manual_game.time.monotonic', side_effect=lambda: clock[0]), \
                 patch('raceops.manual_game.time.sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)):
                result = start()
            self.assertEqual(result['groups'], {'A': 1, 'B': 1})
            self.assertGreaterEqual(clock[0], 120)
            self.assertEqual([states[name]['state'] for name in ('race-a', 'race-b')], ['RUNNING', 'RUNNING'])


class BarrierTests(unittest.TestCase):
    def test_a_finished_group_waits_and_recovered_release_does_not_skip(self):
        states = {'race-a': {'state': 'WAITING', 'track_index': 1, 'attempt_id': 'gp'},
                  'race-b': {'state': 'RUNNING', 'track_index': 1, 'attempt_id': 'gp'}}
        admission = {'attempt': 'gp'}
        class Backend:
            def __init__(self, server): self.server = server
            def read(self): return copy.deepcopy(states[self.server])
            def command(self, _): states[self.server]['armed'] = True
        with patch('raceops.meet_server.Backend', Backend), patch('raceops.meet_server.save_policy'):
            advance_barrier(admission, states)
            self.assertNotIn('armed', states['race-a'])
            states['race-b']['state'] = 'WAITING'
            advance_barrier(admission, states)
            self.assertTrue(all(s['armed'] for s in states.values()))
            self.assertEqual(admission['release_track'], 1)
            states['race-a'].update(state='RUNNING', track_index=2)
            advance_barrier(admission, states)
            self.assertEqual(states['race-a']['track_index'], 2)
            states['race-b'].update(state='RUNNING', track_index=2)
            advance_barrier(admission, states)
            self.assertNotIn('release_track', admission)


class AdminPrivilegesTests(unittest.TestCase):
    def test_only_authorized_online_admin_is_op_and_switch_revokes_old_server(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            roles = {'admins': {'admin-uuid': 'A'}, 'admin_sessions': {'admin-uuid': 'approved-session'}}
            class Backend:
                def __init__(self, server): self.server = server
                def command(self, command):
                    path = root / 'volumes/event' / self.server / 'ops.json'
                    path.parent.mkdir(parents=True, exist_ok=True)
                    ops = json.loads(path.read_text()) if path.exists() else []
                    if command.startswith('execute if entity '): return 'Test passed'
                    verb, name = command.split(' ', 1)
                    if verb == 'op' and not any(row['name'] == name for row in ops):
                        ops.append({'name': name})
                    if verb == 'deop': ops = [row for row in ops if row['name'] != name]
                    path.write_text(json.dumps(ops))
                    return 'Done'
            with patch('raceops.manual_game.ROOT', root), patch('raceops.manual_game.Backend', Backend), \
                 patch('raceops.manual_game.save_policy'):
                people = {'admin-uuid': {'name': 'Commentator', 'server': 'lobby', 'session': 'spoof-session'},
                          'guest-uuid': {'name': 'Guest', 'server': 'lobby', 'session': 'guest-session'}}
                sync_operator_privileges(roles, people)
                self.assertFalse((root / 'volumes/event/lobby/ops.json').exists())
                people['admin-uuid']['session'] = 'approved-session'
                sync_operator_privileges(roles, people)
                self.assertEqual(json.loads((root / 'volumes/event/lobby/ops.json').read_text()),
                                 [{'name': 'Commentator'}])
                people['admin-uuid']['server'] = 'race-b'
                sync_operator_privileges(roles, people)
                self.assertEqual(json.loads((root / 'volumes/event/lobby/ops.json').read_text()), [])
                self.assertEqual(json.loads((root / 'volumes/event/race-b/ops.json').read_text()),
                                 [{'name': 'Commentator'}])
                people['admin-uuid']['session'] = 'reconnected-session'
                sync_operator_privileges(roles, people)
                self.assertEqual(json.loads((root / 'volumes/event/race-b/ops.json').read_text()), [])
                people.pop('admin-uuid')
                sync_operator_privileges(roles, people)
                self.assertEqual(json.loads((root / 'volumes/event/race-b/ops.json').read_text()), [])


class FormatAndQQTests(unittest.TestCase):
    def test_qq_identifiers_reject_lossy_or_ambiguous_inputs(self):
        for value in ['012345', ' 12345', '12345 ', '+12345', 12345.0, True, '1234', '1234567890123']:
            with self.subTest(value=value), self.assertRaises(ValueError): validate_qq(value)
        self.assertEqual(validate_qq('123456789012'), '123456789012')

    def test_ui_only_formula_palette_cannot_reach_lossy_writer(self):
        field = {'field_id': 'status', 'field_name': '状态', 'type': 20,
                 'property': {'formula_expression': 'TRUE()', 'type': {'data_type': 3, 'ui_type': 'SingleSelect',
                              'ui_property': {'options': [{'id': 'yes', 'name': 'TRUE', 'color': 48}]}}}}
        client = Feishu.__new__(Feishu)
        client.request = lambda *args, **kwargs: self.fail('Lossy update reached the remote writer')
        with self.assertRaises(FeishuError): client.update_field('table', field, description='Help')
