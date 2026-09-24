# Sprint Racer 三实例赛事系统：Agent 实施指导

> 目标：BungeeCord 大厅 + 三个独立 Sprint Racer 后端；Docker 一键启动；从同一模板世界生成 A/B/C；管理员独占设置和比赛控制；一条主机指令向三实例装载一套六赛道大奖赛预设、统一开赛/退出；全程零 AI；随时导出只读比赛快照用于留档与人工录入飞书。
>
> 本文面向接手开发的 Agent。先按“核对与决策”取证，再实施。不要把本文出现的函数名当作跨版本稳定 API。源码观察基于官方仓库 `jarrodmmoore/Sprint-Racer-Dev` 的 commit `049f3821dede74e22b4484265dfe907cc2d34453`（2026-09-23，`sr_code/pack.mcmeta` 要求格式 121），仅供定位。选定世界发行版为 2026-07-13 的 Sprint Racer 1.6.13，CurseForge file ID `8422262`，对应 Minecraft 26.2（数据包格式 107.1）。两者不匹配，必须对发行 ZIP 重新取证、计算 hash，并以发行包为补丁真值；禁止直接复制开发仓库的数据包到 26.2。

## 1. 交付定义与硬约束

交付 Docker Compose 项目、可复制的模板世界制作流程、可复现的 Sprint Racer 最小补丁、管理员权限配置、`racectl` 命令行工具、快照导出器、维护文档和实际联机验证记录。不要开发常驻中央控制台或 Web 后台；`racectl` 是操作主机上运行一次就结束的命令。

- 服务：`proxy`（BungeeCord）、`lobby`、`race-a`、`race-b`、`race-c`。对外仅暴露代理入口；后端端口仅 Compose 网络可见。
- 后端：每个独立 Java 进程、独立完整世界和持久化目录；三份世界必须从**停止状态下的**同一个 `template-world/` 复制生成。不要把同一个世界目录同时挂给三服。
- 预设：每个 preset 恰好六个**确定的赛道标识和顺序**；每轮大奖赛固定一套预设，共计划五轮、每组总计 30 场地图赛，三组共 90 次地图赛实例。原生 Grand Prix 可配置序列长度，并非固定六场；本活动主动选择六场，不实现“五场截断”或额外循环。其余比赛设置固定于模板。预设版本、模板 hash、Sprint Racer 版本一并记录。
- 零 AI：模板、预设加载、每图开赛、重连和重启恢复都必须保持 AI 禁用且 AI 参赛数量为 0；关闭人数不足时自动补 AI 的路径。出现 AI 参赛者属于配置/运行错误，禁止开始下一图并保留证据；不可默默过滤 AI 后把结果标为有效，也不可用广泛杀实体命令破坏道具或赛道实体。
- 权限与身份：采用用户明确选择的**私有可信活动网络、允许离线客户端、仅宿主机管理**。代理关闭正版认证并转发离线 UUID；离线 UUID/名字可冒用，只是成绩键，不是身份证明，由组织者核验人与名字映射并接受该风险。普通玩家可比赛/用道具，但不能改变公共设置或生命周期。所有管理走宿主机控制台/RCON；不从离线 UUID/名字授予 OP、`tournament_admin`、原生 `admin` 或代理管理权限。禁止把本模式无保护地暴露到公网。
- 控制：`racectl preset <id> --round N`、`racectl start`、`racectl stop --reason ...`、`racectl export [--round N] [--attempt ID]`、`racectl status`，以及有归档门禁的 `racectl reset --reason ...`。一次命令对三服执行并报告各服确认状态。`stop` 指安全退出大奖赛并留档，绝非直接杀容器。
- 导出：JSON + CSV，以一份 manifest 收集三实例结果；保留每名选手的 UUID、当时游戏名、组、赛次、完赛状态、组内名次等。导出操作不向游戏世界写入任何状态，不触发游戏推进；重复导出不产生重复成绩。
- 赛事外部计分：每轮大奖赛结束，以其**六张地图累计形成的组内大奖赛总名次**代入飞书的组内名次曲线，再乘本轮倍率；每人一轮只获得一笔外部积分。Sprint Racer 的 `points` 只可作为确定大奖赛名次的原始依据，**不可直接作为本活动积分**。未完成整轮大奖赛、单张地图 DNF、并列的处理须在彩排前确定并写入规则；计分、抽奖、飞书写入不在此项目首期范围。

## 2. 已核实的源码锚点与必须再核实的内容

| 主题 | 当前源码位置或状态 | Agent 行动 |
| --- | --- | --- |
| 原生 Admin Mode | `admin_mode.mcfunction`、`admin_player_list.mcfunction`、`bootup_delayed.mcfunction` 和 `join.mcfunction` 管理原生 admin 标签 | 模板开启 Admin Mode，但所有客户端都没有管理身份；阻断按离线名字/UUID授予标签，重连时清理遗留授权。主机控制命令使用独立受信 gate，不借假玩家冒充 admin。 |
| 大厅自动开始 | `sr_code/.../game_logic/0/_initialize_for_real.mcfunction` 根据 `readyup` 进入 ready 状态；`gl0_main_ready.mcfunction` 在倒计时结束时进入下一赛道；参考源码 `_initialize_skip_to_next.mcfunction` 还会直接调用赛道开始 | 阻断投票/红绿灯和跳过倒计时路径；授权 gate 放在实际赛道启动入口，不只改 UI 或倒计时。第 1 图需主机授权，第 2–6 图只在同一个已授权 GP 内自动推进，第 7 图一律拒绝。 |
| 完赛名次 | `sr_code/.../game_logic/1/player_finish.mcfunction` 设置 `finished/finishPos` 和待结算 `addPoints`；`racePosDisplay` 是显示排名 | 在完赛事件中立即捕获 raw 名次和当图获授分数，结算后另记累计原生分数；仅按固定 UUID 名册认定选手，不能因合法完赛者切到旁观模式而丢弃记录。验证零 AI；不把在线 HUD 当历史数据库。 |
| 原生大奖赛 | `sr_code/.../game_logic/0/grand_prix_round_start.mcfunction` 按 GP 序列选赛道；参考源码缺失指定赛道时可能随机回退；Save State 会恢复大量非赛道设置 | 查清发行版六场序列、唯一赛道匹配、结算/颁奖/退出边界。用验证过的原生写入路径装载序列；禁止随机回退、完整 Save State 恢复及跳过合法性校验的 NBT 写入。 |
| 发布与许可 | CurseForge 标记为 All Rights Reserved；GitHub 公开世界内容不等于开放再分发授权 | 代码仓库存补丁及应用脚本，不直接提交原版世界、音频/资源包；组织活动和资源再分发范围先核实授权。 |

源码参考：<https://github.com/jarrodmmoore/Sprint-Racer-Dev>；版本与兼容性：<https://www.curseforge.com/minecraft/worlds/sprint-racer>。官方说明其兼容 BungeeCord、不兼容 Multiverse，并提供公共服务器 Admin Mode。公开源码 HEAD 与发行 zip 不保证完全一致，Agent 必须在锁定版本后重复核查。

**赛程边界（已确定）：** 每轮大奖赛完整跑六张地图，轮内三组成员不变；A/B/C 使用同一六图预设。第 1 轮结束、三服冻结成绩且宿主机成功留档后，玩家回大厅重新随机分成下一轮 A/B/C，再显式复位并加载下一个预设。计划共五轮大奖赛、每组 30 张地图赛；赛道是否跨 GP 重复由实际预设决定，不要求 30 张互异地图。原生六图之间自动推进是预期行为；必须确认第六图完成结算后冻结成绩，关闭循环，绝不误开第七图。外部积分按**大奖赛总名次每轮计算一次**。全程无 AI；测试平分、DNF、完赛后结算前离线、掉线重连与全员离线。若原生积分不能稳定代表真人总排名，保留原始值及差异，并按彩排前公开的固定补充规则裁定，不可临时排序。

## 3. 建议的项目布局

```text
race-event/
  compose.yaml
  .env.example
  config/proxy/                 # 固定版 BungeeCord 配置和插件
  config/lobby/                 # 大厅服务配置
  config/presets.yaml           # 唯一预设真值源：id -> 六个赛道 ID
  config/event.yaml             # 离线私有活动、仅宿主机管理、待裁定政策
  config/versions.lock.json     # 下载身份、版本、文件 hash、镜像 digest
  config/rosters/               # 每轮固定 UUID 分组；真实名单不提交
  template-world/               # 用户本地准备，gitignore
  patches/                      # 版本化 datapack 补丁、构建脚本
  images/                       # Dockerfile、固定版本说明
  scripts/init-worlds           # 克隆模板，仅在初始化时执行
  scripts/racectl               # 控制命令
  scripts/export-results        # 导出器
  volumes/                      # 三服与代理/大厅数据，gitignore
  exports/                      # 留档产物，gitignore
  docs/SETUP.md
  docs/OPERATIONS.md
  tests/
```

固定世界 Sprint Racer 1.6.13 / **原版 Minecraft 26.2 服务端**、BungeeCord build2096、Java25，制品见 `config/versions.lock.json`。用户批准离线身份后无需认证UUID转发：代理 `online_mode:false`、`ip_forward:false`，原版后端 `online-mode=false`，同名依照 OfflinePlayer:name 独立推导同一UUID；已通过两个真实26.2客户端的登录/换服/重连验证，但不认证真实玩家。Paper128保留为对照制品，不再用于部署；其默认RCON输出有缩略行为。默认代理仅绑定localhost；活动网络开放须配置防火墙，后端/RCON不发布端口。所有客户端无OP/管理标签/代理管理组。资源包统一URL、required、SHA-1。原版运行也出现地图原生ItemFrame无效位置日志，不得把该问题误归因给Paper或用隐藏日志冒充修复。

`init-worlds` 必须检查模板路径、必要 datapacks、`level.dat`、补丁版本和目录非空；只在目标世界不存在时复制，已存在则拒绝覆盖。服务端运行时禁止模板复制。保留服务端自己的 `server.properties`、日志和玩家数据；模板内赛前管理配置可以复制，实际游戏运行产生的赛次状态不能当作新的模板。三容器健康检查应以服务端真正接受控制命令/状态探针为准，而不只是 TCP 端口开放。

## 4. 权限与状态机补丁

先绘制所有会改变公共状态的入口清单：大厅选项牌/书、Save State 室、赛道选择、Grand Prix 编辑、红绿灯/ready、开始、暂停/取消/终止、Free Roam 退出、投票和原生隐藏管理员菜单。逐项记录触发 function、调用链、原生 Admin Mode 是否已拦截、补丁位置与测试结果。**权限检查应放在实际状态变更函数入口**；移走一个 UI 物品不足以构成安全锁。

赛事状态存在独立 namespace 的 storage/scoreboard：`IDLE → PRESET_LOADED → ARMED → RUNNING`；第 1–5 图结束经 `BETWEEN_TRACKS → RUNNING` 进入下一图，第 6 图结算后到 `GP_FINISHED`；另有 `STOPPED`、`ERROR`。包含 `event_id`、`preset_id`、`preset_hash`、`grand_prix_round`（1–5）、`track_index`（1–6）、`attempt_id`、`operation_id`、`boot_id`、`revision`。**不存在由 export 写入的世界内 EXPORTED 状态**；导出回执仅存宿主机。显式 `reset` 必须核对三服均已安全结束/停止、当前 attempt 留档完成且 hash 匹配；运行中或任一服不可达时拒绝。复位不删除历史成绩，下一次尝试使用新 `attempt_id`。重复 start 对同一 event/round/attempt 不重启或清分；`operation_id` 用于请求去重，不能替代语义幂等检查。只有受信命令生成的 gate 可启动首图；轮内自动推进也须验证六图边界、固定名单、设置摘要和零 AI。普通玩家不能绕过 gate。`stop` 默认拒绝运行中退出；必要时 `--force --reason ...` 先关闭继续启动的 gate、保存一致快照，再调用已验证适用于当前阶段的原生退出路径。无法留档或安全退出则报告并停止破坏性后续操作，绝不猜测 reset 命令或杀容器。

导出、stop、reset 是三个不同动作。宿主机保存控制审计与导出回执，不代替后端实际赛事状态；控制器/服务端重启后必须读取真实状态并核对当前 attempt。中途重启后的持久化结果可能落后于崩溃前内存；无法证明连续性的 attempt 进入 ERROR/待裁定，禁止自动恢复计分或悄悄重赛。比赛途中从其他组加入者不能成为本轮参赛者；只允许原名册 UUID 回到自己的组，管理员旁观不进入比赛名单。

控制台指令走 Docker exec 调用容器本地 RCON，由本项目 namespace 的受信入口消费；任何客户端触发公共状态变更都必须拒绝。不要把控制台假玩家 `@s[tag=tournament_admin]` 当权限证明，也不允许离线 UUID 白名单变成管理身份。禁止公开 trigger/function 自授标签；重连清理遗留 admin/tournament_admin，OP列表与代理管理组保持空，管理仅通过宿主机。

## 5. 六赛道预设与三服批量指令

预设建议用可审查 YAML：

```yaml
presets:
  newcomers_a:
    description: "新人场 A"
    tracks: [track_id_1, track_id_2, track_id_3, track_id_4, track_id_5, track_id_6]
```

上面 ID 仅为说明，实际配置不得包含占位符。必须从**锁定发行包的实际赛道注册表**验证每项为已安装、启用的 Race 赛道，并验证每个 GP 槽位唯一解析、原生 GP 长度为 6、循环关闭。缺失/歧义赛道必须拒绝，禁止原生随机回退。装载只改变六个赛道及顺序，保留模板圈数、道具、赛种和其他公共设置；AI 固定禁用且实际数量为 0。不得使用完整 Save State loader 冒充 tracks-only；每个槽位也不能夹带会改设置的 Save State 或未经核对的 modifier。装载后、每图启动前回读真实序列和固定设置摘要。绝不在世界运行时从宿主机编辑 `level.dat` 或已加载区块文件。

`racectl` 工作流：

1. 获取本地主机互斥锁，持久化操作 ID、event/round/attempt、命令参数摘要、操作者、UTC 时间和预期状态；敏感名单/密钥不进入公共日志。
2. 对 A/B/C 只读检查命令探针、赛事状态、实际 preset/settings hash、地图阶段、固定 UUID 名册与在线集合、零 AI；名单不得跨组重复，不符合前置条件立即报错。
3. `preset` 依次下发同一六图配置并逐服回读原生序列和固定设置摘要。任一失败记录逐服结果和宿主机协调错误，禁止 start；不可假称已给不可达服务器写入 ERROR。按明确的状态/操作记录修复重试，不自动回滚世界文件。
4. `start` 先在三服准备并核对确认，再下发开始，回读实际开始状态和时间。这不是跨进程原子事务，也不保证同一 tick；允许偏差和彩排超限处理须提前固定。部分成功时阻断后续操作，按 stop/归档/新 attempt 重开流程处理；不可自动复位已经产生的成绩。
5. `stop` 先核对三服阶段，再按前述关闭 gate、快照留档、原生受控退出顺序执行；显示逐服已确认/失败/未知，命令部分失败返回非零退出码。严禁把已结束的 A 服复位而 B/C 仍在比赛。
6. 每步追加 JSONL 审计记录；终端打印三服状态表和失败的下一步，不把“命令已发出”误写成“成功”。

主机控制器采用 Python 一次性 CLI；传输固定为 `docker compose exec -T <service> <container-local-rcon-client>`，在容器内连接本服 RCON，集成后以实际工具名及参数定版，不同时维护 Docker stdin 等第二套传输。接口示例：

```bash
./scripts/racectl status
./scripts/racectl preset newcomers_a --round 2
./scripts/racectl start
./scripts/racectl export --round 2
./scripts/racectl stop --reason "全部比赛结束"
```

服务器 `/function xdu_race:control/...` 名称仅为设计建议，最终以实现注册的 namespace 为准。不要从 BungeeCord 代理直接假设能运行后端 datapack function；`racectl` 分别联系三个后端。RCON 仅内部网络并独立密钥，密钥放本地 secret 文件，不打印到日志。

## 6. 成绩快照：只读、可复核、兼容飞书录入

采集范围必须来自**本轮大奖赛固定 UUID 分组和每图实际起跑名册**，不是导出瞬间的在线列表；断线者保留。`online_now`、`started_this_race`、`finished` 分开；名册在 armed 时固定，每图真正起跑成功后才记 started，不能把失败的初始化当起跑。每人每图完赛时立即写入一次独立记录，包含 UUID、开赛时名字、raw 名次、当图获授分数、时间依据；结算后另记原生累计分数，不能把尚未入账的 points 当最终分数。持久键为 `(event_id, grand_prix_round, attempt_id, group, track_index, uuid)`；导出 ID 不属于成绩键。合法完赛者切换旁观模式不能导致漏记。第六图结算后、原生清理/颁奖退出前冻结六图记录及整轮 GP 数据；之后才允许留档和换组。赛中记录是游戏写入，export 只读，不运行任何原版状态变更 function。

```json
{
  "schema_version": 1,
  "event_id": "xdu-2026-fall",
  "operation_id": "export-2026-10-01T10:00:00Z",
  "preset_id": "newcomers_a",
  "grand_prix_round": 2,
  "attempt_id": "gp-2-attempt-1",
  "boot_id": "race-b-boot-1",
  "revision": 42,
  "ai_count": 0,
  "track_index": 3,
  "group": "B",
  "server": "race-b",
  "track_id": "actual_track_id",
  "snapshot_at_utc": "2026-10-01T10:00:00Z",
  "state": "BETWEEN_TRACKS",
  "players": [
    {
      "uuid": "00000000-0000-0000-0000-000000000000",
      "name_at_start": "ExamplePlayer",
      "online_now": false,
      "started_this_race": true,
      "finished": true,
      "finish_pos_raw": 3,
      "human_rank": 3,
      "status": "FINISHED",
      "captured_at_tick": 7200,
      "captured_at_utc": null,
      "time_basis": "server_tick"
    }
  ]
}
```

本赛事不允许 AI。字段 `human_rank` 是按固定参赛名册、该图有效完赛事实和 raw 名次生成的真人名次；即使零 AI 也不能只凭残留 `finishPos` 认定本图完赛。若发现 AI 参赛、重复名次或记录缺口，保留 raw 值并标记异常/待裁定，不默默修正成“正常成绩”。区分 `DNF`、`DNS`、`DISCONNECTED`、`UNKNOWN`；断线不自动等于 DNF，未完赛不冒充正常末名。输出 UTF-8 `tracks.csv`（每人每图一行，至少 `event_id,gp_round,attempt_id,track_index,group,server,uuid,name,track_id,started,finished,status,finish_pos_raw,human_rank,exported_at`）和 `grand_prix.csv`（每人每 GP attempt 一行，含六图状态、原生 GP 分数/名次、经规则确认的组内总名次、来源和待裁定标记）。manifest 收集三服状态、版本/模板/预设/设置 hash、玩家数、文件 hash、每服快照时间/revision、警告和错误；三服快照不冒充同 tick。重复导出产生不可覆盖的新归档版本，但同一成绩键只出现一次；重赛 attempt 独立留存且不得误累计。`--round N` 指向该轮明确的 attempt，若存在多个且未裁定有效 attempt，必须报歧义；必要时用 `--attempt ID` 明确选择，同时输出六图明细和整轮总名次。

首选读内存 storage：容器内 RCON 执行限定的 `data get storage` 与必要的只读在线状态查询，按固定记录路径分块读取，正确处理 SNBT、Unicode、转义、RCON 分包/截断；不得用正则冒充解析器。读取前后检查 boot_id/attempt/revision，变更时有限重试，持续不一致则明确失败；冻结轮直接读不可变记录。RCON 凭据本身是高权限，所谓只读由 exporter 命令白名单保证。export 的文件副作用仅限宿主机 exports（含导出回执）；不调用 function、save-all、save-off，不标记世界“已导出”，不读写在线世界 NBT 文件。若真实运行证明该路径无法满足离线 UUID 或一致性，再设计并锁定一个极小只读桥接插件，重新过兼容性门禁，而非预先增加插件。精确事件 UTC 若无法从原生获得，保留 server tick/起点时间和精度说明，不能伪造时刻。

## 7. 实施顺序与验收

1. **锁版取证**：按实施图锁定制品，下载官方世界包、记 hash、读许可和 `pack.mcmeta`，与开发 commit 对照；调查 Admin Mode 实际可达入口、六槽写入、确定赛道解析、循环/颁奖/退出、完赛/结算/断线行为及零 AI 路径，产出发行版 `docs/SOURCE_MAP.md`（路径、行号、变量、结论）。
2. **单实例完整纵向验证**：先证明原版26.2/代理离线会话兼容，再用两个真实或受控客户端跑六图；权限、tracks-only loader、受控开赛/退出、零AI、赛中记录和只读导出一起验证。明确区分真实游戏操作、原生超时推进和用于边界验证的受控完赛事件注入，不把后者宣称为真人驾驶彩排。
3. **多实例部署**：一键起5服务；A/B/C从同一停止模板独立初始化，同名离线UUID跨服一致且不共享世界写入；三服回读相同六图预设、固定设置和零AI；名册跨组互斥，轮内禁止换组参赛。
4. **只读留档与恢复**：同轮在六张图之间、结算中及完赛后导出；文件变化仅发生于 exports 和正常游戏写入。验证起跑后断线、完赛后结算前退出、全员离线、重启后历史读取、重复导出和多 attempt，不丢 UUID，不重复成绩，不误认结算完成；可恢复六图明细和 GP 总名次。
5. **真实赛事彩排**：至少 6 真人或受控账户、三服各 2 人；覆盖管理员缺席/吊销、误触红绿灯、赛中掉线、部分实例失败、完整六图结束、第七图不误开、下一轮换组再运行；全程无 AI。对照 HUD、获授/结算分数及导出名次；覆盖重复 start、错误预设、中断恢复、归档前 reset 拒绝。最终跑通五轮、每组 30 图及所有历史轮导出，提交 `docs/OPERATIONS.md` 现场操作卡。
6. **资源与容量**：目标 50 人分成 17/17/16 进行真实容量压力评估；优先分批缓存资源包。仅当彩排数据支持时声明 50 人可用。

**完成标准：** 一条命令启动部署，三实例六赛道预设一致且非赛道设置不被改写；全程零 AI；普通玩家不能改变比赛生命周期；部分失败可察觉、可审计且不自动毁掉成绩；每图明细及每 GP 总名次有只读、可追溯、可按组录入飞书的文件；六图期间分组固定，GP 之间完成留档后才可换组；共五轮、每组 30 张地图赛的留档和计分单位清楚。50 人可用必须另有目标主机的 17/17/16 真实容量证据。

## 8. 给 Agent 的操作提示

先交发行版源码调查报告，再交单实例完整纵向实现和联机记录。执行依赖图见 `docs/IMPLEMENTATION_GRAPH.md`。每轮 GP 不得中途重分组；第六图结算、冻结并留档后才可换组。原版函数与本文不同，以锁定发行包为准并更新 SOURCE_MAP；补丁记录上游原路径、输入文件 hash 和原因，输入不匹配则拒绝应用。每次换版本重新验证权限入口、零 AI、六图边界和名次导出；不凭函数名推断安全退出或终结已成立。无法自动确认的成绩标为待裁定，不能静默给分。
