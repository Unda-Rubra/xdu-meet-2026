"""Create an immutable event template from the locked release, never a running world."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from .assets import ROOT, digest, load_lock
from .compat import extract_world
from .patches import apply


def tree_hash(directory: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Template symlinks are forbidden")
        if path.is_file() and path.name != "xdu-template.json":
            h.update(path.relative_to(directory).as_posix().encode() + b"\0")
            h.update(bytes.fromhex(digest(path)))
    return h.hexdigest()


def bundle_native_datapack(world: Path, name: str) -> None:
    source = world / "datapacks" / name
    if not source.is_dir() or not (source / "pack.mcmeta").is_file():
        raise ValueError(f"Official release is missing datapack {name}")
    target = source.with_suffix(".zip")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise ValueError("Official datapack contains a symlink")
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(source).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
                bundle.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    shutil.rmtree(source)


def install_official_tracks(world: Path, archive: Path, checksum: str) -> None:
    if not archive.is_file() or archive.is_symlink() or digest(archive) != checksum:
        raise ValueError("Official Mario Kart track pack differs from the asset lock")
    import stat
    from pathlib import PurePosixPath
    with zipfile.ZipFile(archive) as bundle:
        names = {item.filename for item in bundle.infolist()}
        expected = "datapacks/mario_kart_track_pack/pack.mcmeta"
        if expected not in names or sum(name.endswith("command_storage.dat") for name in names) != 27:
            raise ValueError("Unexpected Mario Kart track pack layout")
        for item in bundle.infolist():
            name = PurePosixPath(item.filename)
            if (name.is_absolute() or ".." in name.parts or "\\" in item.filename
                    or stat.S_ISLNK(item.external_attr >> 16)
                    or not item.filename.startswith(("data/", "datapacks/", "dimensions/"))):
                raise ValueError("Unsafe Mario Kart track pack member")
            target = world.joinpath(*name.parts)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    metadata = world / "datapacks/mario_kart_track_pack/pack.mcmeta"
    original = json.loads(metadata.read_text())
    if original["pack"].get("pack_format") != 61:
        raise ValueError("Author's track pack format changed; review before enabling")
    original["pack"].pop("pack_format")
    original["pack"].update({"min_format": 121, "max_format": 121})
    metadata.write_text(json.dumps(original) + "\n")


def prepare() -> Path:
    target = ROOT / "template-world"
    if target.exists() or target.is_symlink():
        raise ValueError("Template already exists; refusing to overwrite")
    lock = load_lock()
    archive = ROOT / "downloads" / lock["artifacts"]["world"]["filename"]
    if digest(archive) != lock["artifacts"]["world"]["sha256"]:
        raise ValueError("World archive hash mismatch")
    # No template currently exists; staging is never mounted by any server.
    temporary = Path(tempfile.mkdtemp(prefix=".template-", dir=ROOT / "downloads"))
    try:
        extract_world(archive, lock["world_prefix"], temporary)
        for name in ("sr_code", "sr_language_all"):
            bundle_native_datapack(temporary, name)
        install_official_tracks(temporary, ROOT / "downloads" / lock["artifacts"]["mario_tracks"]["filename"],
                                lock["artifacts"]["mario_tracks"]["sha256"])
        apply(temporary)
        config = temporary / "datapacks/sr_config/data/sprint_racer_config/function"
        admin = config / "admin_mode.mcfunction"
        text = admin.read_text()
        old = "adminMode 0"
        if text.count(old) != 1:
            raise ValueError("Unexpected release Admin Mode configuration")
        admin.write_text(text.replace(old, "adminMode 1", 1))
        # No offline identity may grant administrative authority.
        (config / "admin_player_list.mcfunction").write_text("# Host-only administration; no player grants.\n")
        receipt = {"schema_version": 1, "world_sha256": lock["artifacts"]["world"]["sha256"],
                   "patch_manifest_sha256": digest(ROOT / "patches/manifest.json"),
                   "adapter_tree_hash": tree_hash(ROOT / "patches/xdu_race"),
                   "adapter_version": "2.0.0", "identity_mode": "offline_trusted_private",
                   "mario_tracks_sha256": lock["artifacts"]["mario_tracks"]["sha256"],
                   "template_hash": tree_hash(temporary)}
        (temporary / "xdu-template.json").write_text(json.dumps(receipt, indent=2) + "\n")
        os.rename(temporary, target)
    except BaseException:
        shutil.rmtree(temporary)
        raise
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        print(f"Prepared {prepare()}")
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"prepare-template: {error}\n")


if __name__ == "__main__":
    main()
