"""Stable archive identities and canonical checksums."""
import hashlib
import json
import re

IDENTIFIER = re.compile(r'[a-zA-Z0-9_-]{1,80}\Z')


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError('Identifier must use 1–80 ASCII letters, digits, underscores or hyphens')
    return value
