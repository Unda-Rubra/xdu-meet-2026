# Sprint Racer event agent guide

Current contract: **one main lobby, live QQ registration, random grouping at each GP start, per-track synchronization, post-award local token, explicit manual Feishu upload**. The old preassigned seven-round rosters and auto-uploader have been retired. Follow `docs/OPERATIONS.md` for actions and `docs/RULES.md` for scoring/identity policy; do not revive old fixed-track presets, schedule exports, automatic cloud forwarding or player-name signup.

## Safety

- Keep the pinned author-tagged Sprint Racer 1.6.14 world, Mario Kart Track Pack and vanilla Minecraft 26.3 servers; do not replace game physics or item handlers with a mock or another server implementation.
- Login is verified by the online-mode BungeeCord proxy using pinned authlib-injector and the configured Yggdrasil service. The native vanilla backends must remain offline-mode and private; they compute name-based UUIDs internally. Keep the authenticated proxy UUID distinct in the immutable roster and QQ registry. QQ is not login authentication. Console roles are bound to the current authenticated proxy session, never a QQ or backend UUID.
- The sole main lobby hosts the native GP settings editor. Do not allow racers into race-world lobbies except the built-in award phase. Administrator commentators are always spectators and never counted.
- Each active A/B/C backend must finish a track before any active backend advances. The archived attempt and token are generated only after final ceremonies. Missing evidence blocks publication; never infer a valid result from a timer or UI banner.
- Background service work is local only. Feishu receives actual QQ attendance, nickname, group and results **only** when `./scripts/meet-service upload --token ...` is invoked. First upload binds that token to the Feishu selected round; retries cannot rebind it. An unuploaded token is a warmup.
- `用户／QQ号` is the business primary field. Feishu `record_id` remains the internal link key. Refuse duplicate or unknown QQ instead of guessing from nickname.
- Field updates preserve formula result types and existing palettes/formatting. If the OpenAPI cannot round-trip a UI-only display property, use the native Base editor or stop; do not overwrite it with defaults.
- Backups before any world reset or Base deletion. The one-time pre-cutover Base backup and stopped-world archive are kept under the ignored `volumes/control` and `downloads` directories. Never commit local credentials, raw QQ registrations, test receipts or downloaded world content.

## Verification levels

Python regression tests prove retry/identity/barrier logic only. Native-client proofs require the actual client, proxy and world. A two-player local GP cannot prove production 51-player throughput or QQ ownership. Quote each level precisely; preserve complete archives but label any forced progression or synthetic data.
