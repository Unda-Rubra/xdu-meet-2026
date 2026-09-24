"""Host event configuration; active membership is pinned before preset mutation."""
from __future__ import annotations

import json
import os

from .assets import ROOT

MAX_ROUNDS = 7
GROUP_OPTIONS = (("A", "B"), ("A", "B", "C"))


def validate_event(event: dict) -> dict:
    rounds = event.get("grand_prix_rounds")
    if type(rounds) is not int or not 1 <= rounds <= MAX_ROUNDS:
        raise ValueError("grand_prix_rounds must be an integer from 1 to 7")
    return event


def load_event() -> dict:
    return validate_event(json.loads((ROOT / "config/event.yaml").read_text()))


def race_services(groups) -> tuple[str, ...]:
    return tuple("race-" + group.lower() for group in groups)


def pinned_groups() -> list[str]:
    path = ROOT / "volumes/control/groups.json"
    if not path.exists():
        # Existing installations provision all three. First reduction checks C too.
        return list(GROUP_OPTIONS[1])
    groups = json.loads(path.read_text())["groups"]
    if groups not in [list(option) for option in GROUP_OPTIONS]:
        raise ValueError("Invalid pinned group configuration; retain it for recovery")
    return groups


def pin_groups(groups: list[str]) -> None:
    path = ROOT / "volumes/control/groups.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as stream:
        json.dump({"groups": groups}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
