"""Physical deployment configuration; each GP derives its own live group roster."""
import json
from .assets import ROOT


def validate_event(event):
    if event.get('identity_mode') != 'offline_trusted_private':
        raise ValueError('This deployment requires private supervised offline identity')
    if event.get('backend_admission') != 'proxy_only_private_network':
        raise ValueError('Backends must not be publicly reachable')
    return event


def load_event():
    return validate_event(json.loads((ROOT / 'config/event.yaml').read_text()))
