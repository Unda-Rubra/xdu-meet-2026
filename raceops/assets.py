"""Download only content-addressed, explicitly locked tournament artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_lock(root: Path = ROOT) -> dict:
    data = json.loads((root / "config/versions.lock.json").read_text())
    if data.get("schema_version") != 1 or not isinstance(data.get("artifacts"), dict):
        raise ValueError("Unsupported or missing artifact lock")
    for name, entry in data["artifacts"].items():
        filename = entry.get("filename", "")
        checksum = entry.get("sha256", "")
        if not filename or Path(filename).name != filename or filename in {".", ".."}:
            raise ValueError(f"Unsafe artifact filename: {name}")
        if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
            raise ValueError(f"Missing or invalid SHA-256: {name}")
        if not entry.get("url", "").startswith("https://"):
            raise ValueError(f"Artifact must use HTTPS: {name}")
    return data


def acquire(name: str, entry: dict, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / entry["filename"]
    if target.exists():
        if target.is_symlink() or not target.is_file() or digest(target) != entry["sha256"]:
            raise ValueError(f"Existing {name} does not match lock; refusing to overwrite")
        return target
    fd, temporary = tempfile.mkstemp(prefix=f".{name}-", dir=directory)
    try:
        # curl uses the host's configured trust store (including managed macOS
        # roots). TLS verification stays enabled; bytes must also match the lock.
        with os.fdopen(fd, "wb") as output:
            result = subprocess.run(
                ["curl", "--fail", "--location", "--silent", "--show-error",
                 "--proto", "=https", "--proto-redir", "=https", "--max-time", "600",
                 "--user-agent", "xdu-race-event/1", entry["url"]],
                stdout=output, stderr=subprocess.PIPE, check=False, timeout=610,
            )
            if result.returncode:
                raise OSError(f"Artifact download failed: {name}: {result.stderr.decode(errors='replace').strip()}")
            output.flush()
            os.fsync(output.fileno())
        temporary_path = Path(temporary)
        if digest(temporary_path) != entry["sha256"]:
            raise ValueError(f"Downloaded {name} SHA-256 differs from lock")
        # link is an atomic no-clobber publication, even with concurrent fetchers.
        try:
            os.link(temporary_path, target)
        except FileExistsError:
            if target.is_symlink() or digest(target) != entry["sha256"]:
                raise ValueError(f"Concurrent artifact conflict: {name}") from None
        return target
    finally:
        Path(temporary).unlink(missing_ok=True)


def acquire_resource_pack(lock: dict, directory: Path) -> Path:
    entry = lock["resource_pack"]
    source = directory / lock["artifacts"]["world"]["filename"]
    target = directory / entry["filename"]
    if target.exists():
        if (target.is_symlink() or digest(target) != entry["sha256"]
                or digest(target, "sha1") != entry["sha1"]):
            raise ValueError("Existing version-matched resource pack differs from the lock")
        return target
    fd, temporary = tempfile.mkstemp(prefix=".resource-pack-", dir=directory)
    try:
        with zipfile.ZipFile(source) as world, os.fdopen(fd, "wb") as output:
            with world.open(entry["archive_member"]) as content:
                for block in iter(lambda: content.read(1024 * 1024), b""):
                    output.write(block)
            output.flush()
            os.fsync(output.fileno())
        item = Path(temporary)
        if digest(item) != entry["sha256"] or digest(item, "sha1") != entry["sha1"]:
            raise ValueError("Official embedded resource pack checksum mismatch")
        os.link(item, target)
        return target
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", help="Locked artifact names; default: all")
    args = parser.parse_args()
    try:
        lock = load_lock()
        names = args.only or list(lock["artifacts"])
        unknown = set(names) - lock["artifacts"].keys()
        if unknown:
            raise ValueError(f"Unknown artifacts: {sorted(unknown)}")
        for name in names:
            path = acquire(name, lock["artifacts"][name], ROOT / "downloads")
            print(f"{name}: verified {path.relative_to(ROOT)}")
        if args.only is None or "world" in names:
            pack = acquire_resource_pack(lock, ROOT / "downloads")
            print(f"resource_pack: verified {pack.relative_to(ROOT)}")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"fetch-assets: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
