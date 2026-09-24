"""Host-only proxy routing with backend readback; no client admin permissions."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from .assets import ROOT
from .cli import audit, exclusive, statuses, require_same_attempt
from .exporter import verify_receipt
from .event import MAX_ROUNDS, load_event, pinned_groups, race_services
from .identity import NAME, validate_roster
from .model import canonical_hash
from .transport import Backend


def proxy_command(command: str):
    result = subprocess.run(["docker", "compose", "-p", "xdu-event", "-f", str(ROOT / "compose.yaml"),
                             "exec", "-T", "proxy", "python3", "-c",
                             "import sys; command=sys.stdin.read(); f=open('/proc/1/fd/0','w'); f.write(command+'\\n'); f.flush()"],
                            input=command, text=True, capture_output=True, timeout=10, cwd=ROOT,
                            env={**os.environ, "LOCAL_UID": str(os.getuid()), "LOCAL_GID": str(os.getgid())})
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Proxy console unavailable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round", type=int, choices=range(1, MAX_ROUNDS + 1), required=True)
    parser.add_argument("--lobby", action="store_true", help="Return completed groups to lobby; requires --archive")
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    try:
        with exclusive():
            event = load_event()
            groups = pinned_groups()
            roster_event = {**event, "grand_prix_rounds": MAX_ROUNDS if args.lobby else event["grand_prix_rounds"]}
            roster = validate_roster(json.loads((ROOT / f"config/rosters/round-{args.round}.json").read_text()), roster_event, args.round)
            if list(roster["groups"]) != groups:
                raise ValueError("Roster groups differ from the loaded attempt; no player was routed")
            backends = [Backend(service) for service in race_services(groups)]
            states, errors = statuses(backends)
            if errors:
                raise RuntimeError("Cannot route while any race backend is unavailable")
            require_same_attempt(states)
            if any(s.get("grand_prix_round") != args.round or s.get("roster_hash") != canonical_hash(roster["groups"]) for s in states.values()):
                raise ValueError("Local roster changed or round differs from loaded attempt; no player was routed")
            if args.lobby:
                if not args.archive or any(s["state"] not in {"GP_FINISHED", "STOPPED"} for s in states.values()):
                    raise ValueError("Lobby return requires all GPs ended and an archive receipt")
                verify_receipt(args.archive, states)
            elif any(s["state"] != "PRESET_LOADED" or s.get("grand_prix_round") != args.round for s in states.values()):
                raise ValueError("Group routing requires the selected round loaded on every server")
            for group in groups:
                target = "lobby" if args.lobby else "race-" + group.lower()
                for player in roster["groups"][group]:
                    if not NAME.fullmatch(player["name"]):
                        raise ValueError("Invalid player name")
                    proxy_command(f"send {player['name']} {target}")
                    audit({"command": "route", "target": target, "round": args.round, "phase": "sent", "uuid": player["uuid"]})
            deadline = time.monotonic() + 30
            while True:
                missing = []
                for group in groups:
                    target = "lobby" if args.lobby else "race-" + group.lower()
                    online = Backend(target).command("list uuids")
                    missing.extend(p["name"] for p in roster["groups"][group] if p["uuid"] not in online)
                if not missing:
                    print("All roster members confirmed on their target backend")
                    return 0
                if time.monotonic() >= deadline:
                    raise RuntimeError("Routing not confirmed for: " + ", ".join(missing))
                time.sleep(1)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"route-roster: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
