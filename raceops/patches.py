"""Apply hash-bound changes to a private copy of the official datapack."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from .assets import ROOT


def apply(world: Path) -> None:
    manifest = json.loads((ROOT / "patches/manifest.json").read_text())
    overlay = world / "datapacks/xdu_race"
    if overlay.exists():
        raise ValueError("Refusing to overwrite existing tournament datapack")
    archive_path = world / "datapacks/sr_code.zip"
    if not archive_path.is_file():
        raise ValueError("Expected untouched release sr_code.zip")
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != manifest["archive_sha256"]:
        raise ValueError("Sprint Racer code archive differs from locked release")
    replacements = {}
    with zipfile.ZipFile(archive_path) as archive:
        for patch in manifest["files"]:
            source = archive.read(patch["path"])
            if hashlib.sha256(source).hexdigest() != patch["sha256"]:
                raise ValueError(f"Upstream patch input changed: {patch['path']}")
            text = source.decode("utf-8")
            for change in patch.get("changes", []):
                if text.count(change["anchor"]) != 1:
                    raise ValueError(f"Patch anchor not unique: {patch['path']}")
                text = text.replace(change["anchor"], change["replacement"], 1)
            text = patch.get("prefix", "") + text + patch.get("suffix", "")
            replacements[patch["path"]] = text.encode("utf-8")
        temporary = archive_path.with_suffix(".patched.zip")
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as output:
                for item in archive.infolist():
                    output.writestr(item, replacements.get(item.filename, archive.read(item)))
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    temporary.replace(archive_path)
    shutil.copytree(ROOT / "patches/xdu_race", overlay)
