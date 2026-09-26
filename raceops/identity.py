"""Vanilla backend UUID for a name; the proxy's authenticated UUID is separate."""
import hashlib
import re
import uuid

NAME = re.compile(r'[A-Za-z0-9_]{1,16}\Z')


def offline_uuid(name):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError('Player names must contain 1–16 ASCII letters, digits or underscores')
    return str(uuid.UUID(bytes=hashlib.md5(('OfflinePlayer:' + name).encode('utf-8')).digest(), version=3))
