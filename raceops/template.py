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
