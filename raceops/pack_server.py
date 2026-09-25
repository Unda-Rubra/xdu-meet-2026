"""Serve the pinned native resource pack to event clients, without an external redirect."""
import argparse
import ipaddress
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil

from .assets import ROOT, digest, load_lock

PORT = 25566
SERVERS = ('lobby', 'race-a', 'race-b', 'race-c')


def bind_address():
    value = os.environ.get('EVENT_BIND')
    if not value:
        env_file = ROOT / '.env'
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith('EVENT_BIND='):
                    value = line.partition('=')[2].strip()
                    break
    address = ipaddress.IPv4Address(value or '127.0.0.1')
    if not (address.is_private or address.is_loopback) or address.is_unspecified:
        raise ValueError('The event resource pack may only bind to a private LAN address')
    return str(address)


def resource_pack_url():
    return f'http://{bind_address()}:{PORT}/pack.zip'


def configure_worlds():
    """Refresh the four server properties whenever EVENT_BIND changes."""
    expected = load_lock()['resource_pack']['sha1']
    source = ROOT / 'downloads/resources-1.6.13.zip'
    if not source.is_file() or source.is_symlink() or digest(source, 'sha1') != expected:
        raise ValueError('Locked resource pack missing or checksum mismatch')
    url = resource_pack_url().replace(':', '\\:')
    for name in SERVERS:
        path = ROOT / 'volumes/event' / name / 'server.properties'
        lines = path.read_text().splitlines()
        matches = [i for i, line in enumerate(lines) if line.startswith('resource-pack=')]
        sha_matches = [line for line in lines if line.startswith('resource-pack-sha1=')]
        if len(matches) != 1 or sha_matches != ['resource-pack-sha1=' + expected]:
            raise ValueError('Unexpected native resource pack settings in ' + name)
        lines[matches[0]] = 'resource-pack=' + url
        path.write_text('\n'.join(lines) + '\n')
    return resource_pack_url()


def serve(path: Path, lock: Path):
    expected = json.loads(lock.read_text())['resource_pack']
    if (not path.is_file() or path.is_symlink() or digest(path, 'sha1') != expected['sha1']
            or digest(path) != expected['sha256']):
        raise ValueError('Refusing to serve a resource pack that differs from the asset lock')
    size = path.stat().st_size

    class PackHandler(BaseHTTPRequestHandler):
        def respond(self, head_only=False):
            if self.path != '/pack.zip':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Length', str(size))
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            if not head_only:
                with path.open('rb') as source:
                    shutil.copyfileobj(source, self.wfile, length=128 * 1024)

        def do_GET(self):
            self.respond()

        def do_HEAD(self):
            self.respond(head_only=True)

    server = ThreadingHTTPServer(('0.0.0.0', PORT), PackHandler)
    server.daemon_threads = True
    print(f'Pinned resource pack ready on port {PORT}', flush=True)
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path)
    parser.add_argument('--lock', type=Path)
    parser.add_argument('--configure', action='store_true')
    args = parser.parse_args()
    if args.configure:
        print(configure_worlds())
    else:
        if args.file is None or args.lock is None:
            parser.error('--file and --lock are required when serving')
        serve(args.file, args.lock)


if __name__ == '__main__':
    main()
