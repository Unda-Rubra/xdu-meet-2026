"""Per-instance metadata, separate from the identical stopped template."""
import json
from pathlib import Path

from .snbt import dumps
from .assets import load_lock


def install(world: Path, service: str, receipt: dict):
    group = service[-1].upper()
    if group not in "ABC" or service != "race-" + group.lower():
        raise ValueError("Invalid race service")
    root = world / "datapacks/xdu_instance"
    if root.exists():
        raise ValueError("Instance metadata already exists")
    function_dir = root / "data/xdu_instance/function"
    function_dir.mkdir(parents=True)
    tags = root / "data/minecraft/tags/function"
    tags.mkdir(parents=True)
    (root / "pack.mcmeta").write_text(json.dumps({"pack": {"min_format": 107, "max_format": 107, "description": "Private event instance provenance"}}))
    (tags / "load.json").write_text('{"values":["xdu_instance:load"]}\n')
    metadata = {"server": service, "group": group, "template_hash": receipt["template_hash"],
                "adapter_tree_hash": receipt["adapter_tree_hash"], "template_receipt": receipt,
                "versions": load_lock()}
    (function_dir / "load.mcfunction").write_text("data modify storage xdu_race:config instance set value " + dumps(metadata) + "\n")
