"""Create a dedicated Feishu app without exposing its secret or changing lark-cli accounts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import threading


def register(config):
    import lark_oapi as lark
    path = Path(config['credentials_file'])
    if path.exists():
        raise ValueError('Credentials already exist; refusing to replace a configured application')
    cancelled = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: cancelled.set())
    signal.signal(signal.SIGINT, lambda *_: cancelled.set())

    def show(info):
        print(json.dumps({'verification_url': info['url'], 'expires_in': info['expire_in']}), flush=True)
        print('APP_AUTH_READY', flush=True)

    result = lark.register_app(
        on_qr_code=show, source='xdu-meet-2026', cancel_event=cancelled, create_only=True,
        app_preset={'name': 'XDU 赛务服务', 'desc': '本地赛事分组及成绩同步，仅使用应用身份访问指定多维表格'},
        addons={'preset': False, 'scopes': {'tenant': ['bitable:app']}},
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump({'app_id': result['client_id'], 'app_secret': result['client_secret']}, stream)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({'app_id': result['client_id'], 'credentials_saved': str(path),
                      'next': 'Add this application to the target Base with edit permission; then run doctor.'}), flush=True)
