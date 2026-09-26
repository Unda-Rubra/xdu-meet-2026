# XDU Sprint Racer event service

One native Sprint Racer 1.6.14 main lobby, the creator-linked Mario Kart Track Pack (27 imported tracks), three private A/B/C race backends and BungeeCord 2096. Minecraft 26.3 players authenticate through the user-specified Yggdrasil service via the pinned authlib-injector on the **online-mode proxy**; vanilla backends remain private/offline behind it. The local coordinator handles QQ admission, random per-GP grouping, synchronized track changes, awards, archiving, and **explicit token-based Feishu publication**.

Quick operator path:

1. Start the proxy, game worlds and `./scripts/meet-service serve` (see [setup](docs/SETUP.md)).
2. Console-grant commentator roles with `./scripts/racectl admin NAME A|B|C`. Players register with `/qq 签到QQ号` in the sole main lobby.
3. Set the native GP map pool, items and laps in the main lobby; start with `/gpstart` or `./scripts/racectl start`.
4. After every active group completes each track, the coordinator releases the next one together. After final awards the players return to the main lobby and the local service issues a result token.
5. Set `比赛控制／当前轮次` in Feishu and **explicitly** run `./scripts/meet-service upload --token TOKEN` to count that race. Do not upload warmups.

现场指令、主机脚本、飞书查看及抽奖见[一页速查](docs/QUICK_REFERENCE.md)；完整流程见[活动规则](docs/RULES.md)、[详细操作](docs/OPERATIONS.md)和[架构](docs/IMPLEMENTATION_GRAPH.md)。QQ 仍是签到键，不是登录认证；代理认证 UUID 和原版世界 UUID 不同。比赛后端与 RCON 不对玩家开放。
