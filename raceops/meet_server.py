"""Loopback-only service. One writer/event loop owns SQLite and Feishu operations."""
from __future__ import annotations

import argparse
import fcntl
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import sys
import time

from .assets import ROOT
from .meet import Meet, load_config
from .meet_results import Results


def admin_token(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(secrets.token_urlsafe(40) + '\n')
    if path.stat().st_mode & 0o077:
        raise ValueError('Admin token file must have permissions 0600')
    token = path.read_text().strip()
    if len(token) < 32:
        raise ValueError('Admin token is too short')
    return token


def handler_for(meet, token):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'XduMeet/1'

        def log_message(self, fmt, *args):
            # Do not log query strings, request bodies, credentials or player identities.
            return

        def respond(self, status, body):
            content = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)

        def authorized(self):
            if self.headers.get('Origin'):
                self.respond(403, {'error': 'Browser-origin requests are not accepted'})
                return False
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                self.respond(401, {'error': 'Bearer authentication required'})
                return False
            return True

        def do_GET(self):
            if self.path == '/health':
                self.respond(200, {'ok': True, 'active': meet.store.get('migrated', False)})
                return
            if not self.authorized():
                return
            if self.path == '/status':
                self.respond(200, {'operation': meet.store.active(), 'history': meet.store.history(),
                                   'batch': meet.store.get('batch'), 'last_import': meet.store.get('last_import'),
                                   'last_error': meet.store.get('last_error'),
                                   'sync_error': meet.store.get('sync_error'),
                                   'results_error': meet.store.get('results_error')})
            else:
                self.respond(404, {'error': 'Unknown endpoint'})

        def do_POST(self):
            if not self.authorized():
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if self.headers.get('Transfer-Encoding') or not 0 <= size <= 16384:
                    self.respond(413, {'error': 'Request exceeds 16 KiB or uses unsupported transfer encoding'})
                    return
                self.connection.settimeout(10)
                body = json.loads(self.rfile.read(size) or b'{}')
                if not isinstance(body, dict):
                    raise ValueError('JSON object required')
                actions = {'/group': meet.group, '/clear': meet.clear,
                           '/resume': meet.resume, '/import-results': Results(meet).sync}
                if self.path in actions:
                    if body:
                        raise ValueError('This endpoint takes no parameters')
                    result = actions[self.path]()
                elif self.path == '/roster':
                    result = meet.roster(body['round'])
                elif self.path == '/game':
                    result = meet.game_command(**body)
                else:
                    self.respond(404, {'error': 'Unknown endpoint'})
                    return
                self.respond(200, result)
            except (ValueError, KeyError, TypeError) as error:
                self.respond(400, {'error': str(error)})
            except Exception as error:
                meet.store.put('last_error', {'at': time.time(), 'error': str(error)})
                self.respond(503, {'error': str(error), 'resumable': bool(meet.store.active())})
    return Handler


def serve(meet):
    if not meet.store.get('round_upload_ready'):
        raise ValueError('Run the round-upload migration before serving')
    config = meet.config
    token = admin_token(config['admin_token_file'])
    server = HTTPServer((config['listen'], config['port']), handler_for(meet, token))
    server.timeout = 1
    running = True

    def stop(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    next_results = 0
    print(f"Meet service ready on http://{config['listen']}:{config['port']}; credentials never printed", flush=True)
    try:
        while running:
            server.handle_request()
            now = time.monotonic()
            if now < next_results:
                continue
            try:
                Results(meet).sync()
                meet.store.put('results_ok_at', time.time())
                meet.store.put('results_error', None)
            except Exception as error:
                meet.store.put('results_error', {'at': time.time(), 'error': str(error)})
                print(f'results: {error}', file=sys.stderr, flush=True)
            next_results = time.monotonic() + config['results_interval']
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/feishu.json')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('setup-app', 'doctor', 'migrate', 'serve', 'group', 'clear', 'resume'):
        sub.add_parser(command)
    imp = sub.add_parser('import-results')
    imp.add_argument('--archives-only', action='store_true')
    upload = sub.add_parser('upload-attempt')
    upload.add_argument('--attempt', required=True)
    upload.add_argument('--round', type=int, required=True)
    roster = sub.add_parser('roster')
    roster.add_argument('--round', type=int, required=True)
    game = sub.add_parser('game')
    game.add_argument('action', choices=['status', 'preset', 'route', 'start', 'stop', 'export', 'reset', 'lobby'])
    game.add_argument('--round', type=int)
    game.add_argument('--preset')
    game.add_argument('--reason')
    game.add_argument('--archive')
    args = parser.parse_args()
    meet = None
    try:
        config = load_config(args.config)
        if args.command == 'setup-app':
            from .meet_auth import register
            register(config)
            return 0
        lock_path = Path(config['database']).with_suffix('.lock')
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('Meet service already owns the database; use the authenticated HTTP API') from None
            meet = Meet(config)
            if args.command == 'serve':
                serve(meet)
                return 0
            if args.command == 'doctor':
                result = meet.doctor()
            elif args.command == 'migrate':
                result = meet.ensure_schema()
                meet.store.put('prepared', True)
            elif args.command == 'roster':
                result = meet.roster(args.round)
            elif args.command == 'game':
                result = meet.game_command(args.action, args.round, args.preset, args.reason, args.archive)
            elif args.command == 'import-results':
                result = Results(meet).sync(capture=not args.archives_only)
            elif args.command == 'upload-attempt':
                result = Results(meet).upload_attempt(args.attempt, args.round)
            else:
                result = getattr(meet, args.command)()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
    except Exception as error:
        print(f'meet-service: {error}', file=sys.stderr)
        return 1
    finally:
        if meet:
            meet.close()


if __name__ == '__main__':
    raise SystemExit(main())
