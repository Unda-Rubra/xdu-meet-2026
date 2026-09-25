# XDU Sprint Racer event service

One native Sprint Racer 1.6.14 main lobby, the creator-linked Mario Kart Track Pack (27 imported tracks), three private A/B/C race backends and BungeeCord 2096. Native Minecraft 26.3 gameplay is preserved; the local coordinator handles QQ admission, random per-GP grouping, synchronized track changes, awards, archiving, and **explicit token-based Feishu publication**.

Quick operator path:

1. Start the proxy, game worlds and `./scripts/meet-service serve` (see [setup](docs/SETUP.md)).
2. Console-grant commentator roles with `./scripts/racectl admin NAME A|B|C`. Players register with `/qq 签到QQ号` in the sole main lobby.
3. Set the native GP map pool, items and laps in the main lobby; start with `/gpstart` or `./scripts/racectl start`.
4. After every active group completes each track, the coordinator releases the next one together. After final awards the players return to the main lobby and the local service issues a result token.
5. Set `比赛控制／当前轮次` in Feishu and **explicitly** run `./scripts/meet-service upload --token TOKEN` to count that race. Do not upload warmups.

See [event rules](docs/RULES.md), [field/command operations](docs/OPERATIONS.md) and [architecture](docs/IMPLEMENTATION_GRAPH.md). QQ is a supervised, self-declared identifier, not authentication. Only the proxy may be reachable by participants; never expose backend or RCON ports.
