"""One-shot host control for two or three independently acknowledged race servers."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import getpass
import json
import os
from pathlib import Path
import sys
import subprocess
import uuid

from .assets import ROOT
from .exporter import export, verify_receipt
from .event import MAX_ROUNDS, load_event, pinned_groups, pin_groups, race_services
from .identity import validate_roster
from .model import canonical_hash, identifier, make_plan
from .transport import Backend


@contextmanager
def exclusive():
    directory = ROOT / "exports"
    directory.mkdir(exist_ok=True)
    with (directory / ".racectl.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another racectl operation owns the host lock") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def audit(record):
    path = ROOT / "volumes/control/operations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at_utc": datetime.now(timezone.utc).isoformat(), "operator": getpass.getuser(), **record}, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def statuses(backends):
    states, errors = {}, {}
    for backend in backends:
        try:
            state = backend.read()
            if state.get("schema_version") != 1 or state.get("adapter_version") != "1.0.0":
                raise ValueError("Adapter contract version mismatch")
            states[backend.service] = state
        except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
            errors[backend.service] = str(error)
    return states, errors


def print_states(states, errors):
    print(f"{'SERVER':12} {'STATE':16} {'ROUND':6} {'TRACK':6} {'REV':6} ATTEMPT")
    for server, state in states.items():
        print(f"{server:12} {state['state']:16} {state.get('grand_prix_round', '-'):6} {state.get('track_index', '-'):6} {state['revision']:6} {state.get('attempt_id', '-')}")
    for server, error in errors.items():
        print(f"{server:12} UNKNOWN          {error}")


def send(backend, operation, state, extra=None):
    request = {"operation_id": uuid.uuid4().hex, "expected_revision": state["revision"],
               "expected_boot_id": state["boot_id"], "expected_state": state["state"],
               "attempt_id": state["attempt_id"], **(extra or {})}
    request["payload_hash"] = canonical_hash({"command": operation, **request})
    audit({"operation_id": request["operation_id"], "server": backend.service, "command": operation,
           "phase": "requested", "payload_hash": request["payload_hash"], "expected_revision": state["revision"]})
    try:
        result = backend.request(operation, request)
    except BaseException as error:
        audit({"operation_id": request["operation_id"], "server": backend.service, "command": operation,
               "phase": "unconfirmed", "error": str(error)})
        raise
    audit({"operation_id": request["operation_id"], "server": backend.service, "command": operation,
           "phase": "confirmed", "state": result["state"], "revision": result["revision"]})
    return result


def require_same_attempt(states):
    identities = {(s.get("event_id"), s.get("grand_prix_round"), s.get("attempt_id"),
                   s.get("preset_hash"), s.get("settings_hash"), s.get("roster_hash"), s.get("template_hash"),
                   tuple((t.get("track_id"), t.get("native_id")) for t in s.get("tracks", []))) for s in states.values()}
    if len(identities) != 1:
        raise ValueError("Servers disagree on event, round, attempt, preset, settings or roster")


def select_backends(args):
    if args.compat:
        return [Backend("race", ROOT / "compat.compose.yaml", "xdu-compatibility")]
    groups = pinned_groups()
    if args.groups is not None:
        if args.command not in {"status", "export"}:
            raise ValueError("--groups only selects read-only status/export; use the round roster for racing")
        groups = list("ABC"[:args.groups])
    elif args.command == "preset":
        roster_path = args.roster or ROOT / f"config/rosters/round-{args.round}.json"
        roster = validate_roster(json.loads(roster_path.read_text()), load_event(), args.round)
        configured = list(roster["groups"])
        if configured != groups:
            previous, errors = statuses([Backend(service) for service in race_services(sorted(set(groups + configured)))])
            if errors or any(state["state"] != "IDLE" for state in previous.values()):
                raise ValueError("Changing groups requires all previous and next backends reachable and IDLE; archive/reset first")
            groups = configured
    return [Backend(service) for service in race_services(groups)]


def execute(args, backends):
    if args.command == "export":
        destination, manifest = export(backends, args.round, args.attempt)
        print(destination)
        if not manifest["complete"]:
            raise RuntimeError("Partial export; inspect manifest errors. World state unchanged.")
        return
    states, errors = statuses(backends)
    if args.command == "status":
        print_states(states, errors)
        if errors:
            raise RuntimeError("Some backend states are unknown")
        return
    if errors:
        print_states(states, errors)
        raise RuntimeError("Preflight failed; no control command sent")
    if args.command == "preset":
        if any(s["state"] != "IDLE" for s in states.values()):
            raise ValueError("preset requires every selected server IDLE; archive and explicitly reset first")
        event = load_event()
        roster_path = args.roster or ROOT / f"config/rosters/round-{args.round}.json"
        roster = validate_roster(json.loads(roster_path.read_text()), event, args.round)
        template = json.loads((ROOT / "template-world/xdu-template.json").read_text())
        attempt = identifier(args.attempt or f"gp{args.round}_{uuid.uuid4().hex}")
        plans = []
        for backend in backends:
            group = args.group if args.compat else backend.service[-1].upper()
            plan = make_plan(event, roster, group, args.id, attempt, template)
            plan["settings_summary"] = backend.read("settings", "xdu_race:config")
            plan["settings_hash"] = canonical_hash(plan["settings_summary"])
            if not args.compat:
                plan["provenance"] = backend.read("instance", "xdu_race:config")
            plans.append((backend, plan))
        if not args.compat:
            pin_groups(list(roster["groups"]))
        for backend, plan in plans:
            states[backend.service] = send(backend, "preset", states[backend.service], {"plan": plan})
    elif args.command == "start":
        require_same_attempt(states)
        if all(s["state"] in {"RUNNING", "BETWEEN_TRACKS", "GP_FINISHED"} for s in states.values()):
            print("Current attempt already started; no commands sent")
            print_states(states, {})
            return
        if any(s["state"] not in {"PRESET_LOADED", "ARMED"} for s in states.values()):
            raise ValueError("Mixed or unsafe start state; inspect status and use explicit recovery")
        for backend in backends:
            if states[backend.service]["state"] == "PRESET_LOADED":
                states[backend.service] = send(backend, "prepare", states[backend.service])
        if any(s["state"] != "ARMED" for s in states.values()):
            raise RuntimeError("Not all servers armed")
        # Execution is acknowledged per server, not a distributed atomic commit.
        for backend in backends:
            states[backend.service] = send(backend, "start", states[backend.service])
    elif args.command == "stop":
        if not (args.force and args.acknowledge_error):
            require_same_attempt(states)
        if any(s["state"] in {"RUNNING", "BETWEEN_TRACKS"} for s in states.values()) and not args.force:
            raise ValueError("Active racing requires stop --force --reason; nothing was changed")
        if any(s["state"] == "ERROR" for s in states.values()) and not (args.force and args.acknowledge_error):
            raise ValueError("ERROR requires stop --force --acknowledge-error --reason after operator review")
        for backend in backends:
            if states[backend.service]["state"] not in {"GP_FINISHED", "STOPPED", "IDLE"}:
                states[backend.service] = send(backend, "halt", states[backend.service])
        destination, manifest = export(backends)
        print(f"Pre-stop archive: {destination}")
        if not manifest["complete"]:
            raise RuntimeError("Archive incomplete; launch gates remain closed, no destructive cancellation sent")
        current, failures = statuses(backends)
        if failures:
            raise RuntimeError("Backend disappeared after export; no cancellation sent")
        verify_receipt(destination, current)
        for backend in backends:
            if current[backend.service]["state"] not in {"GP_FINISHED", "STOPPED", "IDLE"}:
                states[backend.service] = send(backend, "stop", current[backend.service], {"archive_verified": True})
        destination, manifest = export(backends)
        print(f"Post-stop archive: {destination}")
        if not manifest["complete"]:
            raise RuntimeError("Stop completed partially; archive current state before reset")
    elif args.command == "reset":
        if any(s["state"] not in {"GP_FINISHED", "STOPPED", "IDLE"} for s in states.values()):
            raise ValueError("reset requires every server GP_FINISHED, STOPPED or already IDLE")
        receipt = verify_receipt(args.archive, states)
        for backend in backends:
            if states[backend.service]["state"] != "IDLE":
                states[backend.service] = send(backend, "reset", states[backend.service], {
                    "archive_verified": True, "archive_snapshot_hash": receipt["servers"][backend.service]["snapshot_hash"]})
    print_states(states, {})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compat", action="store_true", help="Use only the isolated compatibility race backend")
    parser.add_argument("--group", choices=("A", "B", "C"), default="A", help="Roster group for --compat")
    parser.add_argument("--groups", type=int, choices=(2, 3), help="Read-only status/export group selection, including historical attempts")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    preset = sub.add_parser("preset")
    preset.add_argument("id")
    preset.add_argument("--round", type=int, choices=range(1, MAX_ROUNDS + 1), required=True)
    preset.add_argument("--roster", type=Path)
    preset.add_argument("--attempt")
    sub.add_parser("start")
    stop = sub.add_parser("stop")
    stop.add_argument("--force", action="store_true")
    stop.add_argument("--acknowledge-error", action="store_true", help="Explicitly accept reviewed interrupted/partial state before safe cancellation")
    stop.add_argument("--reason", required=True)
    reset = sub.add_parser("reset")
    reset.add_argument("--archive", type=Path, required=True)
    reset.add_argument("--reason", required=True)
    exp = sub.add_parser("export")
    exp.add_argument("--round", type=int, choices=range(1, MAX_ROUNDS + 1))
    exp.add_argument("--attempt")
    args = parser.parse_args()
    try:
        with exclusive():
            backends = select_backends(args)
            if args.command not in {"status", "export"}:
                audit({"command": args.command, "phase": "begin", "reason": getattr(args, "reason", None)})
            execute(args, backends)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
        print(f"racectl: {error}", file=sys.stderr)
        if args.command not in {"status", "export"}:
            print("No automatic rollback performed. Run status; preserve existing attempts before recovery.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
