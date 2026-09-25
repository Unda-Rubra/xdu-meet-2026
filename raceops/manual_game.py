"""Ad-hoc GP control: one main lobby, live occupants, native settings, no Feishu access."""
import json
import re
import secrets
import time
import uuid
from .assets import ROOT
from .cli import exclusive
from .model import canonical_hash
from .qq_identity import load_identities, connected, policy, save_policy
from .routing import proxy_command
from .snbt import dumps, response_value
from .transport import Backend

W = '@e[type=armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1]'
SERVERS = ['race-a', 'race-b', 'race-c']


def scoreboard(backend, selector):
    raw = backend.command('execute as ' + selector + ' run scoreboard players list @s')
    return {k: int(v) for k, v in re.findall(r'\[([^\]]+)\]: (-?\d+)', raw)}


def saved_setting_bank(backend):
    layers = []
    for y in range(70, 81):
        backend.command(f'function xdu_race:capture_bank {{y:{y}}}')
        cells = backend.read('blocks', 'xdu_race:settings')
        if len(cells) != 380:
            raise ValueError('Unrecognized native saved-setting cell; refusing partial transfer')
        layers.append(cells)
    return layers


def settings():
    lobby = Backend('lobby')
    lobby.command('function xdu_race:capture_settings')
    value = lobby.read('blocks', 'xdu_race:settings')
    if len(value) != 300:
        raise ValueError('Unrecognized GP sequence block; do not start with a partial configuration')
    scores = scoreboard(lobby, W)
    count = scores.get('gpNumber', 0)
    if not 1 <= count <= 50:
        raise ValueError('Configure a Grand Prix sequence in the main lobby before starting')
    contract = json.loads((ROOT / 'config/native-settings.json').read_text())
    tags = response_value(lobby.command('data get entity ' + W + ' Tags'))
    # Event boundary wins over native endless/repeat: every GP ends after its award ceremony.
    if 'endlessMode' in tags or 'grandprixloop' in tags:
        raise ValueError('Disable endless/GP-loop in the main lobby: the event must end with its ceremony')
    extras = []
    for entity in contract['entities']:
        selector = entity['selector']
        all_scores = scoreboard(lobby, selector)
        all_tags = response_value(lobby.command('data get entity ' + selector + ' Tags'))
        extras.append({'selector': selector, 'scores': {k: all_scores[k] for k in entity['scores'] if k in all_scores},
                       'tags': [t for t in all_tags if t in entity['tags']]})
    holders = []
    for holder in contract['holders']:
        raw = lobby.command(f'scoreboard players get {holder["name"]} {holder["objective"]}')
        value_match = re.search(r' has (-?\d+) ', raw)
        if not value_match:
            raise ValueError('Missing native saved setting: ' + holder['name'])
        holders.append({**holder, 'value': int(value_match[1])})
    return {'blocks': value, 'tracks': lobby.read('tracks', 'xdu_race:settings'), 'entities': extras, 'holders': holders,
            'saved_bank': saved_setting_bank(lobby), 'round_sequence': lobby.read('', 'sprint_racer:round_sequence'),
            'scores': {k: scores[k] for k in contract['scores'] if k in scores},
            'tags': [t for t in tags if t in contract['tags']], 'track_count': count}


def apply_settings(backend, value):
    contract = json.loads((ROOT / 'config/native-settings.json').read_text())
    for layer in value['saved_bank']:
        backend.commands([f'setblock {b["x"]} {b["y"]} {b["z"]} {b["block"]}' for b in layer])
    if saved_setting_bank(backend) != value['saved_bank']:
        raise ValueError('Native saved preset transfer failed readback')
    backend.stage('round_sequence', value['round_sequence'])
    old_sequence = backend.read('', 'sprint_racer:round_sequence')
    sequence_commands = [f'data remove storage sprint_racer:round_sequence {dumps(k)}' for k in old_sequence]
    sequence_commands += [f'data modify storage sprint_racer:round_sequence {dumps(k)} set from storage xdu_race:request round_sequence.{dumps(k)}'
                          for k in value['round_sequence']]
    if sequence_commands:
        backend.commands(sequence_commands)
    commands = [f'tag {W} remove {tag}' for tag in contract['tags']]
    commands += [f'tag {W} add {tag}' for tag in value['tags']]
    commands += [f'scoreboard players set {W} {k} {v}' for k, v in value['scores'].items()]
    commands += [f'setblock {b["x"]} {b["y"]} {b["z"]} {b["block"]}' for b in value['blocks']]
    for entity, saved in zip(contract['entities'], value['entities'], strict=True):
        selector = entity['selector']
        commands += [f'tag {selector} {"add" if t in saved["tags"] else "remove"} {t}' for t in entity['tags']]
        commands += [f'scoreboard players set {selector} {k} {v}' for k, v in saved['scores'].items()]
    commands += [f'scoreboard players set {h["name"]} {h["objective"]} {h["value"]}' for h in value['holders']]
    for row in value['tracks']:
        kind = 'trackStandR' if 'trackStandR' in row['tags'] else 'trackStandB'
        selector = f'@e[type=armor_stand,tag={kind},scores={{rNumber={row["id"]}}}]'
        for tag in ['rtBlacklist', 'btBlacklist', *[f'gpNo{i}' for i in range(1, 51)]]:
            commands.append(f'tag {selector} {"add" if tag in row["tags"] else "remove"} {tag}')
    for offset in range(0, len(commands), 2000):
        backend.commands(commands[offset:offset + 2000])
    backend.command('function xdu_race:capture_settings')
    if backend.read('blocks', 'xdu_race:settings') != value['blocks']:
        raise ValueError('GP sequence transfer failed')
    actual = scoreboard(backend, W)
    if any(actual.get(k) != v for k, v in value['scores'].items()):
        raise ValueError('Native settings transfer failed')


def sync_admins():
    admission = policy()
    lobby = Backend('lobby')
    lobby.commands(['data modify storage xdu_race:scratch admins set value []',
                    'execute as @a[tag=xdu_admin] run function xdu_race:capture_admin'])
    if not admission.get('active'):
        for tagged in lobby.read('admins', 'xdu_race:scratch'):
            uid = str(uuid.UUID(int=sum((int(n) & 0xffffffff) << (96 - 32 * i) for i, n in enumerate(tagged['uuid']))))
            groups = [g for g in 'ABC' if 'xdu_commentary_' + g in tagged['tags']]
            if len(groups) > 1:
                raise ValueError('Administrator has multiple default commentary tags')
            admission['admins'][uid] = groups[0] if groups else admission['admins'].get(uid, 'A')
        save_policy(admission)
    admins = admission['admins']
    people = connected()
    for server in ['lobby', *SERVERS]:
        commands = []
        for uid, p in people.items():
            if p['server'] != server or not re.fullmatch(r'[A-Za-z0-9_]{1,16}', p['name']):
                continue
            target = '@a[name=' + p['name'] + ']'
            commands.append(f'tag {target} {"add" if uid in admins else "remove"} xdu_admin')
            if uid in admins:
                for group in 'ABC':
                    commands.append(f'tag {target} {"add" if admins[uid]==group else "remove"} xdu_commentary_{group}')
                if server != 'lobby':
                    commands += [f'tag {target} add forcespectate', f'tag {target} remove playing', f'gamemode spectator {target}']
        if commands:
            Backend(server).commands(commands)


def admin(name, group):
    people = connected()
    found = [uid for uid, p in people.items() if p['name'] == name]
    if len(found) != 1:
        raise ValueError('Administrator must be an explicitly verified connected player')
    value = policy()
    if value.get('active'):
        raise ValueError('Change administrator roles only between GPs')
    if group == 'revoke':
        value['admins'].pop(found[0], None)
        Backend(people[found[0]]['server']).command('tag @a[name=' + name + '] remove xdu_admin')
    else:
        value['admins'][found[0]] = group
        target = '@a[name=' + name + ']'
        Backend(people[found[0]]['server']).commands([f'tag {target} add xdu_admin', *[
            f'tag {target} {"add" if g==group else "remove"} xdu_commentary_{g}' for g in 'ABC']])
    save_policy(value)
    sync_admins()
    return {'administrator': name, 'default_group': group}


def start():
    with exclusive():
        sync_admins()
        admission = policy()
        if admission.get('active'):
            raise ValueError('Previous GP is still active; let its ceremony and archive complete')
        states = {s: Backend(s).read() for s in SERVERS}
        if any(s['state'] not in ('IDLE', 'GP_FINISHED') for s in states.values()):
            raise ValueError('A backend is not idle or has an unresolved interrupted GP')
        people, identities = connected(), load_identities()
        entrants = []
        for uid, p in people.items():
            if uid in admission['admins']:
                continue
            if p['server'] != 'lobby' or uid not in identities:
                raise ValueError('All non-admin players must be registered and waiting in the main lobby')
            entrants.append({'uuid': uid, 'name': p['name'], 'qq': identities[uid]['qq']})
        if not 2 <= len(entrants) <= 51:
            raise ValueError('A GP requires 2–51 registered non-admin players')
        settings_value = settings()
        secrets.SystemRandom().shuffle(entrants)
        count = 2 if len(entrants) <= 20 else 3
        groups = {g: entrants[i::count] for i, g in enumerate('ABC'[:count])}
        attempt = 'gp_' + uuid.uuid4().hex
        setting_hash = canonical_hash(settings_value)
        roster_hash = canonical_hash(groups)
        settings_path = ROOT / 'volumes/control/attempts' / (attempt + '.json')
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings_value, ensure_ascii=False, indent=2))
        for group, roster in groups.items():
            backend = Backend('race-' + group.lower())
            apply_settings(backend, settings_value)
            plan = {'schema_version': 2, 'adapter_version': '2.0.0', 'event_id': 'xdu-2026-fall',
                    'attempt_id': attempt, 'group': group, 'server': backend.service, 'active_groups': list(groups),
                    'grand_prix_round': 0, 'state': 'PREPARED', 'frozen': False, 'track_index': 0,
                    'track_count': settings_value['track_count'], 'revision': 1, 'boot_id': states[backend.service]['boot_id'],
                    'settings_hash': setting_hash, 'preset_hash': setting_hash, 'roster_hash': roster_hash,
                    'identity_mode': 'offline_trusted_private', 'roster': roster,
                    'results': {}, 'template_hash': 'native-1.6.13-manual-v2'}
            backend.stage('plan', plan)
            backend.command('data modify storage xdu_race:state current set from storage xdu_race:request plan')
            backend.command('tag @a remove xdu_member')
        admission.update(active=True, attempt=attempt, servers=['race-' + g.lower() for g in groups],
                         members={p['uuid']: 'race-' + g.lower() for g, roster in groups.items() for p in roster})
        save_policy(admission)
        for uid, server in admission['members'].items():
            proxy_command('send ' + people[uid]['name'] + ' ' + server)
        for uid, group in admission['admins'].items():
            if uid in people:
                target = 'race-' + group.lower()
                if target not in admission['servers']:
                    target = admission['servers'][0]
                proxy_command('send ' + people[uid]['name'] + ' ' + target)
        deadline = time.monotonic() + 90
        while any(connected().get(uid, {}).get('server') != target for uid, target in admission['members'].items()):
            if time.monotonic() > deadline:
                raise ValueError('Routing incomplete; no start sent. Inspect the prepared attempt before retry')
            time.sleep(.5)
        for group, roster in groups.items():
            backend = Backend('race-' + group.lower())
            while any('Test passed' not in result for result in backend.commands([
                    'execute if entity @a[name=' + p['name'] + ']' for p in roster])):
                if time.monotonic() > deadline:
                    raise ValueError('Backend admission/resource-pack loading incomplete; no start sent. Abort before retrying')
                time.sleep(.5)
        sync_admins()
        for group, roster in groups.items():
            backend = Backend('race-' + group.lower())
            commands = []
            for p in roster:
                target = '@a[name=' + p['name'] + ']'
                commands += [f'tag {target} add xdu_member', f'tag {target} remove forcespectate',
                             f'tag {target} remove afk', f'tag {target} add playing', f'gamemode adventure {target}']
            backend.commands(commands)
        for group in groups:
            backend = Backend('race-' + group.lower())
            backend.command('function xdu_race:start')
            if backend.read()['state'] != 'RUNNING' or scoreboard(backend, W).get('gameState') not in (1, 3, 7, 8):
                raise ValueError('Start was not acknowledged; inspect every backend, do not blindly restart')
        return {'attempt': attempt, 'groups': {g: len(v) for g, v in groups.items()}, 'settings_hash': setting_hash}


def abort(reason):
    from .exporter import export
    with exclusive():
        admission = policy()
        if not admission.get('active'):
            raise ValueError('No active GP')
        archive, _ = export([Backend(s) for s in admission['servers']])
        for p in connected().values():
            if p['server'] in admission['servers']:
                proxy_command('send ' + p['name'] + ' lobby')
        deadline = time.monotonic() + 30
        while any(p['server'] in admission['servers'] for p in connected().values()):
            if time.monotonic() > deadline:
                raise ValueError('Return to main lobby incomplete; abort retained for recovery')
            time.sleep(.5)
        for server in admission['servers']:
            backend = Backend(server)
            backend.commands(['schedule clear xdu_race:release_track',
                              'data modify storage xdu_race:state current.state set value "ABORTED"',
                              f'tag {W} remove grandprix',
                              f'execute as {W} at @s run function sprint_racer:game_logic/0/_initialize',
                              'data modify storage xdu_race:state current.state set value "IDLE"'])
        admission.update(active=False, members={}, servers=[])
        admission.pop('release_track', None)
        save_policy(admission)
        from .cli import audit
        audit({'command': 'abort', 'attempt': admission['attempt'], 'reason': reason, 'archive': str(archive)})
        return {'aborted': admission['attempt'], 'archive': str(archive), 'upload_token': None}
