"""Host command execution with bounded responses and explicit backend readback."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from .assets import ROOT
from .snbt import dumps, response_value


class Backend:
    def __init__(self, service: str, compose: Path | None = None, project: str = "xdu-event"):
        self.service = service
        self.compose = compose or ROOT / "compose.yaml"
        self.project = project

    def command(self, command: str) -> str:
        result = subprocess.run(
            ["docker", "compose", "-p", self.project, "-f", str(self.compose), "exec", "-T", self.service,
             "python3", "-m", "raceops.rcon", "--json"],
            input=command, text=True, capture_output=True, timeout=20, cwd=ROOT,
            env={**os.environ, "LOCAL_UID": str(os.getuid()), "LOCAL_GID": str(os.getgid())},
        )
        if result.returncode:
            raise RuntimeError(f"{self.service}: {result.stderr.strip() or 'control transport failed'}")
        return json.loads(result.stdout)["response"]

    def commands(self, commands):
        result = subprocess.run(
            ['docker', 'compose', '-p', self.project, '-f', str(self.compose), 'exec', '-T', self.service,
             'python3', '-m', 'raceops.rcon', '--batch'], input=json.dumps(commands), text=True,
            capture_output=True, timeout=240, cwd=ROOT,
            env={**os.environ, 'LOCAL_UID': str(os.getuid()), 'LOCAL_GID': str(os.getgid())})
        if result.returncode:
            raise RuntimeError(self.service + ': ' + result.stderr.strip())
        return json.loads(result.stdout)['responses']

    def read(self, path: str = "current", storage: str = "xdu_race:state"):
        return response_value(self.command(f"data get storage {storage} {path}"))

    def stage(self, path: str, value) -> None:
        commands = []
        def append(target, child):
            command = f'data modify storage xdu_race:request {target} set value {dumps(child)}'
            if len(command.encode('utf-8')) <= 1200:
                commands.append(command)
            elif isinstance(child, dict):
                commands.append(f'data modify storage xdu_race:request {target} set value {{}}')
                for key, nested in child.items():
                    append(f'{target}.{dumps(key)}', nested)
            elif isinstance(child, list):
                commands.append(f'data modify storage xdu_race:request {target} set value []')
                for index, nested in enumerate(child):
                    empty = '{}' if isinstance(nested, dict) else '[]' if isinstance(nested, list) else dumps(nested)
                    commands.append(f'data modify storage xdu_race:request {target} append value {empty}')
                    append(f'{target}[{index}]', nested)
            else:
                raise ValueError('Scalar request exceeds native command limit')
        append(path, value)
        self.commands(commands)
        if self.read(path, 'xdu_race:request') != value:
            raise ValueError('Native request staging readback mismatch')
