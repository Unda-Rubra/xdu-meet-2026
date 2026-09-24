"""Read-only command readiness, not merely an open game/RCON socket."""
import argparse
from pathlib import Path
import sys

from .rcon import Rcon, RconError
from .snbt import response_value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lobby", action="store_true")
    args = parser.parse_args()
    try:
        password = Path("/run/secrets/rcon").read_text().strip()
        with Rcon("127.0.0.1", 25575, password, timeout=5) as client:
            if args.lobby:
                response = client.command("list")
                if not response.startswith("There are ") or " players online:" not in response:
                    raise ValueError("Unexpected lobby readiness response")
            else:
                version = response_value(client.command("data get storage xdu_race:state current.adapter_version"))
                settings = response_value(client.command("data get storage xdu_race:config settings"))
                if version != "1.0.0" or not isinstance(settings, dict) or not settings:
                    raise ValueError("Adapter or settings contract not ready")
        return 0
    except (OSError, ValueError, RconError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
