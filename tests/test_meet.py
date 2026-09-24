import copy
import json
from pathlib import Path
import tempfile
import unittest

from raceops.feishu import Feishu, FeishuError
from raceops.identity import offline_uuid
from raceops.meet import Meet, PARTICIPATION_FIELD, bound_users, can_participate
from raceops.meet_results import Results, read_archive, result_facts, snapshot_key
from raceops.model import canonical_hash


class MemoryBase:
    app_id = 'cli_test'
    upsert = Feishu.upsert

    def __init__(self, participants=21):
        self.data = {
            'users': [{'record_id': f'recUser{i}', 'fields': {'用户ID': str(i), 'Minecraft游戏用户名': f'Player{i}',
                       '不参与比赛': False, PARTICIPATION_FIELD: {'type': 3, 'value': ['TRUE']}, '所属分组': []}} for i in range(participants)],
            'preparation': [], 'control': [{'record_id': 'recControl', 'fields': {'当前轮次': '第1轮'}}],
            'groups': [{'record_id': f'recGroup{n}{g}', 'fields': {'轮次': f'第{n}轮', '组别': g}}
                       for n in range(1, 8) for g in 'ABC'], 'scores': [],
            'multipliers': [{'record_id': f'recRound{i}', 'fields': {'轮次': f'第{i}轮', '积分倍率': 1.5}} for i in range(1, 8)],
            'raw': [], 'gp': []}
        self.tokens, self.fail_once, self.writes = {}, None, 0

    def records(self, table, fields=None):
        return copy.deepcopy(self.data[table])

    def update(self, table, records):
        for record in records:
            row = next(r for r in self.data[table] if r['record_id'] == record['record_id'])
            row['fields'].update(copy.deepcopy(record['fields']))
            self.writes += 1
            if self.fail_once == table:
                self.fail_once = None
                raise RuntimeError('Connection lost after remote write')

    def create(self, table, fields, token):
        if table == 'preparation' and any(set(row) - {'准备记录', '关联用户'} for row in fields):
            raise FeishuError('Preparation schema has no other writable fields')
        if token in self.tokens:
            return self.tokens[token]
        rows = [{'record_id': f'rec{table}{len(self.data[table]) + i}', 'fields': copy.deepcopy(f)} for i, f in enumerate(fields)]
        self.data[table].extend(rows)
        self.tokens[token] = copy.deepcopy(rows)
        self.writes += len(rows)
        if self.fail_once == table:
            self.fail_once = None
            raise RuntimeError('Connection lost after remote create')
        return rows


def finished_snapshot(group='A', attempt='attempt1', names=('Player0', 'Player1')):
    roster = [{'name': name, 'uuid': offline_uuid(name)} for name in names]
    tracks = [{'track_index': n, 'started': True, 'closed': True, 'settled': True, 'commit_phase_reached': True,
               'players': [{'uuid': p['uuid'], 'name_at_start': p['name'], 'started': True, 'finished': True,
                            'status': 'FINISHED', 'finish_pos_raw': i + 1, 'award': 10 - i,
                            'native_total': (10 - i) * n, 'native_commit_observed': True}
                           for i, p in enumerate(roster)]} for n in range(1, 7)]
    return {'event_id': 'xdu-2026-fall', 'grand_prix_round': 7, 'attempt_id': attempt, 'group': group,
            'active_groups': ['A', 'B'], 'state': 'GP_FINISHED', 'frozen': True, 'revision': 10,
            'identity_mode': 'offline_trusted_private', 'ai_count': 0, 'roster': roster, 'tracks': tracks,
            'preset_hash': 'preset', 'roster_hash': 'roster', 'settings_hash': 'settings', 'template_hash': 'template'}


class FieldFormatTests(unittest.TestCase):
    def test_ui_only_formula_palette_is_rejected_before_any_write(self):
        field = {'field_id': 'fldStatus', 'field_name': '状态', 'type': 20,
                 'property': {'formula_expression': 'TRUE()', 'type': {
                     'data_type': 3, 'ui_type': 'SingleSelect', 'ui_property': {
                         'options': [{'id': 'optTrue', 'name': 'TRUE', 'color': 48}],
                         'defaultValue': 'LastOption'}}}}
        client = Feishu.__new__(Feishu)
        def reject_write(*args, **kwargs):
            self.fail('A UI-only format must not reach the lossy OpenAPI writer')
        client.request = reject_write
        with self.assertRaises(FeishuError):
            client.update_field('table', field, formula='FALSE()')
        with self.assertRaises(FeishuError):
            client.update_field('table', field, description='New help')


class MeetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.remote = MemoryBase()
        self.config = {'database': str(Path(self.temporary.name) / 'state.sqlite'),
                       'tables': {k: k for k in self.remote.data if k not in ('raw', 'gp')}}
        self.meet = Meet(self.config, self.remote, idle_check=lambda: None)
        self.meet.store.put('raw_table', 'raw')
        self.meet.store.put('result_table', 'gp')
        self.meet.store.put('round_upload_ready', True)
        self.importer = Results(self.meet)
        self.importer.scan = lambda: {'new_archives': 0, 'errors': []}

    def tearDown(self):
        self.meet.close()
        self.temporary.cleanup()

    def observe(self, group, attempt='attempt1', complete=True):
        s = finished_snapshot(group, attempt, ('Player0', 'Player1') if group == 'A' else ('Player2', 'Player3'))
        if not complete:
            s['state'], s['frozen'], s['revision'] = 'RACING', False, 9
        self.meet.store.remember_snapshot(snapshot_key(s), s, canonical_hash(s), Path('archive'))
        return s

    def test_twenty_excludes_one_and_keeps_all_existing_members_on_rerun(self):
        self.remote.data['users'][-1]['fields'][PARTICIPATION_FIELD] = {'type': 3, 'value': ['FALSE']}
        self.assertEqual(self.meet.group()['groups'], 2)
        before = copy.deepcopy(self.remote.data['users'])
        self.remote.data['users'][-1]['fields'][PARTICIPATION_FIELD] = {'type': 3, 'value': ['TRUE']}
        self.remote.data['users'][-1]['fields']['不参与比赛'] = True
        result = self.meet.group()
        self.assertEqual((result['participants'], result['groups']), (21, 2))
        for a, b in zip(self.remote.data['users'][:-1], before[:-1]):
            self.assertEqual(a['fields']['所属分组'], b['fields']['所属分组'])
        self.assertEqual(len(self.remote.data['users'][-1]['fields']['所属分组']), 7)
        plan = self.meet.store.get('batch')
        self.assertTrue(all(sorted(map(len, r.values())) == [10, 11] for r in plan['rounds'].values()))

    def test_partial_publication_replays_same_plan_after_restart(self):
        self.remote.fail_once = 'users'
        with self.assertRaises(RuntimeError):
            self.meet.group()
        plan = self.meet.store.active()['plan']
        self.meet.close()
        self.meet = Meet(self.config, self.remote, idle_check=lambda: None)
        self.meet.resume()
        self.assertEqual(self.meet.store.get('batch')['assignments'], plan['assignments'])
    def test_partial_existing_assignment_is_preserved_while_missing_rounds_are_filled(self):
        self.remote.data['users'][0]['fields']['所属分组'] = ['recGroup1A']
        self.remote.data['control'][0]['fields']['本批组数'] = 3
        self.meet.group()
        assigned = self.remote.data['users'][0]['fields']['所属分组']
        self.assertEqual(len(assigned), 7)
        self.assertIn('recGroup1A', assigned)


    def test_half_round_does_not_upload_and_cloud_round_overrides_game_round(self):
        self.observe('A')
        self.observe('B', complete=False)
        self.importer.sync(capture=False)
        self.assertEqual(self.remote.data['scores'], [])
        self.assertEqual(self.remote.data['raw'], [])
        self.remote.data['control'][0]['fields']['当前轮次'] = '第3轮'
        self.observe('B')
        self.importer.sync(capture=False)
        self.assertEqual({r['fields']['轮次'] for r in self.remote.data['scores']}, {'第3轮'})
        self.assertEqual(self.remote.data['gp'][0]['fields']['原游戏轮次'], 7)
        self.assertEqual(self.remote.data['control'][0]['fields']['当前轮次'], '第3轮')

    def test_lost_response_restart_and_changed_cloud_round_keep_original_binding(self):
        self.observe('A'); self.observe('B')
        self.remote.fail_once = 'scores'
        with self.assertRaises(RuntimeError):
            self.importer.sync(capture=False)
        self.assertNotIn('已发布批次', self.remote.data['multipliers'][0]['fields'])
        self.remote.data['control'][0]['fields']['当前轮次'] = '第2轮'
        self.meet.close()
        self.meet = Meet(self.config, self.remote, idle_check=lambda: None)
        self.importer = Results(self.meet)
        self.importer.scan = lambda: {'new_archives': 0, 'errors': []}
        self.importer.sync(capture=False)
        self.assertEqual(len(self.remote.data['scores']), 4)
        self.assertEqual({r['fields']['轮次'] for r in self.remote.data['scores']}, {'第1轮'})
        self.assertEqual(self.remote.data['control'][0]['fields']['最近上传轮次'], 1)
        writes = self.remote.writes
        self.importer.sync(capture=False)
        self.assertEqual(writes, self.remote.writes)

    def test_replay_switches_pointer_only_after_complete_valid_attempt(self):
        self.observe('A'); self.observe('B')
        self.importer.sync(capture=False)
        first = self.remote.data['multipliers'][0]['fields']['已发布批次']
        self.observe('A', 'replay')
        self.importer.sync(capture=False)
        self.assertEqual(self.remote.data['multipliers'][0]['fields']['已发布批次'], first)
        self.observe('B', 'replay')
        self.importer.sync(capture=False)
        self.assertEqual(self.remote.data['multipliers'][0]['fields']['已发布批次'], 'xdu-2026-fall/replay')
        with self.assertRaisesRegex(ValueError, 'refusing rebind'):
            self.importer.upload_attempt(first, 2)
        self.assertEqual(self.importer.upload_attempt(first, 1), {'unchanged': True})
        self.assertEqual(self.remote.data['multipliers'][0]['fields']['已发布批次'], 'xdu-2026-fall/replay')

    def test_unknown_identity_uploads_evidence_without_publishing_incomplete_ranking(self):
        self.observe('A'); self.observe('B')
        self.remote.data['users'][0]['fields']['Minecraft游戏用户名'] = ''
        self.importer.sync(capture=False)
        self.assertEqual(len(self.remote.data['raw']), 24)
        self.assertEqual(len(self.remote.data['scores']), 4)
        self.assertEqual(self.remote.data['gp'][0]['fields']['数据状态'], '数据异常')
        self.assertNotIn('已发布批次', self.remote.data['multipliers'][0]['fields'])
        self.assertTrue(all('本轮最终得分' not in r['fields'] and '名次' not in r['fields'] for r in self.remote.data['scores']))

    def test_final_participation_denial_prevents_publishing_despite_old_checkbox(self):
        self.observe('A'); self.observe('B')
        self.remote.data['users'][0]['fields'][PARTICIPATION_FIELD] = {'type': 3, 'value': ['FALSE']}
        self.importer.sync(capture=False)
        self.assertEqual(self.remote.data['gp'][0]['fields']['数据状态'], '数据异常')
        self.assertNotIn('已发布批次', self.remote.data['multipliers'][0]['fields'])

    def test_false_or_missing_formula_never_falls_back_to_old_checkbox(self):
        row = self.remote.data['users'][0]
        row['fields'][PARTICIPATION_FIELD] = {'type': 3, 'value': ['FALSE']}
        self.assertEqual(bound_users([row]), ({}, []))
        del row['fields'][PARTICIPATION_FIELD]
        self.assertEqual(bound_users([row]), ({}, []))
        row['fields'][PARTICIPATION_FIELD] = {'type': 1, 'value': [{'text': '#ERROR!'}]}
        with self.assertRaises(ValueError):
            bound_users([row])

    def test_unseen_multiple_attempts_require_explicit_binding_not_guessing(self):
        for attempt in ('first', 'second'):
            self.observe('A', attempt); self.observe('B', attempt)
        with self.assertRaisesRegex(ValueError, 'Multiple unseen'):
            self.importer.sync(capture=False)
        self.assertEqual(self.remote.data['scores'], [])

    def test_invalid_round_selection_does_not_bind_or_write_scores(self):
        self.observe('A'); self.observe('B')
        for value in (None, 2, '第8轮', ['第1轮', '第2轮']):
            with self.subTest(selection=value):
                self.remote.data['control'][0]['fields']['当前轮次'] = value
                with self.assertRaises(ValueError):
                    self.importer.sync(capture=False)
                self.assertIsNone(self.meet.store.upload('xdu-2026-fall/attempt1'))
                self.assertEqual(self.remote.data['scores'], [])

    def test_two_group_monitor_survives_unavailable_unused_c(self):
        from contextlib import nullcontext
        from unittest.mock import patch

        class AvailableBackend:
            def __init__(self, service):
                if service == 'race-c':
                    raise RuntimeError('Unused C is offline')

            def read(self, path='current', storage=None):
                return {'state': 'IDLE'} if path == 'current' else {}

        with patch('raceops.meet_results.pinned_groups', return_value=['A', 'B']), \
             patch('raceops.meet_results.Backend', AvailableBackend), \
             patch('raceops.meet_results.exclusive', return_value=nullcontext()):
            self.importer.capture()
        self.assertEqual(self.remote.data['control'][0]['fields']['各组进度'], 'race-a: IDLE；race-b: IDLE')


class EvidenceTests(unittest.TestCase):
    def test_tie_is_valid_evidence_but_disconnect_is_not_implicitly_dnf(self):
        s = finished_snapshot()
        for track in s['tracks']:
            track['players'][1]['award'] = 10
            track['players'][1]['native_total'] = 10 * track['track_index']
        facts, errors = result_facts(s)
        self.assertEqual(errors, [])
        self.assertEqual({p['total'] for p in facts.values()}, {60})
        s['tracks'][-1]['players'][0]['status'] = 'DISCONNECTED'
        self.assertTrue(result_facts(s)[1])
        self.assertEqual(result_facts(s)[0][offline_uuid('Player0')]['status'], 'DISCONNECTED')
        s['tracks'][-1]['players'][0]['status'] = 'UNFINISHED'
        self.assertEqual(result_facts(s)[0][offline_uuid('Player0')]['status'], 'UNFINISHED')

    def test_explicit_dnf_and_dns_are_preserved_as_facts(self):
        s = finished_snapshot()
        for t in s['tracks']:
            t['players'][1].update(status='DNS', started=False, finished=False, award=0, native_total=0, finish_pos_raw=None)
        facts, errors = result_facts(s)
        self.assertEqual(errors, [])
        self.assertEqual(facts[offline_uuid('Player1')]['status'], 'DNS')

    def test_transport_alias_and_tamper_detection(self):
        from raceops.assets import digest
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            s = finished_snapshot(); s['server'] = 'race-a'
            (root / 'race.json').write_text(json.dumps({'snapshot': s}))
            receipt = {'snapshot_file': 'race.json', 'snapshot_hash': canonical_hash(s), 'attempt_id': s['attempt_id']}
            manifest = {'schema_version': 1, 'servers': {'transport-alias': receipt}, 'files': {'race.json': digest(root / 'race.json')}}
            (root / 'manifest.json').write_text(json.dumps(manifest))
            self.assertEqual(read_archive(root)[0][0]['server'], 'race-a')
            (root / 'race.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                read_archive(root)


if __name__ == '__main__':
    unittest.main()
