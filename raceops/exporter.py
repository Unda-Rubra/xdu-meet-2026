"""Read backend state without mutating worlds and publish immutable archives."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import uuid
import re
import subprocess

from .assets import ROOT, digest
from .model import canonical_hash, identifier


def consistent_snapshot(backend, round_number=None, attempt_id=None):
    if attempt_id is not None:
        identifier(attempt_id)
    for _ in range(3):
        before = backend.read()
        if round_number is None and attempt_id is None:
            snapshot = before
        else:
            history = backend.read("attempts", "xdu_race:results")
            candidates = [entry for key, entry in history.items()
                          if (attempt_id is None or key == attempt_id)
                          and (round_number is None or entry.get("grand_prix_round") == round_number)]
            if len(candidates) != 1:
                raise ValueError(f"{backend.service}: historical attempt absent or ambiguous; specify --attempt")
            snapshot = candidates[0]
        after = backend.read()
        if (before.get("boot_id"), before.get("attempt_id"), before.get("revision")) == (
                after.get("boot_id"), after.get("attempt_id"), after.get("revision")):
            if snapshot.get('state') == 'GP_FINISHED' and not snapshot.get('frozen'):
                raise ValueError(f'{backend.service}: terminal result is not frozen')
            online_response = backend.command("list uuids")
            return snapshot, online_response
    raise RuntimeError(f"{backend.service}: snapshot changed during all three reads")


def result_rows(snapshot, exported_at):
    if not snapshot.get('results'):
        return [], []
    rows = []
    for player in snapshot['roster']:
        result = snapshot['results'].get(player['uuid'])
        if result is None:
            raise ValueError('Missing native result for a registered entrant')
        rows.append({'event_id': snapshot['event_id'], 'attempt_id': snapshot['attempt_id'],
                     'group': snapshot['group'], 'qq': player['qq'], 'uuid': player['uuid'],
                     'name': player['name'], 'native_total': result['total'], 'status': result['status'],
                     'exported_at': exported_at})
    return [], rows


def write_csv(path, rows):
    if not rows:
        return
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())


def export(backends, round_number=None, attempt_id=None, directory: Path | None = None):
    directory = directory or ROOT / "exports"
    directory.mkdir(parents=True, exist_ok=True)
    exported_at = datetime.now(timezone.utc).isoformat()
    export_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex
    temporary = Path(tempfile.mkdtemp(prefix=".export-", dir=directory))
    manifest = {"schema_version": 1, "export_id": export_id, "exported_at": exported_at,
                "complete": False, "identity_mode": "offline_trusted_private", "pending_adjudication": True,
                "servers": {}, "files": {}, "errors": [], "warnings": ["Offline identities are organizer-supervised, not authenticated", "No external event points computed"]}
    track_rows, gp_rows = [], []
    try:
        for backend in backends:
            try:
                snapshot, online = consistent_snapshot(backend, round_number, attempt_id)
                filename = backend.service + ".json"
                online_ids = set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", online))
                online_by_uuid = {p["uuid"]: p["uuid"] in online_ids for p in snapshot["roster"]}
                (temporary / filename).write_text(json.dumps({"snapshot": snapshot, "online_now_by_uuid": online_by_uuid,
                    "online_response_at_export": online, "exported_at": exported_at}, ensure_ascii=False, indent=2) + "\n")
                tracks, gp = result_rows(snapshot, exported_at)
                for row in tracks:
                    row["online_now"] = online_by_uuid[row["uuid"]]
                track_rows.extend(tracks)
                gp_rows.extend(gp)
                manifest["servers"][backend.service] = {"state": snapshot["state"], "event_id": snapshot.get("event_id"),
                    "grand_prix_round": snapshot.get("grand_prix_round"), "attempt_id": snapshot["attempt_id"],
                    "boot_id": snapshot["boot_id"], "revision": snapshot["revision"],
                    "snapshot_hash": canonical_hash(snapshot), "snapshot_file": filename,
                    "template_hash": snapshot.get("template_hash"), "preset_hash": snapshot.get("preset_hash"),
                    "settings_hash": snapshot.get("settings_hash"), "players": len(snapshot["roster"]),
                    "frozen": bool(snapshot.get("frozen"))}
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
                manifest["errors"].append({"server": backend.service, "error": str(error)})
        write_csv(temporary / "tracks.csv", track_rows)
        write_csv(temporary / "grand_prix.csv", gp_rows)
        identities = {(v["event_id"], v["grand_prix_round"], v["attempt_id"], v["preset_hash"])
                      for v in manifest["servers"].values()}
        manifest["coherent_attempt"] = len(identities) == 1
        if len(identities) > 1:
            manifest["warnings"].append("Backends describe different attempts or idle states; this is a recovery snapshot, not coherent standings")
        manifest["complete"] = not manifest["errors"] and len(manifest["servers"]) == len(backends)
        for file in temporary.iterdir():
            if file.is_file():
                manifest["files"][file.name] = digest(file)
        (temporary / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        for file in temporary.iterdir():
            if file.is_file():
                with file.open("rb") as stream:
                    os.fsync(stream.fileno())
        directory_fd = os.open(temporary, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        destination = directory / export_id
        os.rename(temporary, destination)
        parent_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return destination, manifest
    except BaseException:
        # Do not overwrite or erase a failed archive; keep its partial evidence.
        (temporary / "FAILED").write_text("Export did not publish a complete manifest\n")
        raise


def verify_receipt(path: Path, states: dict):
    path = path.resolve()
    manifest = json.loads((path / "manifest.json").read_text())
    if not manifest.get("complete") or set(manifest["servers"]) != set(states):
        raise ValueError("Archive is partial or belongs to a different backend set")
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("Unsupported archive receipt schema")
    for filename, checksum in manifest["files"].items():
        if Path(filename).name != filename or (path / filename).is_symlink() or digest(path / filename) != checksum:
            raise ValueError("Archive file hash mismatch")
    for server, state in states.items():
        receipt = manifest["servers"][server]
        filename = receipt.get("snapshot_file", "")
        if not filename or Path(filename).name != filename or filename not in manifest["files"]:
            raise ValueError(f"{server}: receipt has no hashed snapshot file")
        stored = json.loads((path / filename).read_text())["snapshot"]
        if canonical_hash(stored) != receipt["snapshot_hash"]:
            raise ValueError(f"{server}: receipt hash does not describe archived snapshot")
        if stored.get("attempt_id") != receipt["attempt_id"] or stored.get("revision") != receipt["revision"]:
            raise ValueError(f"{server}: archive identity/revision mismatch")
        if stored.get('results') and 'grand_prix.csv' not in manifest['files']:
            raise ValueError('Archive is missing required result CSV')
        if state.get("state") == "IDLE" and state.get("reset_receipt_hash") == receipt["snapshot_hash"] and state.get("attempt_id") == receipt["attempt_id"]:
            continue
        if receipt["snapshot_hash"] != canonical_hash(state):
            raise ValueError(f"{server}: archive is stale; export current final state first")
    return manifest
