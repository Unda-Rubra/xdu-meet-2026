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

## Local Feishu service

`scripts/meet-service` replaces the four native workflows and imports game results. It runs on the same host as the existing Docker/BungeeCord deployment, reuses `raceops` and the official Feishu Python SDK, and never reads the personal `lark-cli` token cache. Native workflow quota is not used; normal OpenAPI permissions and rate limits still apply.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./scripts/meet-service setup-app
```

`setup-app` requests a dedicated application using the official device enrollment flow. Complete its verification URL; the returned App ID/Secret are saved directly to `secrets/feishu-app.json` with mode 0600 and never printed. It does not change the CLI's existing application/account. Alternatively, create an enterprise self-built application yourself and write that file as JSON with `app_id` and `app_secret`, then `chmod 600 secrets/feishu-app.json`.

Grant application-identity permission `bitable:app`, publish/approve the application permissions as required by the tenant, and add the application to the target Base with edit access. Advanced Base permissions also apply. `config/feishu.json` contains the real Base token and table IDs, not an OAuth token or wiki node token. Do not paste secrets into this tracked configuration.

`比赛控制／当前轮次` must be a single-select field whose options reference `SprintRacer积分倍率／轮次`, not a free number or a second independent option list. Configure that native option source before running migration on a new Base; the existing deployment already has it. The service reads the selected labels `第1轮`–`第7轮`; clearing the selection prevents binding a new result, while previously bound retries retain their saved round.

For the existing deployment, native workflows have already been backed up and deleted. Run `./scripts/meet-service doctor` to verify the dedicated app; `./scripts/meet-service migrate` applies the idempotent service-only schema migration. The cutover backs up and removes the old manual score rows and unbound rehearsal imports, replaces score-input columns with formulas and raw service fields, and removes grouping/cleanup checkboxes from Feishu. Recovery backups remain in `volumes/control/`.

```sh
# Generate all seven rounds initially; reruns only fill new participants/missing rounds.
./scripts/group-participants
# Start the completed-attempt forwarding daemon.
./scripts/meet-service serve
```

The grouping script automatically uses the authenticated local service endpoint if it is running, otherwise it executes directly. Existing groups and group count are preserved. All provisioned backends must be IDLE. A failed partial grouping retains its exact plan; use `./scripts/meet-service resume` with the daemon stopped or authenticated `POST /resume`. Never edit the saved SQLite plan to force progress.

The authoritative eligibility column is `用户／能够参与小游戏（最终结果）`, not the raw opt-out checkbox. Its current user-owned formula combines attendance, nonempty game name and opt-out; do not overwrite the formula in code or independently recreate its policy. The SDK returns formula booleans wrapped as values such as `["TRUE"]`/`["FALSE"]`; the service decodes those explicitly and never treats nonempty `"FALSE"` as true. Missing/invalid game identity is still rejected separately at roster handoff.

Preparation records are only a one-to-one diagnostic/display layer. `纳入首批` and the write-only `已保存` flag have been retired. The read-only `分组状态` derives current completeness from actual seven-round associations and validation, not a past script invocation. `分组校验` warns about membership conflicts; `分组准备校验` checks that exactly one preparation record exists; `关联校验` checks that preparation-to-user linking is unique. Field tooltips document causes and fixes. `当前轮次编号` is retained for the dashboard. Descriptions labeled `服务维护，禁止手动修改` are operator guidance, not a new permission ACL.

The retired `用户序号` only duplicated the preparation record's user identity; `准备记录` and `关联用户` remain the authoritative pairing. The score table's redundant `参赛人数` formula was replaced by its existing `参赛人数快照` source. Keep original signup/contact fields, provenance, links, diagnostic formulas, option sources and dashboard inputs even when the service does not write them. `分组准备名单／参赛状态` is the owner's lookup of final participation; migration preserves it and derives grouping completeness directly from the final source, not its display text. The `测试` marker belongs only to users, not preparation records.

Migration keeps existing formula result types, precision, percentages and numeric formats; descriptions do not authorize a format reset. Formula single-/multi-select palettes and dynamic option sources are UI-only metadata that OpenAPI cannot safely round-trip. Updates touching these formats fail before the field write with an instruction to use the native Base editor. Do not strip `property.type` or recreate a field to bypass that guard. Keep its field ID, source options, colors and fallback option intact.

Feishu `比赛控制` contains one row. Click its `当前轮次` cell and select `第1轮`–`第7轮` from the dropdown sourced from `SprintRacer积分倍率／轮次`. Keep it unchanged until `最近上传轮次`/`最近上传尝试` show the expected successful attempt, then select the next round yourself. Game preset round numbers remain audit information only. The daemon checks completion every 30 seconds, reads durable backend history so reset/missed polls do not discard finished attempts, and exports only when all enabled groups are frozen `GP_FINISHED`. No intermediate result is automatically uploaded. Persisted retry bindings never change when you choose a different current round.

`比赛原始成绩` stores per-track facts; `轮次上传记录` stores upload receipts/errors; `SprintRacer计分表` stores service evidence and Feishu-computed rank/points. A round's `已发布批次` pointer is advanced only after record-content readback. Old rankings remain visible if upload fails or a replay is invalid. `用户／当前轮排名` shows the selected round; `用户／总排名` ranks the undropped total; `用户／最终排名` ranks `最终总得分` after dropping the lowest scored round. Formula refresh is asynchronous: wait for the canvas to settle after navigation or remote changes rather than reading a stale first paint. During a GP, `上传状态` explicitly says it is waiting for all enabled groups. Unused C is not an export dependency in A/B mode.

The daemon binds to 127.0.0.1:8765; every endpoint except `/health` requires `Authorization: Bearer …` from `secrets/meet-service-token` (0600). Browser-origin operations are rejected. `GET /status` reports uploads/errors. POST `/import-results`, `/group`, `/clear`, `/resume` take `{}`; `/roster` takes `{"round":1}`; `/game` accepts only enumerated game commands. There is no arbitrary console endpoint, no personal OAuth cache and no Feishu workflow trigger. Supervise `serve` on the host; after machine restart run it again. Back up SQLite consistently, including committed upload bindings.

With the daemon stopped, `./scripts/meet-service import-results --archives-only` retries pending/new complete archives. Old rehearsal attempts are deliberately ignored unless explicitly bound using `./scripts/meet-service upload-attempt --attempt EVENT/ATTEMPT --round N`. Binding is immutable. Multiple completed attempts found after downtime require this explicit command; never guess their destination from archive order or bind them all to today's round.

### Separate test-data maintenance

Stop the daemon before maintenance. Each command previews by default; `--apply` performs the requested operation. Filling creates only clearly marked mock users, never scores. Group them using the normal grouping script. Cleanup defaults to exactly the fixture record IDs tracked locally; it does not infer tests from nicknames.

Fixtures populate the inputs required by the current participation formula (including `参会情况=线下参会`); they do not write the computed final result. If the owner changes that formula, update the fixture input data deliberately rather than bypassing the formula.

```sh
./scripts/meet-fixtures fill-users --count 4        # preview
./scripts/meet-fixtures fill-users --count 4 --apply
./scripts/meet-fixtures clean-users --apply        # only this script's fixtures
./scripts/meet-fixtures clean-users --all-test-users # preview all explicit 测试 users
./scripts/meet-fixtures clear-groups --apply       # clear associations only, preserve results
```

Deleting users with imported results is refused to preserve result identities. `clean-users` writes a recovery backup before deletion. After cleanup, rerun the grouping script to adopt preserved memberships; it does not shuffle established users. There are no cleanup/mock/grouping action controls in Feishu.
