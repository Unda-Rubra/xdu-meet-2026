"""Build the single native settings lobby; gameplay remains in the race worlds."""
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
    prefix = "data/sprint_racer/function/"
    with zipfile.ZipFile(archive_path) as archive:
        contents = {item.filename: archive.read(item) for item in archive.infolist()}
    for name, content in list(contents.items()):
        relative = name.removeprefix(prefix)
        if not name.startswith(prefix) or not name.endswith(".mcfunction"):
            continue
        mode = relative.split("/")
        if (len(mode) >= 3 and mode[0] == "game_logic" and mode[1].isdigit() and mode[1] not in ("0", "9", "10", "11") and mode[-1].startswith("_initialize")) or relative in {
            "game_logic/0/set_mode_ready.mcfunction", "game_logic/0/grand_prix_round_start.mcfunction",
            "game_logic/11/start_grand_prix.mcfunction", "admin_enter_editor.mcfunction", "join_solo.mcfunction",
            "inventory_check/inventory_controls/admin_menu.mcfunction"
        }:
            contents[name] = b"return 0\n" + content
    join = prefix + "join.mcfunction"
    contents[join] = b"tag @s remove admin\ntag @s remove xdu_qq_registered\nscoreboard players set @s adminMode 0\n" + contents[join]
    # Native props, item interactions, movement and boundary checks remain intact.
    main = prefix + "game_logic/0/gl0_main.mcfunction"
    text = contents[main].decode()
    ready_item = "function sprint_racer_language:lobby/ready_up_item"
    if text.count(ready_item) != 1:
        raise ValueError("Native ready-item boundary changed")
    text = text.replace(ready_item, "# Waiting room has no ready-up item", 1)
    contents[main] = text.encode()
    # These are editors, not races. Limit their lobby portals to the host-approved
    # session tag; leave native editor initialization and track-pool controls intact.
    portals = prefix + "game_logic/0/misc_lobby_happenings/_main.mcfunction"
    portal_text = contents[portals].decode()
    for target in ("game_logic/9/_initialize", "game_logic/10/_initialize_def", "game_logic/11/_initialize"):
        matches = [line for line in portal_text.splitlines() if "run schedule function sprint_racer:" + target + " " in line]
        if len(matches) != 1 or "as @a[" not in matches[0]:
            raise ValueError("Native administrator editor portal changed: " + target)
        portal_text = portal_text.replace(matches[0], matches[0].replace("as @a[", "as @a[tag=xdu_admin,", 1), 1)
    contents[portals] = portal_text.encode()
    temporary = archive_path.with_suffix(".waiting.zip")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
    temporary.replace(archive_path)
    # The stock ADMIN MENU restarts/forces readiness; none of those controls
    # configures the GP pool. Keep the independent native option signs intact.
    language_path = destination / "datapacks/sr_language_all.zip"
    with zipfile.ZipFile(language_path) as archive:
        language = {item.filename: archive.read(item) for item in archive.infolist()}
    item_key = "data/sprint_racer_language/function/_dlc_4/give_inventory_controls.mcfunction"
    original = language[item_key].decode().splitlines(keepends=True)
    matches = [index for index, line in enumerate(original) if "custom_data={invControl:1b,invAdmin:1b}" in line]
    if len(matches) != 1:
        raise ValueError("Native admin-menu item boundary changed")
    original[matches[0]] = "# Obsolete native ADMIN MENU disabled in the main lobby.\n"
    language[item_key] = "".join(original).encode()
    controls_key = "data/sprint_racer_language/function/_dlc_2/admin_controls.mcfunction"
    if controls_key not in language:
        raise ValueError("Native admin-menu dispatch boundary changed")
    language[controls_key] = b"return 0\n"
    idle_key = "data/sprint_racer_language/function/afk_tag.mcfunction"
    idle = language[idle_key].decode()
    idle_selector = "@s[scores={subtitleDelay=..0}]"
    if idle.count(idle_selector) != 2:
        raise ValueError("Native idle subtitle boundary changed")
    language[idle_key] = idle.replace(idle_selector, "@s[tag=xdu_qq_registered,scores={subtitleDelay=..0}]").encode()
    wake_key = "data/sprint_racer_language/function/afk_tag_remove.mcfunction"
    wake = language[wake_key].decode()
    for command in ('title @s subtitle [""]', 'title @s title [""]'):
        if wake.count(command) != 1:
            raise ValueError("Native idle wakeup boundary changed")
        wake = wake.replace(command, 'execute if entity @s[tag=xdu_qq_registered] run ' + command, 1)
    language[wake_key] = wake.encode()
    language_temporary = language_path.with_suffix(".waiting.zip")
    with zipfile.ZipFile(language_temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in language.items():
            archive.writestr(name, content)
    language_temporary.replace(language_path)
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
