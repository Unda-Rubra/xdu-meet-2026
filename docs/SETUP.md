# Deployment and local service

Use the pinned Sprint Racer 1.6.13 world, Minecraft 26.2 client/server, Java 25 and BungeeCord 2096 assets in `config/versions.lock.json`. Do not replace the native race worlds with Paper or approximate the game mechanics.

```sh
./scripts/fetch-assets
./scripts/prepare-template
./scripts/build-identity
./scripts/init-worlds --accept-eula
export LOCAL_UID=$(id -u) LOCAL_GID=$(id -g)
docker compose -p xdu-event up --build -d
.venv/bin/python -m pip install -r requirements.txt
```

`init-worlds` creates one native main lobby and private race-a/b/c backends; it refuses to overwrite any existing event. The native GP option signs remain available in the main lobby; the unrelated SprintRacer `ADMIN MENU` (restart/force-ready controls) is removed there. The race worlds are not additional waiting lobbies. Set `EVENT_BIND` in the ignored local `.env` to the host's current **private LAN IPv4** for remote players, never a public address. This exposes only proxy TCP 25565 and the read-only locked resource pack on TCP 25566; never expose backend game/RCON ports. `scripts/up` refreshes all four world URLs when the LAN address changes. Restart worlds after changing the URL.

## QQ identity and administrator roles

The proxy plugin is built reproducibly from `plugins/identity/src/XduIdentity.java` against the pinned BungeeCord jar. QQ registrations and current connections are kept in `volumes/event/proxy/plugins/XduIdentity/`. An unregistered non-admin sees a persistent red `/qq XXX` title; native idle subtitles are suppressed until QQ is confirmed. `/qq <signup QQ>` displays private clickable green `[是]` and red `[不是]` choices. No draft is persisted until `[是]`; a confirmed QQ cannot be overwritten with `/qq`. Duplicate QQ, malformed identifiers and unauthorized backend entry are rejected. This is supervised offline mode, not proof of QQ or Microsoft account ownership.

Grant commentator/OP for the **current connected session** from the trusted host using `./scripts/racectl admin Name A` (or B/C). A trusted native `xdu_commentary_A/B/C` tag may select the default group but cannot grant permission by itself. Roles and OP must be reapproved by the host after a reconnect; OP is revoked when the session leaves a server or disconnects. Commentators are spectators in race worlds and excluded from rosters and scoring. Player-supplied names or QQ values never grant permissions. Offline names can still be impersonated on a LAN: only trusted supervised users should receive OP; do not treat QQ as authentication. Registration repair is console-only, with the player disconnected and no active GP.

The previous third-party short URL redirected through Mediafire and did not work reliably on other machines. The event now hosts the pinned `downloads/resources-1.6.13.zip` on `http://<EVENT_BIND>:25566/pack.zip`; startup verifies its SHA-1 and SHA-256 against `config/versions.lock.json` and serves only that path. Clients use the same URL and locked SHA-1 from all four worlds. If remote clients cannot download, confirm Mac firewall permits TCP 25566 on the private LAN; a working game port 25565 alone is insufficient.

## Feishu configuration

`config/feishu.json` references a private dedicated app credential file, `volumes/control/manual-meet.sqlite3`, and the live table IDs. Credentials are ignored by Git; never replace them with an interactive CLI app's credentials.

```sh
./scripts/meet-service setup-app
./scripts/meet-service doctor
./scripts/meet-service migrate
```

Migration takes a complete metadata/record backup before removing the old seven-round grouping/preparation/raw-track structures. User identity is the QQ primary field; internal Feishu `record_id` links remain stable. Minecraft names are not requested at signup. Preserve the required QQ question in the existing signup form when changing its backing field.

Formula/description updates preserve existing display properties. OpenAPI updates refuse UI-only select palettes rather than resetting their colors or result type. The already migrated Base includes current attendance/group, nickname, points, rank, round-multiplier and upload-receipt fields. `比赛控制／当前轮次` is selected only when manually publishing a token; it does not configure or start gameplay.

## Local synchronization and capture

```sh
./scripts/meet-service serve
```

This daemon has no HTTP listener and does not periodically access Feishu. It processes explicit in-game `/gpstart` requests, synchronizes native per-track barriers, maintains commentator roles, returns players after awards, and archives finished GP snapshots. Use the host's process supervisor for production. Keep it running through all tracks and awards.

Each start reads the actual online registered non-admins, randomly balances A/B for 2–20 players or A/B/C for 21–51, and captures the current native lobby settings. It transfers all 50 native GP configuration slots, map pools, item/lap settings, cheats/custom AI settings and saved-preset bank/round-sequence storage. It does not impose a novice/intermediate/expert recipe. Each participant's QQ, name and UUID are immutable inside that attempt. Backends must acknowledge actual player admission before launch; resource-pack loading is not considered completed merely because the proxy selected a server.

A group that finishes early stays behind the current-track barrier. Once all enabled groups reach the same barrier, an idempotent persisted release decision arms a shared countdown. The last barrier leads to the native awards ceremony. Only post-ceremony frozen snapshots receive a complete archive token.

## Manual publication

```sh
./scripts/meet-service tokens
./scripts/meet-service upload --token TOKEN
```

Read-only inspection and local gameplay do not publish attendance. Upload binds the token to the then-selected Feishu round before any cloud write. Retries retain that binding and use idempotent keys. QQ must identify exactly one signup record; unknown/duplicate QQ blocks publication. Nicknames, actual groups and attendance arrive with the explicitly uploaded results. A different valid token may replace the round's published batch; it does not add the two attempts together. Warmups need no special mode: simply do not upload their tokens.

Archives contain native evidence and checksums; SQLite retains tokens, publication plans and operator state. Back up both, plus the proxy identity registry and worlds. Never hand-edit state JSON, archive files or published-batch pointers to bypass validation.

## Verification

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The regression suite covers QQ ambiguity, token integrity, explicit publication, lost-response recovery, immutable first-round binding, cross-server barrier progression and protected field formats. Native-client acceptance is recorded in `docs/verification/`; synthetic or admin-forced progress is labeled as such and is not a capacity test. See `docs/OPERATIONS.md` for the live command sequence.
