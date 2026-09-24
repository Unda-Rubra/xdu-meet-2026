"""Private offline-session compatibility harness. Not the tournament deployment."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

from .assets import ROOT, digest, load_lock

COMPOSE = ROOT / "compat.compose.yaml"
DATA = ROOT / "volumes/compatibility"


def extract_world(archive: Path, prefix: str, destination: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        selected = [m for m in bundle.infolist() if m.filename.startswith(prefix)]
        if not any(m.filename == prefix + "level.dat" for m in selected):
            raise ValueError("Locked ZIP does not contain the expected world")
        for member in selected:
            relative = PurePosixPath(member.filename[len(prefix):])
            if relative.is_absolute() or ".." in relative.parts or "\\" in str(relative):
                raise ValueError("Unsafe archive path")
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError("Archive symlinks are not permitted")
            target = destination.joinpath(*relative.parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)


def prepare(accepted: bool, destination: Path = DATA, races: tuple[str, ...] = ("race",), template: Path | None = None) -> None:
    if not accepted:
        raise ValueError("Explicit --accept-eula is required: https://www.minecraft.net/eula")
    if destination.exists() or destination.is_symlink():
        raise ValueError("Deployment data already exists; refusing to overwrite")
    lock = load_lock()
    for name, entry in lock["artifacts"].items():
        artifact = ROOT / "downloads" / entry["filename"]
        if not artifact.is_file() or digest(artifact) != entry["sha256"]:
            raise ValueError(f"Missing or mismatched locked artifact: {name}; run fetch-assets")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".deployment-", dir=destination.parent))
    try:
        for service in (*races, "lobby", "proxy"):
            (temporary / service).mkdir()
        for service in races:
            if template is None:
                extract_world(ROOT / "downloads" / lock["artifacts"]["world"]["filename"], lock["world_prefix"], temporary / service / "world")
            else:
                shutil.copytree(template, temporary / service / "world")
        (temporary / "secrets").mkdir(mode=0o700)
        for service in (*races, "lobby"):
            password = secrets.token_urlsafe(32)
            secret = temporary / "secrets" / service
            secret.write_text(password)
            secret.chmod(0o600)
            directory = temporary / service
            (directory / "eula.txt").write_text("# Explicitly accepted by deployment owner\neula=true\n")
            properties = {
                "level-name": "world", "online-mode": "false", "enforce-secure-profile": "false",
                "enable-rcon": "true", "rcon.port": "25575", "rcon.password": password,
                "broadcast-rcon-to-ops": "false", "server-port": "25565", "max-players": "60" if service == "lobby" else "20",
                "difficulty": "2", "allow-flight": "true", "view-distance": "8",
                "simulation-distance": "8", "spawn-protection": "0", "pause-when-empty-seconds": "0",
                "resource-pack": lock["resource_pack"]["url"],
                "resource-pack-sha1": lock["resource_pack"]["sha1"], "require-resource-pack": "true",
                "resource-pack-id": "1575504c-90ec-4241-89ba-c44de61d0491",
                "motd": f"XDU private event {service}",
            }
            if service == "lobby":
                properties.update({"gamemode": "adventure", "difficulty": "2"})
                if template is not None:
                    from .lobby import prepare_lobby
                    prepare_lobby(template, directory / "world")
                else:
                    # The isolated compatibility harness retains a plain vanilla lobby.
                    properties.update({"level-type": "minecraft:flat", "generate-structures": "false"})
            prop_path = directory / "server.properties"
            prop_path.write_text("".join(f"{k}={v}\n" for k, v in properties.items()))
            prop_path.chmod(0o600)
        proxy = temporary / "proxy"
        # Disable remote module management; explicitly locked modules load as plugins.
        (proxy / "modules.yml").write_text("version: 2\nmodules: []\n")
        (proxy / "plugins").mkdir()
        for module in ("cmd_server", "cmd_send"):
            shutil.copyfile(ROOT / "downloads" / lock["artifacts"][module]["filename"], proxy / "plugins" / f"{module}.jar")
        proxy_configuration = {
            "online_mode": False, "ip_forward": False, "network_compression_threshold": 256,
            "player_limit": 60, "connection_throttle": 4000, "prevent_proxy_connections": False,
            "log_commands": True, "log_pings": False,
            "permissions": {"default": ["bungeecord.command.server"]}, "groups": {},
            "servers": {name: {"address": f"{name}:25565", "motd": name, "restricted": False}
                        for name in ("lobby", *races)},
            "listeners": [{"host": "0.0.0.0:25565", "query_enabled": False, "ping_passthrough": False,
                           "force_default_server": True, "forced_hosts": {}, "priorities": ["lobby"],
                           "max_players": 60, "tab_list": "GLOBAL_PING", "motd": "XDU private event"}],
        }
        (proxy / "config.yml").write_text(json.dumps(proxy_configuration, indent=2) + "\n")
        (temporary / "acceptance.json").write_text(json.dumps({"eula": "explicitly_accepted", "identity_mode": "offline_trusted_private", "admin_policy": "host_only", "impersonation_risk": "accepted_by_owner", "at_utc": datetime.now(timezone.utc).isoformat(), "scope": "local compatibility harness"}, indent=2) + "\n")
        os.rename(temporary, destination)
    except BaseException:
        shutil.rmtree(temporary)
        raise
    print(f"Prepared {destination.relative_to(ROOT)}; no servers started")


def compose_args(*arguments: str) -> list[str]:
    return ["docker", "compose", "-p", "xdu-compatibility", "-f", str(COMPOSE), *arguments]


def environment() -> dict[str, str]:
    return {**os.environ, "LOCAL_UID": str(os.getuid()), "LOCAL_GID": str(os.getgid())}


def query(service: str, command: str) -> str:
    result = subprocess.run(compose_args("exec", "-T", service, "python3", "-m", "raceops.rcon", "--json"),
                            input=command, text=True, capture_output=True, timeout=20, env=environment(), cwd=ROOT)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "RCON command failed")
    return json.loads(result.stdout)["response"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--accept-eula", action="store_true")
    sub.add_parser("up")
    sub.add_parser("stop")
    sub.add_parser("status")
    command = sub.add_parser("query")
    command.add_argument("service", choices=("race", "lobby"))
    command.add_argument("query")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.accept_eula)
        elif args.command == "query":
            print(query(args.service, args.query))
        elif args.command == "status":
            for service in ("lobby", "race"):
                print(f"{service}: {query(service, 'list uuids')}")
        else:
            if not (DATA / "acceptance.json").exists():
                raise ValueError("Run prepare with explicit EULA acceptance first")
            arguments = ("up", "--no-build", "--menu=false") if args.command == "up" else ("stop", "--timeout", "60")
            os.execvpe("docker", compose_args(*arguments), environment())
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"compat: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
