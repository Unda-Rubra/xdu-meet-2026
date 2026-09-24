"""Validated host-side records for the six-track event contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import uuid

from .assets import ROOT
from .snbt import IntArray

IDENTIFIER = re.compile(r"[a-zA-Z0-9_-]{1,80}\Z")


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def identifier(value: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("Identifier must use 1–80 ASCII letters, digits, underscores or hyphens")
    return value


def make_plan(event: dict, roster: dict, group: str, preset_id: str, attempt_id: str, template: dict) -> dict:
    identifier(event["event_id"])
    identifier(attempt_id)
    catalog = json.loads((ROOT / "config/presets.yaml").read_text())
    preset = catalog["presets"][preset_id]
    if len(preset["tracks"]) != 6:
        raise ValueError("A Grand Prix requires exactly six tracks")
    players = []
    for index, player in enumerate(roster["groups"][group]):
        players.append({**player, "index": index,
                        "uuid_int": IntArray(struct.unpack(">iiii", uuid.UUID(player["uuid"]).bytes))})
    tracks = []
    for index, track_id in enumerate(preset["tracks"]):
        entry = catalog["tracks"][track_id]
        if entry["mode"] != "Race" or type(entry["native_id"]) is not int or not 1 <= entry["native_id"] <= 999:
            raise ValueError("Invalid installed Race track")
        records = [{"index": p["index"], "uuid": p["uuid"], "name_at_start": p["name"], "started": False, "finished": False,
                    "status": "DNS", "native_commit_observed": False, "pending_adjudication": True} for p in players]
        tracks.append({"index": index, "track_index": index + 1, "track_id": track_id, "native_id": entry["native_id"],
                       "started": False, "closed": False, "settled": False, "commit_phase_reached": False,
                       "players": records})
    return {"schema_version": 1, "adapter_version": "1.0.0", "identity_mode": "offline_trusted_private",
            "admin_policy": "host_only", "event_id": event["event_id"], "group": group,
            "active_groups": list(roster["groups"]), "configured_rounds": event["grand_prix_rounds"],
            "server": "race-" + group.lower(), "grand_prix_round": roster["grand_prix_round"],
            "attempt_id": attempt_id, "preset_id": preset_id, "preset_hash": canonical_hash([
                {"track_id": t["track_id"], "native_id": t["native_id"], "mode": "Race"} for t in tracks]),
            "roster_hash": canonical_hash(roster["groups"]), "template_hash": template["template_hash"],
            "state": "IDLE", "track_index": 0, "revision": 0, "boot_id": 0, "ai_count": 0,
            "pending_adjudication": True, "roster": players, "tracks": tracks}
