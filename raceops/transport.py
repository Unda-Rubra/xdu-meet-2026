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

    def read(self, path: str = "current", storage: str = "xdu_race:state"):
        return response_value(self.command(f"data get storage {storage} {path}"))

    def stage(self, path: str, value) -> None:
        command = f"data modify storage xdu_race:request {path} set value {dumps(value)}"
        if len(command.encode("utf-8")) <= 1200:
            self.command(command)
            return
        if isinstance(value, dict):
            self.command(f"data modify storage xdu_race:request {path} set value {{}}")
            for key, child in value.items():
                self.stage(f"{path}.{dumps(key)}", child)
        elif isinstance(value, list):
            self.command(f"data modify storage xdu_race:request {path} set value []")
            for index, child in enumerate(value):
                empty = "{}" if isinstance(child, dict) else "[]" if isinstance(child, list) else dumps(child)
                self.command(f"data modify storage xdu_race:request {path} append value {empty}")
                self.stage(f"{path}[{index}]", child)
        else:
            raise ValueError("Scalar request exceeds the native RCON command limit")

    def request(self, operation: str, arguments: dict) -> dict:
        if operation not in {"preset", "prepare", "start", "halt", "stop", "reset"}:
            raise ValueError("Unknown control operation")
        staged = {key: value for key, value in arguments.items() if key != "plan"}
        # Clear optional authorization from the preceding operation before staging.
        self.command("data remove storage xdu_race:request archive_verified")
        self.command(f"data merge storage xdu_race:request {dumps(staged)}")
        self.command("data remove storage xdu_race:request plan")
        if "plan" in arguments:
            self.stage("plan", arguments["plan"])
            if self.read("plan", "xdu_race:request") != arguments["plan"]:
                raise RuntimeError(f"{self.service}: staged plan readback differs; not activating")
        response = self.command(f"function xdu_race:control/{operation}")
        state = self.read()
        if state.get("operation_id") != arguments["operation_id"] or state.get("payload_hash") != arguments["payload_hash"]:
            raise RuntimeError(f"{self.service}: {operation} not acknowledged; state={state.get('state')}; response={response[:160]}")
        return state
