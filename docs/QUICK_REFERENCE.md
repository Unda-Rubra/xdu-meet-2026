# 现场速查

在仓库根目录运行 `./scripts/...`；游戏内指令在聊天框输入，**代理控制台指令不能在游戏内输入**。游戏账号先通过指定 Yggdrasil 服务登录；QQ 仅用于匹配签到。

## 游戏内／代理控制台

| 谁 | 指令 | 用途 |
|---|---|---|
| 玩家（主大厅） | `/qq <签到QQ号>` | 登记 5–12 位 QQ；在私聊提示中点 `[是]` 确认或 `[不是]` 取消。已确认不能自行改绑。 |
| 授权管理员（主大厅） | `/gpstart` | 按大厅当前设置开赛；等服务端确认，勿重复发送。 |
| 授权管理员 | `/watch A`、`/watch B`、`/watch C`、`/watch lobby` | 切换旁观组／返回大厅；只有开放的比赛组可进入。 |
| **代理控制台** | `xduidentity reset <代理认证UUID>` | 玩家离线且没有进行中 GP 时解除错误 QQ 绑定；UUID 查代理 `plugins/XduIdentity/identities.json` 的键，**不是**游戏世界的离线 UUID。 |

赛道池、轮数、道具、圈数使用大厅原版菜单配置，不是聊天指令。这里列的是本活动自定义指令；原版 Minecraft 的通用命令不在本表。

## 主机脚本

| 命令 | 用途 |
|---|---|
| `./scripts/up` | 启动代理、四个世界与资源包服务（前台）；另开终端运行 `./scripts/meet-service serve` 保持本地协调器运行。 |
| `./scripts/racectl admin <游戏名> A\|B\|C` | 给已在线玩家授权当次认证会话的管理员／解说身份；重连须重新授权。 |
| `./scripts/racectl admin <游戏名> revoke` | 撤销；仅在 GP 之间操作。 |
| `./scripts/racectl start` | 主机端开赛，与游戏内 `/gpstart` 二选一。 |
| `./scripts/racectl status` | 查看各比赛组状态。 |
| `./scripts/racectl abort --reason '原因'` | 中止异常 GP；不要对中断成绩直接上传。 |
| `./scripts/meet-service doctor` | 开赛前检查云端连接及已登记 QQ 与签到表的匹配；输出可能含私人 QQ，勿公开。 |
| `./scripts/meet-service tokens` | 查看已归档比赛的本地 token；热身赛不要上传。 |
| `./scripts/meet-service upload --token TOKEN` | **唯一正式成绩上传入口**；先在飞书「比赛控制」选「当前轮次」，再上传该次 GP 的 token。 |
| `./scripts/meet-service capture` | 手动执行一次本地采集；通常由 `serve` 自动执行。`start`、`admin` 也可用，分别等同上述 `racectl` 操作。 |
| `./scripts/draw-prize` | 从飞书`参会情况=线下参会`且未中奖者中随机抽 **一人**，写回中奖状态与时间；每运行一次抽一人。需本机 `lark-cli` 用户授权。 |

仅部署／维护：`./scripts/fetch-assets` 下载校验锁定素材；`./scripts/prepare-template` 创建停止状态的世界模板；`./scripts/build-identity` 编译代理插件；`./scripts/init-worlds --accept-eula` **首次**初始化（不覆盖已有世界）；`./scripts/prepare-lobby` 在停服时更换大厅并备份原大厅；`./scripts/meet-service setup-app`、`migrate` 用于首次飞书应用配置及结构迁移，不要在活动中重复执行。`./scripts/compat` 是隔离兼容性测试，**不操作正式赛事**。`./scripts/export-results` 的旧入口已不受支持，勿用；成绩用 `tokens` 和 `upload`。

## 飞书表格怎么看

[打开活动多维表格「用户」](https://xducraft.feishu.cn/wiki/OYwMwtVQAiU9HekVm3FckIqjnyh?table=tblNXdxT2jqPczfh&view=vewbLKXzfF)。在「用户」表切换「当前轮排名」「总排名（按最终总得分）」「最终排名（去掉最低轮）」视图；另外还有「SprintRacer计分表」「SprintRacer积分倍率」「比赛控制」「轮次上传记录」表。上传前先在「比赛控制」设置「当前轮次」；上传后核对最近上传状态为**完整**及轮次、token，才对外发布排名。前四次有效参赛累计得分；个人第五次有效参赛起才扣最低一轮，缺席不能再多扣一轮。五轮倍率依次为 `1.0／1.1／1.2／1.5／1.8`。

## 怎么抽奖

1. 在「用户」表核对正式签到、`参会情况`为`线下参会`、`已中奖`未勾选且`中奖时间`为空；**当前六条是测试报名记录，正式开奖前先换成真实数据**。线上玩家不自动获得资格。
2. 主机运行 `./scripts/draw-prize` **一次**。脚本在飞书同一条记录写入`已中奖`和`中奖时间`，读回确认后显示昵称与 QQ 尾号；在表里用原记录核对全号。再抽一人就再运行一次，已中奖者不会重抽。
3. 如果出现「写入未确认」，先到飞书核对该记录的两个字段，不要直接重试或另行颁奖。
