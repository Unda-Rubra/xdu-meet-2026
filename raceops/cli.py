"""Host-only ad-hoc game controls; no preassigned rounds or schedules."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
import time
from .assets import ROOT
from .transport import Backend


@contextmanager
def exclusive():
    directory = ROOT / 'exports'
    directory.mkdir(exist_ok=True)
    with (directory / '.racectl.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def audit(record):
    path = ROOT / 'volumes/control/operations.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        stream.write(json.dumps({'at': time.time(), **record}) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('start')
    sub.add_parser('status')
    stop = sub.add_parser('abort')
    stop.add_argument('--reason', required=True)
    admin = sub.add_parser('admin')
    admin.add_argument('name')
    admin.add_argument('group', choices=['A', 'B', 'C', 'revoke'])
    args = parser.parse_args()
    try:
        from .manual_game import start, admin as set_admin, SERVERS
        if args.command == 'start':
            result = start()
        elif args.command == 'admin':
            with exclusive():
                result = set_admin(args.name, args.group)
        elif args.command == 'abort':
            from .manual_game import abort
            result = abort(args.reason)
        else:
            result = {server: {k: v for k, v in Backend(server).read().items()
                               if k in ('state', 'attempt_id', 'track_index', 'track_count', 'frozen')}
                      for server in SERVERS}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, 'racectl: ' + str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
