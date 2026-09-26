"""Manually draw one unawarded onsite attendee from the existing Feishu Base."""
import fcntl
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from .assets import ROOT

ATTENDANCE = '参会情况'
ONSITE = '线下参会'
AWARDED = '已中奖'
AWARDED_AT = '中奖时间'
FIELDS = (ATTENDANCE, AWARDED, AWARDED_AT, '昵称', 'QQ号')
FILTER = {'logic': 'and', 'conditions': [[ATTENDANCE, '==', [ONSITE]], [AWARDED, '==', False]]}


def cli(*args):
    executable = shutil.which('lark-cli')
    if not executable:
        raise RuntimeError('Install @larksuite/cli and authorize the user identity before drawing')
    result = subprocess.run([executable, 'base', *args, '--as', 'user'],
                            text=True, capture_output=True, timeout=60, check=False)
    try:
        envelope = json.loads(result.stdout if result.returncode == 0 else result.stderr)
    except json.JSONDecodeError as error:
        raise RuntimeError('Lark CLI did not return a JSON envelope') from error
    if result.returncode or envelope.get('ok') is not True:
        reason = envelope.get('error', {}).get('message', 'Lark Base operation failed')
        raise RuntimeError(str(reason))
    return envelope['data']


def text(value):
    if isinstance(value, list):
        return ''.join(text(part) for part in value)
    if isinstance(value, dict):
        return str(value.get('text', ''))
    return '' if value is None else str(value)


def projected(response):
    if response.get('field_id_list') is None or response.get('record_id_list') is None:
        raise ValueError('Unexpected Base record response')
    columns = response['field_id_list']
    if len(columns) != len(FIELDS) or len(set(columns)) != len(FIELDS):
        raise ValueError('Unexpected lottery projection')
    if len(response['data']) != len(response['record_id_list']):
        raise ValueError('Incomplete Base record response')
    for record_id, values in zip(response['record_id_list'], response['data']):
        if len(values) != len(FIELDS):
            raise ValueError('Missing lottery field value')
        yield record_id, dict(zip(FIELDS, values))


def choose(base_token, table_id, randbelow=secrets.randbelow):
    selected = None
    count = offset = 0
    observed = set()
    timezone = None
    while True:
        response = cli('+record-list', '--base-token', base_token, '--table-id', table_id,
                       '--filter-json', json.dumps(FILTER, ensure_ascii=False),
                       *(flag for field in FIELDS for flag in ('--field-id', field)),
                       '--offset', str(offset), '--limit', '200', '--format', 'json')
        if timezone is None:
            timezone = response.get('timezone')
        elif timezone != response.get('timezone'):
            raise ValueError('Base timezone changed while drawing')
        page = list(projected(response))
        for record_id, row in page:
            if record_id in observed:
                raise ValueError('Base pagination changed while drawing; retry later')
            observed.add(record_id)
            if text(row[ATTENDANCE]) != ONSITE or row[AWARDED] not in (None, False) or row[AWARDED_AT] not in (None, ''):
                raise ValueError('Lottery candidate state changed or contains a prior award time')
            count += 1
            if randbelow(count) == 0:
                selected = record_id, row
        offset += len(page)
        if not response.get('has_more'):
            break
        if not page:
            raise ValueError('Base pagination did not advance')
    return selected, count, timezone


def draw(randbelow=secrets.randbelow):
    config = json.loads((ROOT / 'config/feishu.json').read_text())
    lock = ROOT / 'volumes/control/onsite-lottery.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        base = config['base_token']
        table = config['tables']['users']
        selected, count, timezone = choose(base, table, randbelow)
        if selected is None:
            return {'eligible': 0, 'winner': None}
        record_id, _ = selected
        current = cli('+record-get', '--base-token', base, '--table-id', table,
                      '--record-id', record_id,
                      *(flag for field in FIELDS for flag in ('--field-id', field)),
                      '--format', 'json')
        row_id, row = next(projected(current))
        if row_id != record_id or text(row[ATTENDANCE]) != ONSITE or row[AWARDED] not in (None, False) or row[AWARDED_AT] not in (None, ''):
            raise ValueError('Chosen record changed before update; no award was made')
        if timezone != 'Asia/Shanghai':
            raise ValueError('Unexpected Base timezone; no award was made')
        now = datetime.now(ZoneInfo(timezone)).strftime('%Y-%m-%d %H:%M:%S')
        cli('+record-upsert', '--base-token', base, '--table-id', table,
            '--record-id', record_id, '--json', json.dumps({AWARDED: True, AWARDED_AT: now}, ensure_ascii=False))
        deadline = time.monotonic() + 20
        while True:
            saved = cli('+record-get', '--base-token', base, '--table-id', table,
                        '--record-id', record_id,
                        *(flag for field in FIELDS for flag in ('--field-id', field)),
                        '--format', 'json')
            saved_id, state = next(projected(saved))
            if saved_id == record_id and state[AWARDED] is True and state[AWARDED_AT]:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Lottery write was not confirmed; check this record before drawing again')
            time.sleep(.5)
        qq = text(row['QQ号'])
        return {'eligible_before_draw': count, 'winner': text(row['昵称']),
                'qq_hint': ('…' + qq[-4:]) if qq else None, 'awarded_at': now}


def main():
    try:
        print(json.dumps(draw(), ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit('draw-prize: ' + str(error)) from None


if __name__ == '__main__':
    main()
