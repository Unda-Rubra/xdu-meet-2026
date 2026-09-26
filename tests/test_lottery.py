import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from raceops import lottery


class LotteryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        config = self.root / 'config'
        config.mkdir()
        (config / 'feishu.json').write_text(json.dumps({
            'base_token': 'base', 'tables': {'users': 'users'}}))
        self.records = {
            'onsite': {'参会情况': ['线下参会'], '已中奖': None, '中奖时间': None,
                       '昵称': '现场用户', 'QQ号': '123450001'},
            'remote': {'参会情况': ['线上填写问卷'], '已中奖': None, '中奖时间': None,
                       '昵称': '远程用户', 'QQ号': '123450002'},
            'won': {'参会情况': ['线下参会'], '已中奖': True, '中奖时间': 1700000000000,
                    '昵称': '往期中奖者', 'QQ号': '123450003'},
        }
        self.patches = []

    def cli(self, action, *args):
        def argument(flag):
            return args[args.index(flag) + 1]
        if action == '+record-list':
            self.assertEqual(json.loads(argument('--filter-json')), lottery.FILTER)
            remaining = [uid for uid, row in self.records.items()
                         if row['参会情况'] == ['线下参会'] and row['已中奖'] in (None, False)]
            offset = int(argument('--offset'))
            page = remaining[offset:offset + 200]
            return self.response(page, offset + len(page) < len(remaining))
        if action == '+record-get':
            return self.response([argument('--record-id')], False)
        if action == '+record-upsert':
            uid, change = argument('--record-id'), json.loads(argument('--json'))
            self.assertEqual(set(change), {'已中奖', '中奖时间'})
            self.patches.append((uid, change))
            self.records[uid].update(change)
            return {'updated': True}
        raise AssertionError(action)

    def response(self, ids, more):
        return {'record_id_list': ids, 'field_id_list': list(lottery.FIELDS),
                'data': [[self.records[uid][field] for field in lottery.FIELDS] for uid in ids],
                'has_more': more, 'timezone': 'Asia/Shanghai'}

    def test_draw_marks_only_onsite_once_in_one_update(self):
        with patch.object(lottery, 'ROOT', self.root), patch.object(lottery, 'cli', side_effect=self.cli):
            first = lottery.draw()
            second = lottery.draw()
        self.assertEqual(first['winner'], '现场用户')
        self.assertEqual(first['eligible_before_draw'], 1)
        self.assertEqual(first['qq_hint'], '…0001')
        self.assertEqual(second, {'eligible': 0, 'winner': None})
        self.assertEqual(len(self.patches), 1)
        self.assertTrue(self.records['onsite']['已中奖'])
        self.assertIsNone(self.records['remote']['中奖时间'])
        self.assertTrue(self.records['won']['已中奖'])

    def test_changed_winner_is_rejected_before_any_patch(self):
        def changing(action, *args):
            if action == '+record-get':
                self.records['onsite']['已中奖'] = True
            return self.cli(action, *args)
        with patch.object(lottery, 'ROOT', self.root), patch.object(lottery, 'cli', side_effect=changing):
            with self.assertRaisesRegex(ValueError, 'changed before update'):
                lottery.draw()
        self.assertEqual(self.patches, [])

    def test_reservoir_sees_all_pages_not_just_first(self):
        self.records = {f'rec{i}': {'参会情况': ['线下参会'], '已中奖': None,
                        '中奖时间': None, '昵称': f'测试{i}', 'QQ号': str(123450000 + i)}
                        for i in range(205)}
        with patch.object(lottery, 'ROOT', self.root), patch.object(lottery, 'cli', side_effect=self.cli):
            result = lottery.draw(randbelow=lambda _: 0)
        self.assertEqual(result['eligible_before_draw'], 205)
        self.assertEqual(result['winner'], '测试204')
        self.assertEqual(len(self.patches), 1)


if __name__ == '__main__':
    unittest.main()
