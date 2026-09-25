"""Explicit Feishu operations; gameplay and automatic local capture never contact Base."""
import json
from pathlib import Path
from .assets import ROOT
from .feishu import Feishu
from .meet_store import Store
from .qq_identity import validate_qq


def load_config(path=None):
    config = json.loads((path or ROOT / 'config/feishu.json').read_text())
    for key in ('credentials_file', 'database'):
        config[key] = str((ROOT / config[key]).resolve())
    return config


def row_patch(record_id, **fields):
    return {'record_id': record_id, 'fields': fields}


class Meet:
    def __init__(self, config, remote=None):
        self.config = config
        self.store = Store(Path(config['database']))
        self.remote = remote or Feishu(Path(config['credentials_file']), config['base_token'])
        self.tables = config['tables']

    def close(self):
        self.store.close()

    def read(self, table, fields=None):
        return self.remote.records(self.tables[table], fields)

    def update(self, table, patches):
        if patches:
            self.remote.update(self.tables[table], patches)

    def control(self):
        rows = self.read('control')
        if len(rows) != 1:
            raise ValueError('Exactly one upload-control record is required')
        return rows[0]

    def users_by_qq(self):
        result = {}
        for row in self.read('users', ['QQ号']):
            value = row['fields'].get('QQ号')
            if value in (None, '', []):
                continue
            if isinstance(value, list):
                value = ''.join(v.get('text', '') for v in value)
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            qq = validate_qq(value)
            if qq in result:
                raise ValueError('Duplicate signup QQ; resolve signup records before upload')
            result[qq] = row
        return result

    def doctor(self):
        return {'tables': len(self.tables), 'signup_users': len(self.users_by_qq()),
                'pending_uploads': len(self.store.uploads('pending')), 'mode': 'manual-token-upload'}

    def ensure_schema(self):
        from .meet_migration import migrate
        return migrate(self)
