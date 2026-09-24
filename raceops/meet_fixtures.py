"""Explicit, backed-up test-data operations. Never delete arbitrary attendees by nickname."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import uuid

from .assets import ROOT
from .feishu import flag, links
from .meet import Meet, load_config
from .meet_migration import delete_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    fill = sub.add_parser('fill-users')
    fill.add_argument('--count', type=int, default=4)
    fill.add_argument('--apply', action='store_true')
    clean = sub.add_parser('clean-users')
    clean.add_argument('--all-test-users', action='store_true', help='Also remove existing users explicitly flagged 测试')
    clean.add_argument('--apply', action='store_true')
    sub.add_parser('clear-groups').add_argument('--apply', action='store_true')
    args = parser.parse_args()
    config = load_config()
    lock = Path(config['database']).with_suffix('.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as file:
        try:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Stop meet-service before fixture maintenance, then restart it.') from None
        meet = Meet(config)
        try:
            meet.idle_check()
            if meet.store.active():
                raise ValueError('Resume unfinished grouping first')
            if args.action == 'clear-groups':
                print(json.dumps(meet.clear() if args.apply else {'preview': 'Clear all memberships; preserve users and results'}, ensure_ascii=False))
            elif args.action == 'fill-users':
                if not 1 <= args.count <= 51:
                    raise ValueError('Count must be 1–51')
                batch = uuid.uuid4().hex[:8]
                fields = [{'昵称': f'MOCK_{batch}_{i}', 'Minecraft游戏用户名': f'M{batch}{i:02d}',
                           '测试': True, '不参与比赛': False, '参会情况': '线下参会'} for i in range(args.count)]
                if args.apply:
                    created = meet.remote.create(meet.tables['users'], fields, str(uuid.uuid4()))
                    meet.store.put('fixture_users', meet.store.get('fixture_users', []) + [r['record_id'] for r in created])
                print(json.dumps({'created' if args.apply else 'preview': fields}, ensure_ascii=False))
            else:
                owned = set(meet.store.get('fixture_users', []))
                users = meet.read('users')
                targets = [u for u in users if u['record_id'] in owned or (args.all_test_users and flag(u['fields'].get('测试')))]
                ids = {u['record_id'] for u in targets}
                # Results are immutable service evidence, not deleted as a side effect of attendee cleanup.
                scores = meet.read('scores', ['关联用户'])
                if any(ids.intersection(links(r['fields'].get('关联用户'))) for r in scores):
                    raise ValueError('Target users have imported results; preserve their identity and exclude from competition instead')
                prep = [r for r in meet.read('preparation') if ids.intersection(links(r['fields'].get('关联用户')))]
                if args.apply and ids:
                    path = ROOT / 'volumes/control' / ('fixture-delete-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '.json')
                    path.write_text(json.dumps({'users': targets, 'preparation': prep}, ensure_ascii=False, indent=2))
                    delete_records(meet.remote, meet.tables['preparation'], [r['record_id'] for r in prep])
                    delete_records(meet.remote, meet.tables['users'], sorted(ids))
                    meet.store.put('fixture_users', sorted(owned - ids))
                    meet.store.put('batch', None)
                print(json.dumps({'deleted' if args.apply else 'preview': sorted(ids), 'preparation': len(prep)}, ensure_ascii=False))
        finally:
            meet.close()


if __name__ == '__main__':
    main()
