"""Local console transport; proxy admission policy remains authoritative."""
import os
import subprocess
from .assets import ROOT


def proxy_command(command):
    if '\n' in command or '\r' in command:
        raise ValueError('Proxy commands must be one line')
    result = subprocess.run(['docker', 'compose', '-p', 'xdu-event', '-f', str(ROOT / 'compose.yaml'),
                             'exec', '-T', 'proxy', 'python3', '-c',
                             "import sys; command=sys.stdin.read(); f=open('/proc/1/fd/0','w'); f.write(command+'\\n'); f.flush()"],
                            input=command, text=True, capture_output=True, timeout=10, cwd=ROOT,
                            env={**os.environ, 'LOCAL_UID': str(os.getuid()), 'LOCAL_GID': str(os.getgid())})
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Proxy console unavailable')
