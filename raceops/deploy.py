"""Initialize the five-service event from one stopped, verified template."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from .assets import ROOT, digest
from .compat import environment, prepare
from .template import tree_hash


def initialize(accept_eula: bool):
    template = ROOT / "template-world"
    if not template.is_dir() or template.is_symlink():
        raise ValueError("Prepare a real template first")
    receipt = json.loads((template / "xdu-template.json").read_text())
    if tree_hash(template) != receipt["template_hash"]:
        raise ValueError("Template content changed after preparation")
    if digest(ROOT / "patches/manifest.json") != receipt["patch_manifest_sha256"]:
        raise ValueError("Patch manifest changed; prepare a new stopped template")
    if tree_hash(ROOT / "patches/xdu_race") != receipt["adapter_tree_hash"]:
        raise ValueError("Adapter functions changed; prepare a new stopped template")
    ids = subprocess.run(["docker", "ps", "-q"], text=True, capture_output=True, check=True, timeout=20).stdout.split()
    if ids:
        running = json.loads(subprocess.run(["docker", "inspect", *ids], text=True, capture_output=True, check=True, timeout=20).stdout)
        for container in running:
            for mount in container.get("Mounts", []):
                source = Path(mount.get("Source", "/nonexistent")).resolve()
                if source == template or template.is_relative_to(source) or source.is_relative_to(template):
                    raise ValueError("Template is mounted by a running container; stop it before cloning")
    prepare(accept_eula, ROOT / "volumes/event", ("race-a", "race-b", "race-c"), template)
    for service in ("race-a", "race-b", "race-c"):
        clone = ROOT / "volumes/event" / service / "world"
        if tree_hash(clone) != receipt["template_hash"]:
            raise ValueError(f"Independent clone differs from template: {service}")
        from .instance import install
        install(clone, service, receipt)
    (ROOT / "volumes/event/initialized.json").write_text(json.dumps({
        "schema_version": 1, "template_hash": receipt["template_hash"],
        "adapter_tree_hash": receipt["adapter_tree_hash"], "services": ["proxy", "lobby", "race-a", "race-b", "race-c"]}, indent=2) + "\n")
    print("A/B/C are independent verified copies; existing worlds were not overwritten")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init")
    init.add_argument("--accept-eula", action="store_true")
    sub.add_parser("up")
    args = parser.parse_args()
    try:
        if args.action == "init":
            initialize(args.accept_eula)
        else:
            if not (ROOT / "volumes/event/acceptance.json").exists():
                raise ValueError("Initialize with explicit EULA acceptance first")
            initialized = json.loads((ROOT / "volumes/event/initialized.json").read_text())
            if initialized.get("schema_version") != 1 or initialized.get("services") != ["proxy", "lobby", "race-a", "race-b", "race-c"]:
                raise ValueError("Deployment initialization is incomplete; refusing startup")
            command = ["docker", "compose", "-p", "xdu-event", "-f", str(ROOT / "compose.yaml"), "up", "--build", "--menu=false"]
            os.execvpe(command[0], command, environment())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"deploy: {error}\n")


if __name__ == "__main__":
    main()
