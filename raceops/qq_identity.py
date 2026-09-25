"""QQ is a self-declared signup key; privileges are console-owned, never inferred from it."""
import json
import os
from pathlib import Path
import re
import time
import uuid
from .assets import ROOT

DIRECTORY = ROOT / 'volumes/event/proxy/plugins/XduIdentity'
QQ = re.compile(r'[1-9][0-9]{4,11}\Z')


def validate_qq(value):
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str) or not QQ.fullmatch(value):
        raise ValueError('QQ must be 5–12 decimal digits without leading zero')
    return value


def load_identities():
    raw = json.loads((DIRECTORY / 'identities.json').read_text())
    if raw.get('schema_version') != 1:
        raise ValueError('Unsupported QQ registry')
    seen = set()
    for uid, row in raw['players'].items():
        if str(uuid.UUID(uid)) != uid or validate_qq(row['qq']) in seen:
            raise ValueError('Malformed or duplicate QQ registry identity')
        seen.add(row['qq'])
    return raw['players']


def connected():
    raw = json.loads((DIRECTORY / 'online.json').read_text())
    if not 0 <= time.time() * 1000 - raw['at'] <= 10000:
        raise ValueError('Proxy identity gate is not reporting live connections')
    return raw['players']


def policy():
    path = DIRECTORY / 'admissions.json'
    return json.loads(path.read_text()) if path.exists() else {'active': False, 'admins': {}, 'members': {}, 'servers': []}


def save_policy(value):
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = DIRECTORY / 'admissions.json'
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
