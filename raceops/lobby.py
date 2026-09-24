"""Build a waiting-only copy of the verified native map, never a race world."""
from __future__ import annotations

import json
import argparse
from datetime import datetime, timezone
import os
import subprocess
import uuid
from pathlib import Path
import shutil
import zipfile

from .assets import ROOT


def prepare_lobby(template: Path, destination: Path) -> None:
    if destination.exists():
        raise ValueError("Lobby destination already exists; preserve it before replacement")
    shutil.copytree(template, destination)
    archive_path = destination / "datapacks/sr_code.zip"
    manifest = json.loads((ROOT / "patches/manifest.json").read_text())
    prefix = "data/sprint_racer/function/"
    with zipfile.ZipFile(archive_path) as archive:
        contents = {item.filename: archive.read(item) for item in archive.infolist()}
    # Reuse the event's audited denial boundaries; only settings become session-authorized.
    for patch in manifest["files"]:
        name = patch["path"]
        if "/options_signs/" in name or name.endswith(("boq/trigger_option.mcfunction", "inventory_controls/admin_menu.mcfunction", "cheat_menu/ca_trigger.mcfunction", "cheat_menu/cl_trigger.mcfunction")):
            text = contents[name].decode()
            guard = "execute unless score #native xdu matches 1 run return 0\n"
            if not text.startswith(guard):
                raise ValueError(f"Expected protected settings entry: {name}")
            # Access policy and AI admission cannot be changed from a waiting-room menu.
            protected = name.endswith(("/admin_mode.mcfunction", "/ai_count_race.mcfunction", "/ai_count_battle.mcfunction", "/ai_add_type_race.mcfunction", "/ai_add_type_battle.mcfunction", "/ai_context_race.mcfunction", "/ai_context_battle.mcfunction", "/defaults.mcfunction", "/save_state_load.mcfunction", "/save_state_load_specific.mcfunction"))
            replacement = "return 0\n" if protected else "execute unless entity @s[type=player,tag=xdu_lobby_operator] run return 0\n"
            contents[name] = (replacement + text[len(guard):]).encode()
    # No mode, editor, practice, ready-up or GP start may activate in this world.
    for name, content in list(contents.items()):
        relative = name.removeprefix(prefix)
        if not name.startswith(prefix) or not name.endswith(".mcfunction"):
            continue
        mode = relative.split("/")
        if (len(mode) >= 3 and mode[0] == "game_logic" and mode[1].isdigit() and mode[1] != "0" and mode[-1].startswith("_initialize")) or relative in {
            "game_logic/0/set_mode_ready.mcfunction", "game_logic/0/grand_prix_round_start.mcfunction",
            "game_logic/11/start_grand_prix.mcfunction", "admin_enter_editor.mcfunction", "join_solo.mcfunction"
        }:
            contents[name] = b"return 0\n" + content
    join = prefix + "join.mcfunction"
    contents[join] = b"tag @s remove xdu_lobby_operator\ntag @s remove admin\nscoreboard players set @s adminMode 0\n" + contents[join]
    # Native props, item interactions, movement and boundary checks remain intact.
    main = prefix + "game_logic/0/gl0_main.mcfunction"
    text = contents[main].decode()
    ready_item = "function sprint_racer_language:lobby/ready_up_item"
    if text.count(ready_item) != 1:
        raise ValueError("Native ready-item boundary changed")
    text = text.replace(ready_item, "# Waiting room has no ready-up item", 1)
    contents[main] = text.encode()
    temporary = archive_path.with_suffix(".waiting.zip")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
    temporary.replace(archive_path)
    overlay = destination / "datapacks/xdu_race/data/xdu_race/function"
    # Native join invokes these; waiting-room visitors are not tournament spectators.
    (overlay / "access/join.mcfunction").write_text("tag @s remove admin\ntag @s remove tournament_admin\nscoreboard players set @s adminMode 0\n")
    (overlay / "access/refresh.mcfunction").write_text("execute as @a[tag=!xdu_lobby_operator] run tag @s remove admin\n")
    (destination / "datapacks/xdu_race/data/minecraft/tags/function/tick.json").write_text('{"values": []}\n')
    shutil.copytree(ROOT / "config/lobby-datapack", destination / "datapacks/xdu_lobby")
    (destination / "xdu-lobby.json").write_text(json.dumps({"schema_version": 1, "source_template": json.loads((template / "xdu-template.json").read_text())["template_hash"], "settings_policy": "host_granted_session_tag", "games_enabled": False}, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    from .cli import exclusive
    from .template import tree_hash
    try:
        with exclusive():
            template = ROOT / "template-world"
            lobby = ROOT / "volumes/event/lobby"
            if not lobby.is_dir() or not (ROOT / "volumes/event/acceptance.json").is_file():
                raise ValueError("Initialize the event with EULA acceptance first")
            receipt = json.loads((template / "xdu-template.json").read_text())
            if tree_hash(template) != receipt["template_hash"]:
                raise ValueError("Template hash mismatch")
            ids = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True, check=True, timeout=20).stdout.split()
            if ids:
                running = json.loads(subprocess.run(["docker", "inspect", *ids], capture_output=True, text=True, check=True, timeout=20).stdout)
                for container in running:
                    for mount in container.get("Mounts", []):
                        source = Path(mount.get("Source", "/nonexistent")).resolve()
                        if any(source == target or source.is_relative_to(target) or target.is_relative_to(source) for target in (template.resolve(), lobby.resolve())):
                            raise ValueError("Stop the lobby and any template-mounted server before installing; race worlds are not changed")
            suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
            staged = lobby / ("world-waiting-" + suffix)
            prepare_lobby(template, staged)
            world = lobby / "world"
            if world.exists():
                backup = lobby / ("world-before-waiting-" + suffix)
                os.rename(world, backup)
                print(f"Previous lobby preserved: {backup}")
            os.rename(staged, world)
            print("Native waiting room installed; start the lobby. Race worlds unchanged.")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"prepare-lobby: {error}\n")
