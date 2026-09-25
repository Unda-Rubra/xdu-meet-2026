"""Local capture daemon and explicit token upload CLI; no background Feishu traffic."""
import argparse
import fcntl
import json
from pathlib import Path
import signal
import time
from .assets import ROOT, digest
from .exporter import export
from .meet import Meet, load_config
from .meet_store import Store
from .manual_game import start, admin, sync_admins, SERVERS
from .qq_identity import policy, save_policy, connected, DIRECTORY
from .routing import proxy_command
from .transport import Backend
from .cli import exclusive

def advance_barrier(admission, states):
    if any(s['attempt_id'] != admission['attempt'] for s in states.values()):
        raise ValueError('Active backend attempt differs from the coordinated GP')
    release = admission.get('release_track')
    if release is None:
        if not all(s['state'] == 'WAITING' for s in states.values()):
            return
        indices = {s['track_index'] for s in states.values()}
        if len(indices) != 1:
            raise ValueError('Backends reached different track barriers; not advancing')
        release = indices.pop()
        admission['release_track'] = release
        save_policy(admission)
    # This release decision survives restarts; each native function accepts it once.
    for server, state in states.items():
        if state['state'] == 'WAITING' and state['track_index'] == release:
            Backend(server).command('function xdu_race:arm_release')
    updated = {server: Backend(server).read() for server in states}
    if all(s['state'] in ('CEREMONY', 'GP_FINISHED') or s['track_index'] > release for s in updated.values()):
        admission.pop('release_track', None)
        save_policy(admission)
    states.update(updated)


def process_start_request(store):
    path = DIRECTORY / 'start-request.json'
    if not path.exists():
        return
    request = json.loads(path.read_text())
    if store.get('last_start_request') == request['request_id']:
        return
    store.put('last_start_request', request['request_id'])
    uid = request['requested_by']
    if not 0 <= time.time() * 1000 - request['at'] <= 30000 or uid not in policy()['admins']:
        return
    player = connected().get(uid)
    if not player or player['server'] != 'lobby':
        return
    try:
        result = start()
        print(json.dumps({'explicit_start': result}), flush=True)
    except Exception as error:
        Backend('lobby').command('tellraw @a[tag=xdu_admin] ' + json.dumps({'text': '开赛未完成：' + str(error)}, ensure_ascii=False))
        raise


def capture(store):
    process_start_request(store)
    with exclusive():
        return capture_locked(store)


def capture_locked(store):
    admission = policy()
    sync_admins()
    if not admission.get('active'):
        return []
    states = {s: Backend(s).read() for s in admission['servers']}
    advance_barrier(admission, states)
    # Each group's ceremony ends independently. Return its players immediately afterwards.
    people = connected()
    for server, state in states.items():
        if state['state'] == 'GP_FINISHED' and state.get('frozen'):
            for p in people.values():
                if p['server'] == server:
                    proxy_command('send ' + p['name'] + ' lobby')
    if any(s['state'] != 'GP_FINISHED' or not s.get('frozen') for s in states.values()):
        return []
    attempt = admission['attempt']
    previous = next((r for r in store.receipts() if r['attempt'] == attempt), None)
    if previous is None:
        archive, manifest = export([Backend(s) for s in admission['servers']], attempt_id=attempt)
        if not manifest['complete'] or not manifest['coherent_attempt']:
            raise ValueError('Final archive is incomplete; no token issued')
        previous = store.register(attempt, archive, digest(archive / 'manifest.json'))
    admission.update(active=False, members={}, servers=[])
    save_policy(admission)
    Backend('lobby').command('tellraw @a[tag=xdu_admin] ' + json.dumps({
        'text': 'GP已颁奖并留档。手动上传 token：' + previous['token'],
        'click_event': {'action': 'copy_to_clipboard', 'value': previous['token']}}, ensure_ascii=False))
    return [previous]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('serve', 'capture', 'tokens', 'start', 'doctor', 'migrate', 'setup-app'):
        sub.add_parser(name)
    upload = sub.add_parser('upload')
    upload.add_argument('--token', required=True)
    role = sub.add_parser('admin')
    role.add_argument('name')
    role.add_argument('group', choices=['A', 'B', 'C', 'revoke'])
    args = parser.parse_args()
    config = load_config(args.config)
    try:
        if args.command == 'setup-app':
            from .meet_auth import register
            register(config)
            return 0
        if args.command in ('upload', 'doctor', 'migrate'):
            with Path(config['database']).with_suffix('.upload.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                meet = Meet(config)
                try:
                    if args.command == 'upload':
                        from .meet_results import Results
                        result = Results(meet).upload(args.token)
                    elif args.command == 'migrate':
                        result = meet.ensure_schema()
                    else:
                        result = meet.doctor()
                finally:
                    meet.close()
        elif args.command == 'start':
            result = start()
        elif args.command == 'admin':
            with exclusive():
                result = admin(args.name, args.group)
        else:
            store = Store(Path(config['database']))
            try:
                if args.command == 'tokens':
                    result = store.receipts()
                elif args.command == 'capture':
                    result = capture(store)
                else:
                    with Path(config['database']).with_suffix('.capture.lock').open('a') as lock:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        running = True
                        def stop(*_):
                            nonlocal running
                            running = False
                        signal.signal(signal.SIGTERM, stop)
                        signal.signal(signal.SIGINT, stop)
                        print('Local GP capture ready; Feishu updates require upload --token', flush=True)
                        while running:
                            try:
                                for receipt in capture(store):
                                    print(json.dumps({'result_token': receipt['token'], 'archive': receipt['archive']}, ensure_ascii=False), flush=True)
                            except Exception as error:
                                print('capture: ' + str(error), flush=True)
                            time.sleep(2)
                    return 0
            finally:
                store.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, 'meet-service: ' + str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
