# Local deployment

## Scope and trust

This is a private-event system for Minecraft Java **26.2**, Sprint Racer **1.6.13**, BungeeCord **2096** and pinned Temurin Java **25**. Backends use the official vanilla JAR. Paper128 is retained only as a comparison artifact. Offline names/UUIDs are organizer-supervised record keys, **not authentication**. No player has Minecraft OP or proxy administrator permissions. Race-world administration is host-only; the separate waiting room permits host-granted session operators to change lobby settings, never launch games.

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

`config/event.yaml` and `config/presets.yaml` contain JSON (despite their `.yaml` suffixes); no third-party parser is required. Set `grand_prix_rounds` to an integer from 1 through 7. The supplied `gp1`–`gp7` presets each contain six stock Race tracks in an explicit order. Organizers can replace their sequences with release-verified IDs, but must retain six slots.

Create `config/rosters/round-N.json` for each scheduled GP. Its `groups` object selects that GP's active worlds: include A/B for two groups, or A/B/C for three. **Omit unused C; do not supply an empty C array.** Each included group contains 1–17 entries of `{ "name": "FixedName", "uuid": "offline-uuid" }`. Generate UUIDs from exact case-sensitive names with `raceops.identity.offline_uuid`; duplicates, case-ambiguous names and UUID mismatches are rejected. Two groups accommodate at most 34 players; 50 need 17/17/16 across three groups.

The existing proxy, lobby and three race-world architecture remains unchanged. Group selection comes from the round roster, not attendance polling or `event.yaml.groups`. `preset` pins the selected groups in `volumes/control/groups.json` before sending requests; start, routing, stop, reset and default exports use that membership until another preset is loaded. Keep that control file with the deployment data. Changing from two groups to three or back requires all previous and next worlds reachable and IDLE after archive/reset. An omitted world's state and results are untouched. Editing a roster after loading it does not change the attempt; routing rejects a changed roster.

For read-only inspection or historical export of a different group count, use `./scripts/racectl --groups 3 status` or `./scripts/racectl --groups 3 export --round N --attempt ID` (substitute 2 when appropriate). This does not change the pinned active groups.

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

## Native shared waiting room

New event installations copy the verified Sprint Racer template into a separate lobby world, preserving the full map, rooms, native boundary, item containers, villagers and movement props. Race, practice, GP and editor entrypoints are disabled only in this waiting-world copy. All three race worlds and the original template are unchanged.

To replace an existing flat lobby, first move visitors to safe race-world lobbies or disconnect them, then run:

```sh
docker compose -p xdu-event stop --timeout 60 lobby
./scripts/prepare-lobby
docker compose -p xdu-event start lobby
```

The installer refuses a running lobby or mounted template, verifies the source template hash, and preserves the previous world as `volumes/event/lobby/world-before-waiting-*`. Do not delete that backup until the new waiting room is accepted. New installations use `init-worlds`; no separate upgrade step is required.

Ordinary visitors can use props but cannot change shared settings. After verifying the connected person's identity, the host may run:

```sh
./scripts/lobby-operator grant ExactPlayerName
./scripts/lobby-operator revoke ExactPlayerName
```

This grants only the `xdu_lobby_operator` session tag, not OP. It is cleared on every native join (including proxy return) and server reload/restart. Access-policy changes, AI admission, saved-settings restoration and all game launch remain blocked even for these operators. Other lobby settings affect only the waiting world, never race settings. Offline identity supervision remains essential.


## Compatibility harness

For isolated upstream comparison, `./scripts/compat prepare --accept-eula`, build `docker build -f images/server/Dockerfile -t xdu-race-runtime:local .`, then `./scripts/compat up`. This creates a lobby, proxy and one **unpatched original** race world. Do not confuse it with the protected event deployment. `scripts/racectl --compat` only works if an explicitly prepared adapter copy has been installed for integration testing. The harness and event share localhost port25565; stop one before starting the other.

## Version changes and rebuilds

Never edit live NBT or overwrite an active world. A change to the patch manifest or adapter functions requires a newly prepared stopped template and fresh event world directories after all prior attempts have been archived. Preserve existing directories with an explicit operator-chosen backup name; do not use `down -v` as recovery. Historical archives remain immutable.

Do not refresh version tags during startup. Every downloaded artifact is checked against `config/versions.lock.json`. The Java image uses a fixed digest; Python packages in the image are pinned to available Ubuntu versions. A repository removing those versions causes a build failure, not a silent upgrade.
