# Local deployment

## Scope and trust

This is a private-event system for Minecraft Java **26.2**, Sprint Racer **1.6.13**, BungeeCord **2096** and pinned Temurin Java **25**. Backends use the official vanilla JAR. Paper128 is retained only as a comparison artifact. The owner approved offline clients: names/offline UUIDs are organizer-supervised record keys, **not authentication**. No player has OP, tournament admin or proxy administrator permissions. Administration is host-only.

Default ingress is `127.0.0.1:25565`. Do not expose an offline network to the public Internet. On the event LAN, explicitly set `EVENT_BIND` to the event interface and configure the host firewall to admit only the trusted event network. Backends and RCON have no published ports. Docker and host access are trusted administrator capabilities.

## Prerequisites

- Docker with Compose v2 or later; Python 3.10+ and system curl on the host.
- Explicit deployment-owner acceptance of <https://www.minecraft.net/eula>.
- Permission for your activity under the map's included terms. Do not republish the world or resource pack. Original binaries, worlds, rosters and exports are Git-ignored.
- Minecraft **26.2** clients, using fixed event names. The required resource pack is served from the author's URL; pre-cache it in batches before the event. Its SHA-1 is locked in `config/versions.lock.json`.

## First setup

```sh
./scripts/fetch-assets
./scripts/prepare-template
./scripts/init-worlds --accept-eula
./scripts/up
```

`prepare-template` starts from the hashed release ZIP, applies hash-checked source patches and an event datapack, and records the resulting immutable template hash. It refuses an existing template. `init-worlds` refuses existing deployment directories and any template mounted by a running container, verifies three independent copies, installs instance provenance and records initialization completion. It never overwrites an existing world or accepts EULA implicitly.

`up` runs Compose in the foreground. Use a supervised terminal/process manager on the event host. It builds the control image, waits for real RCON/adapter readiness, then starts the proxy. Only that proxy publishes a port.

The default JVM heaps are conservative functional-test values. Copy `.env.example` to `.env` and tune `RACE_HEAP`, `LOBBY_HEAP`, `PROXY_HEAP` on the actual host. **No Docker memory or CPU ceilings are imposed.** The planned M4 Mac mini is not yet available; no 50-player capacity claim has been made. Set Docker Desktop's own VM allocation appropriately, leaving headroom for native memory and the host.

## Roster and presets

`config/event.yaml` and `config/presets.yaml` intentionally use JSON-compatible YAML; no third-party parser is required. The included five presets rotate six real stock Race tracks. Organizers can replace them with release-verified IDs, but must retain six explicit slots and revalidate the resulting tracks.

Copy `config/roster.example.json` into `config/rosters/round-1.json` through `round-5.json`. Each group A/B/C contains 1–17 entries of `{ "name": "FixedName", "uuid": "offline-uuid" }`. Generate the UUID from the exact case-sensitive name with `raceops.identity.offline_uuid`; the CLI rejects mismatches, duplicate UUIDs and case-ambiguous names. Names are fixed for the event and verified against the organizer's attendance list. A sample with empty groups is deliberately not startable.

Unresolved DNF/DNS, disconnection, incomplete GP and ties remain judge-review cases. Export preserves facts without inventing a final rank or external points. Read `docs/RULES.md` before the formal rehearsal.

## Commands

```sh
./scripts/racectl status
./scripts/racectl preset gp1 --round 1
# Players connect to proxy; route them using their exact loaded roster.
./scripts/route-roster --round 1
./scripts/racectl start
./scripts/racectl export --round 1
```

See `OPERATIONS.md` for safe stop, archive, reset, regrouping and recovery.

## Compatibility harness

For isolated upstream comparison, `./scripts/compat prepare --accept-eula`, build `docker build -f images/server/Dockerfile -t xdu-race-runtime:local .`, then `./scripts/compat up`. This creates a lobby, proxy and one **unpatched original** race world. Do not confuse it with the protected event deployment. `scripts/racectl --compat` only works if an explicitly prepared adapter copy has been installed for integration testing. The harness and event share localhost port25565; stop one before starting the other.

## Version changes and rebuilds

Never edit live NBT or overwrite an active world. A change to the patch manifest or adapter functions requires a newly prepared stopped template and fresh event world directories after all prior attempts have been archived. Preserve existing directories with an explicit operator-chosen backup name; do not use `down -v` as recovery. Historical archives remain immutable.

Do not refresh version tags during startup. Every downloaded artifact is checked against `config/versions.lock.json`. The Java image uses a fixed digest; Python packages in the image are pinned to available Ubuntu versions. A repository removing those versions causes a build failure, not a silent upgrade.
