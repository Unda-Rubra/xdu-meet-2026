"""Offline UUIDs are stable keys, never authentication or administrator proof."""
from __future__ import annotations

import hashlib
import re
import uuid

NAME = re.compile(r"[A-Za-z0-9_]{1,16}\Z")
GROUPS = ("A", "B", "C")


def offline_uuid(name: str) -> str:
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError("Player names must contain 1–16 ASCII letters, digits or underscores")
    return str(uuid.UUID(bytes=hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest(), version=3))


def validate_roster(data: dict, event_id: str, round_number: int) -> dict:
    if data.get("schema_version") != 1 or data.get("event_id") != event_id:
        raise ValueError("Roster schema/event mismatch")
    if data.get("grand_prix_round") != round_number or type(round_number) is not int or not 1 <= round_number <= 5:
        raise ValueError("Roster round must match the requested Grand Prix (1–5)")
    groups = data.get("groups")
    if not isinstance(groups, dict) or set(groups) != set(GROUPS):
        raise ValueError("Roster must specify exactly groups A, B, C")
    seen_names: set[str] = set()
    seen_uuids: set[str] = set()
    result: dict[str, list[dict]] = {}
    for group in GROUPS:
        players = groups[group]
        if not isinstance(players, list) or not 1 <= len(players) <= 17:
            raise ValueError(f"Group {group} must contain 1–17 entrants")
        result[group] = []
        for player in players:
            if not isinstance(player, dict) or set(player) != {"name", "uuid"}:
                raise ValueError("Every roster entrant must contain only name and uuid")
            name = player["name"]
            expected = offline_uuid(name)
            if player["uuid"] != expected:
                raise ValueError(f"Offline UUID does not match the exact fixed name: {name}")
            if name.casefold() in seen_names or expected in seen_uuids:
                raise ValueError(f"Duplicate or case-ambiguous entrant: {name}")
            seen_names.add(name.casefold())
            seen_uuids.add(expected)
            result[group].append({"uuid": expected, "name": name})
    return {"schema_version": 1, "event_id": event_id, "grand_prix_round": round_number,
            "identity_mode": "offline_trusted_private", "groups": result}
