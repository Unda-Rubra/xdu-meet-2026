"""App-identity Base client. SDK owns token caching; all writes are serialized by the caller."""
from __future__ import annotations

import json
from pathlib import Path
import random
import stat
import time
from urllib.parse import quote

from .model import canonical_hash


class FeishuError(RuntimeError):
    pass


def text(value):
    if value is None:
        return ''
    if isinstance(value, list):
        return ''.join(str(v.get('text', '')) if isinstance(v, dict) else str(v) for v in value)
    return str(value)


def links(value):
    if not value:
        return []
    if isinstance(value, dict):
        return value.get('link_record_ids', value.get('record_ids', []))
    result = []
    for item in value:
        if isinstance(item, str):
            result.append(item)
        elif 'record_ids' in item:
            result.extend(item['record_ids'])
        elif 'id' in item:
            result.append(item['id'])
        else:
            raise ValueError('Unknown linked-record response shape')
    return result


def flag(value):
    if value in (None, '', False, 0):
        return False
    if value in (True, 1):
        return True
    raise ValueError('Expected a stored checkbox, not a computed string')


def equivalent(actual, desired):
    if isinstance(desired, str):
        return text(actual) == desired
    if desired is None:
        return actual in (None, '', [])
    if isinstance(desired, list) and all(isinstance(v, str) and v.startswith('rec') for v in desired):
        return set(links(actual)) == set(desired)
    return actual == desired


class Feishu:
    def __init__(self, credentials: Path, base_token: str):
        import lark_oapi as lark
        from lark_oapi.core.model import BaseRequest
        if not credentials.is_file():
            raise ValueError(f'Missing credentials file: {credentials}. Supply app_id and app_secret; never a user token.')
        if credentials.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise ValueError(f'Credentials must be owner-only: chmod 600 {credentials}')
        auth = json.loads(credentials.read_text())
        if not isinstance(auth.get('app_id'), str) or not auth['app_id'].startswith('cli_') or not auth.get('app_secret'):
            raise ValueError('Credentials require a Feishu custom app_id and app_secret')
        self.app_id = auth['app_id']
        self._secret = auth['app_secret']
        self.lark = lark
        self.request_type = BaseRequest
        self.client = (lark.Client.builder().app_id(self.app_id).app_secret(self._secret)
                       .timeout(20).log_level(lark.LogLevel.ERROR).build())
        self.root = '/open-apis/bitable/v1/apps/' + quote(base_token, safe='')

    def request(self, method, path, body=None, query=None, *, retry=True):
        request = (self.request_type.builder().http_method(getattr(self.lark.HttpMethod, method))
                   .uri(self.root + path).token_types({self.lark.AccessTokenType.TENANT})
                   .queries([(k, str(v)) for k, v in (query or {}).items()]).body(body).build())
        for attempt in range(5):
            try:
                response = self.client.request(request)
                payload = json.loads(response.raw.content)
                status = response.raw.status_code
            except Exception as error:
                if retry and attempt < 4:
                    time.sleep(min(8, 2 ** attempt) + random.random() / 4)
                    continue
                raise FeishuError('Feishu transport error: ' + str(error).replace(self._secret, '[redacted]')) from None
            code = payload.get('code')
            if status == 200 and code == 0:
                return payload.get('data', {})
            if retry and attempt < 4 and (status == 429 or status >= 500 or code in (1254290, 1254291, 1254607)):
                time.sleep(min(16, 2 ** attempt) + random.random() / 4)
                continue
            message = str(payload.get('msg', 'unknown error')).replace(self._secret, '[redacted]')
            raise FeishuError(f'Feishu HTTP {status}, code {code}: {message}')
        raise AssertionError('Unreachable retry state')

    def tables(self):
        return self._pages('/tables')

    def fields(self, table):
        return self._pages('/tables/' + table + '/fields')

    def update_field(self, table, field, *, formula=None, description=None):
        """Preserve supported formatting; refuse UI-only metadata before writing."""
        if field['type'] not in (1, 2, 7, 20):
            raise FeishuError('Update this linked/option field in the Base UI: ' + field['field_name'])
        property = dict(field.get('property') or {})
        result_type = property.get('type') or {}
        supported_ui = {None, 'Number', 'Progress', 'Currency', 'Rating', 'DateTime'}
        supported_properties = {'currency_code', 'formatter', 'range_customize', 'min', 'max', 'date_formatter', 'rating'}
        if (result_type.get('ui_type') not in supported_ui
                or set(result_type.get('ui_property') or {}) - supported_properties):
            raise FeishuError('OpenAPI cannot preserve this formula display format; update it in the Base UI: '
                              + field['field_name'])
        if formula is not None:
            if field['type'] != 20:
                raise FeishuError('Refusing to convert an existing field to a formula: ' + field['field_name'])
            property['formula_expression'] = formula
        if description is None:
            description = field.get('description') or ''
        if isinstance(description, str):
            description = {'text': description, 'disable_sync': True}
        body = {'field_name': field['field_name'], 'type': field['type'],
                'property': property, 'description': description}
        if field.get('ui_type'):
            body['ui_type'] = field['ui_type']
        return self.request('PUT', f"/tables/{table}/fields/{field['field_id']}", body)

    def _pages(self, path):
        result, token, seen = [], None, set()
        while True:
            page = self.request('GET', path, query={'page_size': 100, **({'page_token': token} if token else {})})
            result.extend(page.get('items', []))
            if not page.get('has_more'):
                return result
            token = page.get('page_token')
            if not token or token in seen:
                raise FeishuError('Invalid pagination cursor')
            seen.add(token)

    def records(self, table, fields=None):
        result, token, seen = [], None, set()
        while True:
            page = self.request('POST', '/tables/' + table + '/records/search',
                                {'field_names': fields} if fields else {},
                                {'page_size': 500, **({'page_token': token} if token else {})})
            result.extend(page.get('items', []))
            if not page.get('has_more'):
                return result
            token = page.get('page_token')
            if not token or token in seen:
                raise FeishuError('Invalid record pagination cursor')
            seen.add(token)

    def update(self, table, records):
        for offset in range(0, len(records), 500):
            batch = records[offset:offset + 500]
            data = self.request('POST', '/tables/' + table + '/records/batch_update', {'records': batch})
            returned = {r['record_id'] for r in data.get('records', [])}
            if returned != {r['record_id'] for r in batch}:
                raise FeishuError('Partial batch update response; operation is resumable')

    def create(self, table, fields, token):
        data = self.request('POST', '/tables/' + table + '/records/batch_create',
                            {'records': [{'fields': f} for f in fields]}, {'client_token': token})
        result = data.get('records', [])
        if len(result) != len(fields):
            raise FeishuError('Partial batch create response; reconcile before retry')
        return result

    def ensure_table(self, name, fields):
        matches = [t for t in self.tables() if t['name'] == name]
        if len(matches) > 1:
            raise FeishuError('Ambiguous table name: ' + name)
        if matches:
            table = matches[0]['table_id']
        else:
            # No blind retry: a timed-out table creation must be reconciled by name.
            data = self.request('POST', '/tables', {'table': {'name': name, 'fields': fields}}, retry=False)
            table = data['table_id']
        self.ensure_fields(table, fields)
        return table

    def ensure_fields(self, table, fields):
        actual = {f['field_name']: f for f in self.fields(table)}
        for field in fields:
            name = field['field_name']
            if name in actual:
                if actual[name]['type'] != field['type']:
                    raise FeishuError('Existing field has incompatible type: ' + name)
            else:
                self.request('POST', '/tables/' + table + '/fields', field, retry=False)

    def upsert(self, table, rows, store, key_field='导入键'):
        existing = {}
        for row in self.records(table):
            key = text(row['fields'].get(key_field))
            if key:
                if key in existing:
                    raise FeishuError('Duplicate import identity in remote table: ' + key)
                existing[key] = row
        updates, creates = [], []
        for fields in rows:
            key = fields[key_field]
            row = existing.get(key)
            if row:
                # Only owned fields are patched; unrelated operator columns are retained.
                if any(not equivalent(row['fields'].get(k), v) for k, v in fields.items()):
                    updates.append({'record_id': row['record_id'], 'fields': fields})
            else:
                creates.append(fields)
        self.update(table, updates)
        for offset in range(0, len(creates), 200):
            batch = creates[offset:offset + 200]
            identity = table + ':' + canonical_hash(batch)
            self.create(table, batch, store.token(identity))
        return {'created': len(creates), 'updated': len(updates)}
