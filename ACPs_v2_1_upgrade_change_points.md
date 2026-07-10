# RenTA 平台升级到 ACPs-community v2.1.0 改造点清单

## 升级计划：不影响现有功能的兼容升级路线

本次升级目标不是“用新版 ACPs-community 直接替换现有平台代码”，而是在**保持现有平台功能、入口、接口、数据和编排流程不受影响**的基础上，把 ACPs-community v2.1.0 的协议能力逐步移植进现有系统。

### 一、升级总策略

| 策略 | 说明 |
|---|---|
| 保留主线功能 | 现有前端、Registry 自定义能力、积分、事件、Passport、Supervisor、Mode Router、旧 `/api` 全部保留 |
| 协议模块增量移植 | 只把新版 AIC、ACS、EAB、CA 发证、Discovery、MQ Inbox 等协议能力分阶段移植 |
| 新旧协议双轨兼容 | 旧 Agent / 旧 AIC / 旧 ACS / 旧证书继续可读可用，新注册 Agent 默认走 v2.1 |
| 外部接口不破坏 | `10.126.126.8:8888`、前端路由、旧 `/api`、已有网关路径保持不变 |
| 可灰度、可回滚 | 每个新能力都通过环境变量开关控制，异常时可以切回旧链路 |
| 先旁路验证再切主链路 | 新协议能力先影子计算/旁路校验，通过后再对新数据启用 |

### 二、分阶段实施计划

| 阶段 | 目标 | 主要修改 | 不影响原功能的措施 | 交付结果 |
|---|---|---|---|---|
| 阶段 0：基线冻结与回归清单 | 固定当前平台状态 | 记录当前前端页面、API、数据库表、启动脚本、端口、核心流程 | 不改代码，只做盘点 | 当前功能基线、回归测试清单 |
| 阶段 1：AIC/ACS 兼容升级（已完成） | 支持 AIC v02.01、ACS v02.01 | 升级 `aic.py`、双 Schema、Agent 申请/审批和 Supervisor 逻辑 | 旧 AIC v02.00 保留 legacy validator；v2.1 写入受开关控制 | 新旧 AIC/ACS 双轨可用；代码提交 `2e9bd07` |
| 阶段 2：Registry EAB 旁路能力（已完成） | 引入新版 Registry 的 EAB 生成和一次性消费能力 | 增加 `app/eab`、SM4、migration、EAB API 和隔离迁移门禁 | 默认关闭；不覆盖 `points/events/Passport/Supervisor`，旧 `/api` 继续可用 | Registry 支持 EAB；代码提交 `0e8baf4` |
| 阶段 3：CA 发证链路升级（已完成） | 从 HTTP-01 Challenge 切到 EAB | 引入 `eab_verifier.py`、Registry EAB client，修改 ACME `new-account/new-order/finalize` 和 v2.1 证书 CN/SAN | Challenge Server 保留 legacy，旧 account/证书继续可用，默认开关关闭 | EAB 隔离端到端发证通过；提交 `fed618e`；CA `131 passed` |
| 阶段 4：前端与网关兼容适配 | 前端支持新版字段但不破坏旧页面 | Agent 申请页支持 ACS 02.01、certificate、AMQP endpoint；网关新增 EAB/CA 分流 | 旧页面、旧接口、旧字段继续兼容；`/api` 不改成强制 `/api/v1` | 前端可申请新版 Agent |
| 阶段 5：Discovery 适配 | 引入新版 Discovery 查询能力 | 接入 `/acps-adp-v2/discover`，Registry DSP 同步适配 | Mode Router 保留旧 `passports/discovery` fallback | Discovery 优先、Registry fallback |
| 阶段 6：MQ Inbox / mTLS 增强 | 支持新版 AIP 群组通信 | 引入 mq-auth-server、AMQPS、Inbox endpoint、SDK 调用适配 | Direct RPC / HTTP 调度不删除，失败自动 fallback | 新版 MQ Inbox 可灰度使用 |
| 阶段 7：全量回归与灰度上线 | 确认升级不影响既有功能 | 跑页面、API、数据、发证、编排、积分、事件回归 | 发现问题关闭对应开关回滚 | 可上线版本与回滚方案 |

### 三、推荐实施顺序

```text
1. 以远端 /home/johnteller/team_ws 为升级主线，先冻结当前目录结构和启动路径
2. 保留 sds/th/wyl/yhl/ACPs_update_code/cyf/server_logs 原路径，不做破坏性重命名
3. 在远端真实代码上增加兼容开关和回归测试脚本
4. 优先升级 AIC v02.01 与 ACS v02.01
5. 移植 Registry EAB 模块，但保留旧 /api 与 points/events/Passport/Supervisor 等平台扩展
6. 改造 CA EAB 发证链路，Challenge Server 转 legacy fallback
7. 适配前端申请页和 wyl/server.py 网关分流
8. 接入 Discovery v2.1，但保留 yhl/Registry discovery fallback
9. 最后接入 MQ Inbox/mTLS，保留 Direct RPC/HTTP fallback
10. 全量回归通过后，只对新注册 Agent 默认启用 v2.1
```

### 阶段 1 完成状态与阶段 2 入口

2026-07-10 已在远端主线完成阶段 1，分支为 `upgrade/acps-v2.1-aic-acs`，代码提交为 `2e9bd07af7449ff1c7cbb87557e923009d68593c`。完整实施、测试、部署和回滚记录见 `STAGE1_AIC_ACS_UPGRADE.md`。

已完成的能力：

- AIC v02.00/v02.01 双生成、双校验和布局识别。
- ACS 02.00/02.01 双 Schema；02.01 支持 certificate、AMQP 和无 Challenge。
- Agent 创建/更新写入门禁，审批按 ACS 版本分配 AIC，AMQP `{AIC}` 自动替换。
- Supervisor 对 Challenge 和 endpoint transport 按版本分流。
- 三个开关进入 Registry 配置、示例配置和正式启动脚本。
- 阶段 1 专项 `14 passed`；Registry 全量 `120 passed, 6` 个阶段 0 既有失败；总门禁退出码 `0`。
- 正式重启后 HTTP `18/18`；数据库版本和阶段 0 行数未变化。

当前生产运行态仍为：

```text
ACPS_V21_ENABLED=false
ACPS_LEGACY_API_ENABLED=true
ACPS_AIC_DUAL_READ_ENABLED=true
```

阶段 2 已按上述边界完成：只移植 Registry EAB 生成/一次性消费能力和新增表，没有切换 CA、删除 Challenge 或修改积分、事件、Passport、Supervisor 和旧 `/api`。实施记录见阶段 1 完成报告第 6 节和阶段 2 完成报告。

### 阶段 2 完成状态与阶段 3 入口

2026-07-10 已在远端主线完成阶段 2，分支为 `upgrade/acps-v2.1-registry-eab`，代码提交为 `0e8baf4de43e51f215d656a27afff802d6310894`。完整实现、数据库迁移、测试、部署和回滚记录见 `STAGE2_REGISTRY_EAB_UPGRADE.md`。

已完成：

- EAB Credential 模型、SM4 密文存储、用户签发 API 和内部一次性消费 API。
- Agent 所有权、审批状态、active 状态和 ACS/AIC v02.01 限制。
- PostgreSQL `FOR UPDATE` 并发消费保护、过期和重复消费处理。
- Alembic `f1a2b3c4d5e6` 纯新增表 migration。
- 生产库 Alembic 漂移已在副本验证后完成对账，生产业务表数据未变化，EAB 表为空。
- 阶段 1+2 专项 `27 passed`；Registry 全量 `133 passed`，仅保留 6 个阶段 0 既有失败。
- 总门禁退出码 `0`；生产重启后 HTTP `18/18`。

当前生产仍设置 `ACPS_EAB_ISSUANCE_ENABLED=false`，EAB 路由不注册。阶段 3 已完成 CA EAB JWS 校验、account-AIC 绑定、无 Challenge Order 和 v2.1 证书签发；生产 CA EAB 准入仍默认关闭。完整记录见 `STAGE3_CA_EAB_UPGRADE.md`。

### 阶段 3 完成状态与阶段 4 入口

2026-07-10 已在远端 `upgrade/acps-v2.1-ca-eab` 分支完成阶段 3，核心代码提交为 `fed618e70b9686942f54bc091838e1b6b36c76fc`。

已完成：

- EAB `HS256` JWS 校验、Registry 一次性消费和 `acme_accounts.aic` 持久化。
- EAB account 的 identifier-AIC 限制、valid Authorization、ready Order 和无 HTTP-01 签发。
- finalize 阶段的 Registry ACS、CSR `CN=AIC` 和 `URI:acps://AIC` 校验。
- v2.1 证书的裸 AIC CN、ACS DNS/IP SAN 和有效期裁剪；legacy 证书路径不变。
- CA SQLite 迁移 `d4e5f6a7b8c9`，23 条旧证书在 upgrade/downgrade/re-upgrade 和生产迁移中保持不变。
- 真实隔离 Registry/CA E2E：`new-account=201 -> order=ready -> finalize=valid`，EAB 重放返回 400。
- 阶段 3 专项 `12 passed`，CA 全量 `131 passed`，总门禁退出码 `0`，HTTP `18/18`。

生产运行态：

```text
ACPS_CA_EAB_ENABLED=false
ACPS_CHALLENGE_LEGACY_ENABLED=true
ACPS_EAB_ISSUANCE_ENABLED=false
alembic_version=d4e5f6a7b8c9
```

下一步进入阶段 4：在 `wyl/frontend` 增加 ACS 02.01 certificate/AMQP 表单与 EAB 申请流程，在 `wyl/server/server.py` 增加 Registry EAB 和 CA 路由转发，但保留旧页面、旧 `/api`、积分、事件、Passport 和 Supervisor。阶段 4 详细顺序见阶段 3 完成报告第 7 节。

### 远端已联通后的实际基线与整理结果

结论：**后续升级以远端 `/home/johnteller/team_ws` 实际代码为主线；提交包解压代码只作为历史提交参考和差异对照。**

远端已按“不影响原有功能”的原则做了轻量整理：没有改名或移动任何启动脚本依赖的活跃目录，只把未被启动路径引用的备份/临时目录移入可回滚归档，并新增一个语义化软链接视图。

| 项 | 当前处理结果 |
|---|---|
| 远端主线根目录 | `/home/johnteller/team_ws` |
| 语义化项目视图 | `/home/johnteller/team_ws/renta_platform`，内部均为软链接，不替代原路径 |
| 项目结构说明 | `/home/johnteller/team_ws/PROJECT_LAYOUT.md` |
| 归档目录 | `/home/johnteller/team_ws/_archive/pre_upgrade_cleanup_20260708_194323` |
| 已归档内容 | `backups`、`port_swap_backups`、`th_backups`、`tmp_agent_profiles`、`ztl` |
| 保留原因 | 启动路径、日志路径、依赖路径和历史兼容路径保持不变，避免影响原功能 |

远端当前实际活跃/保留目录如下：

| 路径 | 角色 | 升级处理原则 |
|---|---|---|
| `/home/johnteller/team_ws/sds/registry-server` | Registry 主后端，包含 points/events/Passport/Supervisor 等 RenTA 扩展 | 作为 Registry 升级主线，不能被新版官方 Registry 直接覆盖 |
| `/home/johnteller/team_ws/sds/ca-server` | CA / ACME 服务 | 迁移到 EAB 发证链路，但保留旧接口兼容 |
| `/home/johnteller/team_ws/sds/challenge-server` | 旧 HTTP-01 Challenge 服务 | v2.1 后降级为 legacy fallback，不直接删除 |
| `/home/johnteller/team_ws/th/mode_router` | Orchestrator / Mode Router 编排端 | 保持原调度、回调、积分结算能力，再逐步接入 Discovery/MQ Inbox |
| `/home/johnteller/team_ws/wyl/frontend` | 前端静态页面 | 只做兼容字段/UI 适配，不破坏现有页面 |
| `/home/johnteller/team_ws/wyl/server/server.py` | 8888 前端静态服务与反向代理 | 保持入口不变，升级时只增加必要路由分流 |
| `/home/johnteller/team_ws/yhl/ACPs-Discovery-Server` | 现有 Discovery 服务 | 短期保留，后续对接 ACPs-community v2.1 Discovery |
| `/home/johnteller/team_ws/yhl/partner-literature-*`、`direct_rpc_server.py` | Partner Agent / Direct RPC | MQ Inbox 未稳定前保留 fallback |
| `/home/johnteller/team_ws/ACPs_update_code/ACPs-SDK` | 当前启动脚本引用的旧 SDK | SDK 升级前必须保留该路径 |
| `/home/johnteller/team_ws/cyf/ACPs-Registry-Server` | 历史 legacy registry，被 `start_all_servers.sh` 引用 | 先保留，不作为主升级对象 |
| `/home/johnteller/team_ws/server_logs` | 日志和 PID 路径 | 保留原路径，启动脚本仍写入这里 |

语义化软链接视图如下，供后续开发和文档引用：

```text
/home/johnteller/team_ws/renta_platform/
  registry_stack_sds        -> ../sds
  registry_server           -> ../sds/registry-server
  ca_server                 -> ../sds/ca-server
  challenge_server_legacy   -> ../sds/challenge-server
  orchestrator_mode_router  -> ../th/mode_router
  frontend                  -> ../wyl/frontend
  frontend_gateway_server   -> ../wyl/server
  discovery_server          -> ../yhl/ACPs-Discovery-Server
  agent_partners_yhl        -> ../yhl
  legacy_acps_sdk           -> ../ACPs_update_code/ACPs-SDK
  legacy_acps_reference     -> ../ACPs_update_code
  legacy_registry_cyf       -> ../cyf/ACPs-Registry-Server
  server_logs               -> ../server_logs
```

因此，升级分支/补丁应直接面向远端真实路径：

```text
主升级基线：/home/johnteller/team_ws
Registry：/home/johnteller/team_ws/sds/registry-server
CA：/home/johnteller/team_ws/sds/ca-server
Challenge legacy：/home/johnteller/team_ws/sds/challenge-server
Orchestrator：/home/johnteller/team_ws/th/mode_router
Frontend：/home/johnteller/team_ws/wyl/frontend
Gateway：/home/johnteller/team_ws/wyl/server/server.py
Discovery/Partners：/home/johnteller/team_ws/yhl
```

2026-07-10 已完成阶段 0 基线验证。平台已通过原 `wyl/start_stack.sh` 完整启动，`8001`、`8003`、`8004`、`8098`、`8099`、`18080`、`19090`、`8888` 均正常监听，RabbitMQ `5672` 和本机 PostgreSQL `5432` 正常。阶段 0 没有修改业务代码、数据库结构或原有接口。

阶段 0 已新增只读 HTTP 冒烟脚本和隔离测试数据库的一键回归脚本，并完成 Registry、CA、Challenge、Mode Router 的测试基线记录。完整结果、数据行数、已知测试失败和升级前数据快照位置见 `STAGE0_BASELINE.md`。

### 四、首个可交付版本范围

首个版本建议只做“协议主链路兼容升级”，不要一次性切换所有新版能力：

1. AIC v02.01 生成/校验。
2. ACS v02.01 schema、前端申请表和后端校验。
3. Registry EAB 凭据生成与消费接口。
4. CA EAB 发证主链路。
5. Challenge Server 从主链路下线，但保留 legacy。
6. 网关保持旧 `/api`，新增必要 EAB/CA 分流。
7. 旧 Agent、旧积分、旧事件、旧 Passport、旧编排流程全部通过回归。

暂缓到后续版本：

- 完整 mTLS entity 平面。
- MQ Inbox 全量切换。
- Discovery 完全替代 Registry discovery。
- Python 3.14 / hatchling 全量运行时重构。

### 五、关键开关与回滚策略

| 开关 | 回滚作用 |
|---|---|
| `ACPS_V21_ENABLED=false` | 关闭 v2.1 新写入，恢复旧协议写入路径 |
| `ACPS_AIC_DUAL_READ_ENABLED=true` | 保证旧 AIC 和新 AIC 都能读取 |
| `ACPS_EAB_ISSUANCE_ENABLED=false` | 新发证暂时回退旧链路或停止新链路灰度 |
| `ACPS_CHALLENGE_LEGACY_ENABLED=true` | 保留旧 Challenge 兜底 |
| `ACPS_DISCOVERY_V21_ENABLED=false` | Mode Router 回退旧 discovery/passport 查询 |
| `ACPS_MQ_INBOX_ENABLED=false` | 群组通信回退 Direct RPC / HTTP fallback |
| `ACPS_HTTP_FALLBACK_ENABLED=true` | 新版 Discovery/MQ/mTLS 异常时继续走旧 HTTP 流程 |

### 六、升级完成判定

只有满足以下条件，才认为升级完成：

- 原有平台入口、页面、菜单、登录和管理流程不变。
- 旧 `/api` 接口继续可用。
- 历史 Agent、旧 AIC、旧证书、积分、事件、Passport、Supervisor 记录可查。
- 新注册 Agent 默认使用 AIC v02.01 和 ACS v02.01。
- 新证书通过 EAB 发证，不再依赖 Challenge Server 主链路。
- Mode Router 原有调度、回调、结算流程不受影响。
- 关闭新协议开关后，平台可以回到旧链路运行。

---

生成时间：2026-07-08  
目标：记录平台从当前提交版本/远端主线升级到 ACPs-community v2.1.0 时，所有需要关注和修改的代码点、协议差异、配置差异、数据迁移点和验证方式。  
新版协议库：[ACPs-community](https://atomgit.com/AIP-PUB/ACPs-community)  
新版基线：`v2.1.0` / commit `39cc7113f00e80df93b2033224a3b93750c16958` / 2026-06-22。

> 说明：远端主线目录以 `/home/johnteller/team_ws` 为准。2026-07-08 已通过 SSH 复核远端目录，并按“零破坏”原则完成轻量整理：活跃启动路径保持不变，备份/临时目录归档到 `_archive`，新增 `renta_platform` 软链接视图。提交包解压代码仅作为历史对照。

---

## 0. 新增约束：升级不能影响原有所有功能

用户补充约束：**协议升级后不能影响原来的所有功能**。因此本次升级不能采用“直接替换新版 ACPs-community 服务”的方式，而应采用 **兼容层 + 增量迁移 + 可回滚开关** 的方案。

### 0.1 零回归边界

升级过程中必须保持以下能力在入口、菜单、接口、数据和行为上继续可用：

| 原有能力 | 升级要求 | 具体改造原则 |
|---|---|---|
| 平台访问入口 | `10.126.126.8:8888` 不变 | 前端入口、网关端口、静态资源路径不因协议升级变化 |
| 前端菜单/页面 | 登录、Agent 申请、Agent 详情、Square/市场、账户、积分、事件、审批/监管类页面不消失 | 先适配字段，不删除旧页面；新增 v2.1 字段以兼容方式展示 |
| 旧 `/api` 接口 | 必须继续响应 | 新版官方 `/api/v1` 只能作为内部或新增路径；对前端保留 `/api`，通过 alias/router adapter 转发 |
| Registry 自定义能力 | `points`、`events`、`Passport`、`Supervisor`、前端兼容 API 全部保留 | 不用新版 `registry-server` 目录直接覆盖当前 Registry；只移植协议相关模块 |
| 旧 Agent 数据 | 历史 Agent、旧 AIC、旧证书、日志、积分、事件仍可查 | 数据库迁移只新增字段/表；不得破坏旧主键和旧 AIC 关联 |
| 新 Agent 注册 | 默认生成 ACPs v2.1 / AIC v02.01 / ACS v02.01 | 新写入走新协议；旧读取继续兼容 v02.00 |
| 旧证书链路 | 已签发证书继续可用到过期 | 新发证走 EAB；Challenge Server 保留 legacy，不作为新主链路 |
| 编排/调度 | Mode Router 原有任务分发、结算、回调不受影响 | Discovery/MQ Inbox 先做可选增强，不能切断原 HTTP/RPC fallback |
| 网关路由 | `/api`、`/acps-atr-v2`、`/acps-adp-v2` 等现有前端依赖路径继续可用 | 通过网关分流到 Registry/CA/Discovery，保留旧路径别名 |
| 启动方式 | 当前 `.py312deps` + `.venv` 依赖路径仍能启动 | 短期不强制 py3.14；新依赖先做兼容安装和启动脚本封装 |

### 0.2 兼容升级总原则

1. **只新增，不破坏**：数据库迁移优先 `ADD COLUMN`、新增映射表、新增索引；避免删除列、改主键、改旧枚举含义。
2. **旧协议读兼容，新协议写默认**：旧 AIC/ACS/证书/接口返回可继续读取；新注册、新发证、新发布能力默认使用 v2.1。
3. **外部契约不变**：前端和第三方已调用的 URL、请求字段、响应字段保持兼容；新增字段只能作为 optional。
4. **协议能力后置切换**：AIC/ACS/EAB 可以先落地；Discovery v2.1、mTLS entity、MQ Inbox 要在 HTTP fallback 完整保留后再灰度。
5. **可配置开关**：每个新协议能力都要有环境变量开关，出现问题可立即回退到旧链路。
6. **双轨验证**：同一 Agent 可同时保留 `legacy_aic` 与 `current_aic`；迁移前后查询结果必须一致。

### 0.3 必须新增的兼容开关

建议在 Registry、CA、Gateway、Mode Router 启动配置中增加以下开关：

| 开关 | 默认值 | 用途 |
|---|---:|---|
| `ACPS_V21_ENABLED` | `false` 或灰度环境 `true` | 总开关，控制是否启用 v2.1 协议写入 |
| `ACPS_LEGACY_API_ENABLED` | `true` | 保留旧 `/api`、旧响应字段和旧校验入口 |
| `ACPS_AIC_DUAL_READ_ENABLED` | `true` | 同时识别 v02.00 与 v02.01 AIC |
| `ACPS_EAB_ISSUANCE_ENABLED` | `false -> true` | 控制新证书是否切到 EAB 流程 |
| `ACPS_CHALLENGE_LEGACY_ENABLED` | `true` | 只给旧流程兜底，不作为新主路径 |
| `ACPS_DISCOVERY_V21_ENABLED` | `false` | 控制是否启用新版 Discovery 查询/注册 |
| `ACPS_MQ_INBOX_ENABLED` | `false` | 控制是否启用 MQ Inbox 群组邀请 |
| `ACPS_HTTP_FALLBACK_ENABLED` | `true` | Discovery/MQ/mTLS 未就绪时保留原 HTTP/RPC 调度 |

### 0.4 实施策略：旁路验证后再切主链路

```text
阶段 A：基线冻结
  记录当前远端/提交包接口、页面、数据库表和关键流程，不改功能。

阶段 B：兼容层落地
  新增 AIC v02.01、ACS v02.01、EAB 模块，但旧接口/旧字段/旧数据继续可用。

阶段 C：影子写入/影子校验
  Agent 审批时同时计算新 AIC/新 ACS/新证书申请参数，但不立即替换旧链路输出。

阶段 D：灰度切换
  只对新注册 Agent 启用 v2.1；旧 Agent 继续 legacy 读取。

阶段 E：全量切换新写入
  新注册、新发证、新 Discovery 注册默认 v2.1；旧数据不强制失效。
```

### 0.5 升级验收门槛

在任何一次切换前，以下检查必须全部通过：

| 验收项 | 通过标准 |
|---|---|
| 页面回归 | 原有主要页面可打开、可登录、列表和详情可加载 |
| 接口回归 | 旧 `/api` 自动化 smoke test 通过，HTTP 状态码和关键字段不变 |
| 数据回归 | 旧 Agent、旧积分、旧事件、旧证书记录能查；迁移脚本可重复执行 |
| 协议回归 | 新 Agent 生成 v02.01 AIC/ACS；旧 Agent 仍能通过 legacy validator |
| 发证回归 | 旧证书继续可用于访问；新证书通过 EAB 签发；Challenge 不参与新链路 |
| 编排回归 | Mode Router 可完成原有任务分发、回调、积分结算；Discovery/MQ 失败时 fallback 正常 |
| 回滚验证 | 关闭 `ACPS_V21_ENABLED` 后，平台恢复旧链路，已迁移数据不导致启动失败 |

---

## 1. 代码基线与路径映射

| 领域 | 当前提交包/本地解压路径 | 远端主线路径 | 新版 ACPs-community 对应路径 | 结论 |
|---|---|---|---|---|
| 前端源码 | `D:\B-EP1\_analysis\renta_source_submission_20260618_143957\frontend_source` | `/home/johnteller/team_ws/wyl/frontend` | 无官方对应，属 RenTA 平台 UI | 需要保留并适配新版协议字段/API |
| 前端网关/静态服务 | `...\backend_server\server.py` | `/home/johnteller/team_ws/wyl/server/server.py` | `acps-infra` 的 nginx/standalone 方案可参考 | 保留平台网关，但路由要升级 |
| 编排端 | `...\orchestrator\mode_router` | `/home/johnteller/team_ws/th` | `demo-leader`、`acps-sdk`、新版 AIP | 保留业务编排，适配 ADP/AIP/MQ Inbox |
| Registry 端 | `...\registry_stack\registry-server` | `/home/johnteller/team_ws/sds/registry-server` | `ACPs-community/registry-server` | 不建议直接覆盖；做兼容升级或分层迁移 |
| CA 端 | `...\registry_stack\ca-server` | `/home/johnteller/team_ws/sds/ca-server` | `ACPs-community/ca-server` | 证书主链路必须升级到 EAB |
| Challenge Server | `...\registry_stack\challenge-server` | `/home/johnteller/team_ws/sds/challenge-server` | 新版已删除 | 只保留 legacy，主流程下线 |
| Discovery | 提交包中主要通过外部 YHL Discovery/接口使用 | `/home/johnteller/team_ws` 下可能有 YHL 代码 | `ACPs-community/discovery-server` | 建议引入新版作为主发现服务 |
| MQ Auth | 当前无完整对应 | 可能仅 RabbitMQ demo/旧容器 | `ACPs-community/mq-auth-server` | v2.1 群组 Inbox 需要新增 |
| SDK/CLI | 当前编排端引用旧 `acps_sdk` | 远端环境中按实际 PYTHONPATH | `ACPs-community/acps-sdk`, `acps-cli` | SDK 要升级，证书/注册建议统一走 CLI |

---

## 2. 版本前后差异总表

| 项 | 当前/旧版本 | 新版 v2.1.0 | 需要修改 |
|---|---|---|---|
| ACPs 整体版本 | 近似 v2.0.0 | v2.1.0 | 固定 upstream commit，建立升级分支 |
| Registry 包版本 | `2.0.0` | `2.1.0` | 引入 EAB、verification、mTLS entity、服务拆分 |
| CA 包版本 | `2.0.0` | `2.1.0` | 从 HTTP-01 challenge 改 EAB 绑定发证 |
| Challenge 包版本 | `2.0.0` | 已删除 | compose/start 脚本中从主链路移除 |
| AIC 规范 | `ACPs-spec-AIC-v02.00` | `ACPs-spec-AIC-v02.01` | 新旧 AIC 双校验；新注册只发 v02.01 |
| ACS 规范 | `protocolVersion: 02.00` | `protocolVersion: 02.01` | 更新 schema、前端生成、后端校验 |
| ATR | Registry + CA + HTTP-01 Challenge | Registry EAB + CA EAB + mTLS entity | 改证书申请流程与实体注册入口 |
| AIP 群组 | RabbitMQ 明文/账号密码 + Direct RPC 邀请 | AMQPS + mTLS + MQ Inbox 优先 | 新增 AMQP endpoint、mq-auth-server、Inbox 邀请 |
| API 前缀 | 旧 Registry 默认 `/api` | 官方默认 `/api/v1` | 平台保留 `/api` 兼容或网关重写 |
| 端口 | Registry 8001、CA 8003、Challenge 8004、Discovery 8005 | 官方默认 Registry 9001/9002、CA 9003、Discovery 9005、MQ Auth 9007/9008 | 决定“保留旧端口”还是“迁到官方端口”，网关同步改 |
| Python 运行时 | 当前说明依赖 `.py312deps` + `.venv`，旧包 requires-python 多为 >=3.13 | 官方 Registry/CA requires-python `>=3.14,<4.0` | 短期兼容当前运行时，长期准备 py3.14/uv runtime |
| 数据库驱动 | `asyncpg` + `psycopg2-binary` | `asyncpg` + `psycopg[binary]` | requirements/pyproject/start PYTHONPATH 调整 |

---

## 3. 协议层必须修改的点

### 3.1 AIC：v02.00 -> v02.01

**旧代码位置**

- 本地：`D:\B-EP1\_analysis\renta_source_submission_20260618_143957\registry_stack\registry-server\app\utils\aic.py`
- 远端：`/home/johnteller/team_ws/sds/registry-server/app/utils/aic.py`

**新版代码位置**

- `D:\B-EP1\_analysis\ACPs-community\registry-server\app\utils\aic.py`

**前后区别**

旧版 v02.00：版本号在第 9 级。

```py
# ACPs-spec-AIC-v02.00
body_1_9 = f"{AIC_PREFIX}.{arsp}.{vendor}.{ontology_serial}.{instance_serial}.{ver}"
# 形如：1.2.156.3088.<manager>.<provider>.<ontology>.<instance>.<version>.<crc>
```

新版 v02.01：版本号在第 5 级。

```py
# ACPs-spec-AIC-v02.01
body_1_9 = f"{AIC_PREFIX}.{ver}.{arsp}.{vendor}.{ontology_serial}.{instance_serial}"
# 形如：1.2.156.3088.<version>.<manager>.<provider>.<ontology>.<instance>.<crc>
```

**需要修改**

| 文件/模块 | 修改内容 |
|---|---|
| `app/utils/aic.py` | 引入新版 v02.01 生成、校验、CRC 逻辑 |
| `app/utils/aic_legacy.py` 或同文件函数 | 保留旧版 v02.00 `validate_aic_legacy()`，用于旧数据读取 |
| `Agent.aic` 相关服务 | 新注册/审批只生成 v02.01 AIC；旧 AIC 不再用于新发证 |
| `get_ontology_aic_from_entity()` | 按新版“第 9 级实例序列号”重算，不再按旧第 8 级 |
| `generate_entity_aic_from_ontology()` | 以新版段位生成实体 AIC |
| 前端展示 | 标注旧 AIC / 新 AIC，必要时展示迁移状态 |
| Discovery 索引 | 按新 AIC 重建或保留 legacy 索引映射 |
| Mode Router 硬编码 AIC | 全部替换或建立 old->new 映射 |

**数据迁移策略**

1. 新增字段或映射表：`legacy_aic`, `current_aic`, `aic_version`, `migration_status`。
2. 旧 Agent 保留原 AIC 供历史记录、积分、日志查询。
3. 对继续运行的 Agent 分配 v02.01 新 AIC。
4. 基于新 AIC 重新签发证书。
5. Discovery 以新 AIC 为主，旧 AIC 仅做重定向/别名。

**验证**

- 单测：旧 AIC 只通过 legacy validator，不通过新 validator。
- 单测：新 AIC 通过新版 validator，CRC 正确。
- 集成：旧 Agent 详情仍可打开，新 Agent 审批后生成 v02.01 AIC。

---

### 3.2 ACS：v02.00 -> v02.01

**旧代码位置**

- `registry-server/app/agent/acsSchema.json`
- `frontend_source/src/views/AgentApplyView.vue`
- `frontend_source/public/assets/agent-apply-bridge.js`

**新版代码位置**

- `ACPs-community/registry-server/app/agent/acsSchema.json`
- `ACPs-community/acps-specs/03-ACPs-spec-ACS/ACPs-spec-ACS.md`

**前后区别**

| 字段 | 旧版 | 新版 |
|---|---|---|
| `protocolVersion` | `02.00` | `02.01` |
| `securitySchemes.mtls.x-caChallengeBaseUrl` | 必填，用于 HTTP-01 challenge | 废弃，EAB 替代 challenge |
| `certificate` | 无 | 新增 `certificate.altNames`, `certificate.requestedValidity` |
| `endPoints.transport` | 旧前端用了 `HTTP`，旧 schema 示例为 `JSONRPC/HTTP_JSON` | 明确支持 `JSONRPC/HTTP_JSON/AMQP` |
| AMQP Inbox | 无 | `amqps://host:5671/acps?inbox=inbox_{AIC}` |
| `{AIC}` 占位符 | 旧服务无统一替换 | 新版 service_acs 会替换 endpoint 中 `{AIC}` |

**需要修改**

| 文件/模块 | 修改内容 |
|---|---|
| `registry-server/app/agent/acsSchema.json` | 更新到 v2.1 schema；保留兼容校验错误提示 |
| `registry-server/app/utils/acs.py` | 校验 v02.01；过渡期允许旧 ACS 只读 |
| `frontend_source/src/views/AgentApplyView.vue` | 生成 `protocolVersion: '02.01'`；去掉 challenge 必填；增加 certificate/AMQP 字段 |
| `frontend_source/public/assets/agent-apply-bridge.js` | 同步修改 ACS 构造、校验、预览逻辑 |
| `AgentApplyView.vue` transport | 把旧 `HTTP` 改成 `HTTP_JSON` 或 `JSONRPC`；增加 `AMQP` |
| `registry-server/app/agent/service_acs.py` | 若采用新版代码，要接入 `{AIC}` endpoint 替换逻辑 |

**旧前端待改代码示例**

```js
protocolVersion: '02.00',
securitySchemes: {
  mtls: {
    type: 'mutualTLS',
    description: '智能体间mTLS双向认证',
    'x-caChallengeBaseUrl': 'http://10.126.126.8:8888/acps-atr-v2'
  }
},
endPoints: [{ url: form.value.url, transport: 'HTTP', security: [{ mtls: [] }] }]
```

**建议改为**

```js
protocolVersion: '02.01',
securitySchemes: {
  mtls: {
    type: 'mutualTLS',
    description: '智能体间 mTLS 双向认证'
  }
},
certificate: {
  altNames: {
    dns: form.value.certDnsNames || [],
    ip: form.value.certIpNames || []
  },
  requestedValidity: Number(form.value.requestedValidity || 365)
},
endPoints: [{
  url: form.value.url,
  transport: form.value.transport || 'JSONRPC',
  security: [{ mtls: [] }]
}]
```

AMQP 模式示例：

```js
endPoints: [{
  url: 'amqps://mq.acps.example.com:5671/acps?inbox=inbox_{AIC}',
  transport: 'AMQP',
  security: [{ mtls: [] }]
}]
```

**验证**

- 前端提交新 ACS 后 Registry 校验通过。
- 审批通过后 `{AIC}` 被替换为真实 AIC。
- Discovery 能按 `endPoints.transport` 查询 JSONRPC/AMQP Agent。

---

### 3.3 ATR：HTTP-01 Challenge -> EAB

**旧链路**

```text
Agent 注册 ACS，其中 securitySchemes.mtls.x-caChallengeBaseUrl 指向 Challenge Server
Agent 向 CA 创建 ACME order
CA 从 Registry 拉 ACS
CA 生成 HTTP-01 challenge
Agent 写入 Challenge Server
CA 读取 challenge URL 验证控制权
CA 签发证书
```

**新版链路**

```text
Agent 在 Registry 审批通过并获得 AIC
Agent/Provider 从 Registry 获取一次性 EAB 凭据
Agent 使用 EAB 向 CA 创建/绑定 ACME account
CA 消费 Registry EAB，确认 account 属于该 AIC
Agent 创建 order 并 finalize CSR
CA 根据 Registry ACS 和 EAB 绑定签发证书
```

**需要修改**

| 组件 | 旧代码/行为 | 新代码/行为 | 修改动作 |
|---|---|---|---|
| Registry | 无 EAB 主链路 | `app/eab/api.py`, `app/eab/service.py`, `app/eab/model.py` | 增加 EAB 表、生成接口、内部消费接口 |
| CA | `http01_validator.py`, `agent_registry.py` 读取 challenge URL | `eab_verifier.py`, `registry_client.py.consume_eab_credential()` | 替换 HTTP-01 校验为 EAB 校验 |
| ACS | `x-caChallengeBaseUrl` 必填 | `x-caChallengeBaseUrl` 废弃 | 不再要求该字段 |
| Challenge Server | 主链路必须启动 | 官方删除 | compose/start 中移出主流程 |
| acps-cli | 旧 CA Client/手工流程 | `cert eab fetch`, `cert issue --eab-file` | 引入 CLI 作为注册/发证工具 |

**Registry 新增接口**

| 接口 | 用途 | 鉴权 |
|---|---|---|
| `POST /acps-atr-v2/eab/{agent_aic}` | 为已审批 Agent 生成一次性 EAB | Provider 登录态/Agent 所有者 |
| `POST /internal/eab/consume` | CA 内部消费 EAB | 内部服务 token |

**CA 新增/修改逻辑**

| 文件 | 修改内容 |
|---|---|
| `ca-server/app/acme/api.py` | `new-account` 解析 `externalAccountBinding` |
| `ca-server/app/acme/eab_verifier.py` | 校验 HS256、kid、payload JWK、签名，并返回绑定 AIC |
| `ca-server/app/acme/model.py` | account 增加 `aic`/绑定字段 |
| `ca-server/app/acme/service.py` | Authorization/challenge 仅兼容输出，直接 valid |
| `ca-server/app/acme/registry_client.py` | 调 Registry `/internal/eab/consume` |

**数据库新增/迁移**

- Registry：新增 EAB credential 表。
- CA：ACME account 表新增 AIC 绑定字段。
- CA：保留 challenge 表可兼容旧 ACME 输出，但不作为验证依据。

**验证**

1. 未提供 EAB 调 `new-account` 应失败。
2. 伪造 EAB 签名应失败。
3. EAB 只能消费一次。
4. account 绑定 AIC 后，只能为同一 AIC 申请证书。
5. 证书签发不再访问 Challenge Server。

---

### 3.4 证书内容：CN/SAN 变化

**旧 CA 行为**

- CN 通常构造为 `{AIC}.acps.pub`。
- SAN 包含 `agent://{AIC}` 和 endpoint URL。
- 证书前置验证依赖 challenge URL。

**新版 CA 行为**

- CN 直接使用裸 AIC。
- 默认 SAN 为 `URI:acps://{AIC}`。
- 额外 DNS/IP SAN 只能来自 ACS `certificate.altNames`。
- 有效期读取 ACS `certificate.requestedValidity`，但由 CA 上限裁剪。

**需要修改**

| 文件 | 修改内容 |
|---|---|
| `ca-server/app/core/ca_manager.py` | 按新版 CN/SAN 生成证书 |
| `ca-server/app/acme/registry_client.py` | 解析 ACS `certificate.altNames`, `requestedValidity` |
| `registry-server/app/agent/acsSchema.json` | 增加 certificate schema |
| 前端申请页 | 增加证书 SAN 和有效期输入 |
| mTLS 校验方 | 从证书中读取 `acps://{AIC}` 或 CN=AIC，不再依赖 `{AIC}.acps.pub` |

**验证**

- 新证书 CN 为 AIC。
- SAN 至少包含 `URI:acps://{AIC}`。
- ACS 里配置的 DNS/IP 被写入 SAN。
- 超过 CA 上限的 requestedValidity 会被裁剪。

---

## 4. Registry 端改造清单

### 4.1 包版本和运行时

| 项 | 旧版 | 新版 | 修改建议 |
|---|---|---|---|
| 包版本 | `2.0.0` | `2.1.0` | 升级项目版本和接口说明 |
| Python | `>=3.13,<4.0` | `>=3.14,<4.0` | 短期不强切 py3.14；长期准备新运行时 |
| DB 驱动 | `asyncpg`, `psycopg2-binary` | `asyncpg`, `psycopg[binary]` | 检查远端 `.py312deps` / `.venv` 是否满足 |
| 构建 | poetry-core | hatchling | 若采用官方新版，更新 build/deploy 脚本 |

**远端启动注意**

用户已说明：`asyncpg` 在 `.py312deps`，`xattr` 在 `.venv`。升级启动脚本仍需同时带这两份路径，直到依赖收敛：

```bash
export PYTHONPATH=/home/johnteller/team_ws/sds/registry-server:/home/johnteller/team_ws/sds/registry-server/.py312deps:/home/johnteller/team_ws/sds/registry-server/.venv/lib/python*/site-packages:$PYTHONPATH
```

实际路径需远端复核。

---

### 4.2 API 前缀和前端兼容

**旧版**

- `API_V1_STR = "/api"`
- 前端 axios `baseURL: '/api'`

**新版官方默认**

- `api.v1_str = "/api/v1"`

**需要修改**

| 方案 | 修改内容 | 推荐度 |
|---|---|---|
| 保留 `/api` | 新版 Registry config 中设回 `/api`，前端不用大改 | 短期推荐 |
| 网关重写 | `/api/* -> /api/v1/*`，但 points/passport 等平台接口单独保留 | 中期可选 |
| 前端全改 `/api/v1` | 修改所有 API 调用 | 不推荐首阶段做 |

涉及文件：

- `/home/johnteller/team_ws/wyl/frontend/src/api/index.js`
- `/home/johnteller/team_ws/wyl/server/server.py`
- `/home/johnteller/team_ws/sds/registry-server/app/core/config.py`
- 新版 `registry-server/config/default.toml`

---

### 4.3 模块结构变化

| 当前旧模块 | 新版变化 | 改造动作 |
|---|---|---|
| `app/agent/service.py` 大文件 | 拆为 `service_acs.py`, `service_atr.py`, `service_command.py`, `service_query.py` | 如果 rebase 到新版，要把 RenTA 自定义逻辑迁到对应新 service |
| `app/events` | 官方新版无 | 作为 RenTA 平台扩展保留，避免被覆盖 |
| `app/points` | 官方新版无 | 作为 RenTA 平台扩展保留，Mode Router 结算依赖它 |
| `app/agent/supervisor.py` | 官方新版删除 | Passport/supervisor 审核若仍用，需要迁成扩展模块 |
| `app/eab` | 新增 | 必须引入 |
| `app/verification` | 新增 | 可用于身份/组织审核，可和现有审核体系整合 |
| `app/sync/api.py` | 新版拆为 `api_admin.py`, `api_protocol.py`, `api_webhook.py` | 路由可保持不变，内部代码按新版拆分 |

---

### 4.4 Agent API 差异

| 接口 | 当前旧版 | 新版 | 修改动作 |
|---|---|---|---|
| `/api/agent/public/acs_example` | 有 | 有 | 更新示例为 ACS 02.01 |
| `/api/agent/public/recent` | 有 | 有 | 保持前端 Agent Square 可用 |
| `/api/agent/client/{id}/passport/latest` | 旧平台有 | 官方新版无 | 作为平台扩展保留或改到 `/api/platform/passports` |
| `/api/agent/client/{id}/supervisor-review/latest` | 旧平台有 | 官方新版无 | 作为平台扩展保留 |
| `/acps-atr-v2/passports/discovery` | 旧平台有 | 官方新版无 | 短期保留给 Mode Router；中期迁到 Discovery |
| `/acps-atr-v2/passports/{aic}/dispatch` | 旧平台有 | 官方新版无 | 保留为平台调度策略接口 |
| `/acps-atr-v2/passports/runtime-review/schedule` | 旧平台有 | 官方新版无 | 保留或改成后台任务接口 |
| `/acps-atr-v2/acs/{aic}` | 有 | 有 | 校验逻辑升级到 AIC v02.01，旧 AIC legacy 兼容 |
| `/acps-atr-v2/entity` | 旧 public/API token 语义 | 新版 mTLS 平面 | 改为 mTLS listener 9002 或保留兼容 wrapper |
| `/acps-atr-v2/eab/{aic}` | 无 | 新增 | 必须实现 |
| `/internal/eab/consume` | 无 | 新增 | 必须实现，CA 调用 |

---

### 4.5 Registry 数据库迁移点

| 数据 | 当前 | 升级修改 |
|---|---|---|
| Agent AIC | 旧 AIC 直接存在 `agent.aic` | 增加 AIC 版本/映射；新 AIC 重新分配 |
| Agent ACS | 可能为 v02.00，含 challenge 字段 | 增加 ACS 版本迁移；编辑时升级到 v02.01 |
| Passport | 平台自定义 | 保留；但不要混入官方协议核心表 |
| SupervisorReview | 平台自定义 | 保留或迁移到 platform schema |
| Points | 平台自定义 | 保留，Mode Router 依赖 |
| Events | 平台自定义 | 保留，前端运行态可能依赖 |
| Sync Snapshot/Changelog/Webhook | v2.0 已有 | 按 v2.1 迁移脚本升级，注意 JSONB/timestamptz |
| EAB Credential | 无 | 新增表，字段含 key_id/mac_key/aic/expires/consumed |
| Verification | 无或平台已有其他审核 | 可新增官方 verification 表，和现有用户审核区分 |

---

## 5. CA Server 改造清单

### 5.1 包版本与依赖

| 项 | 旧版 | 新版 | 修改建议 |
|---|---|---|---|
| 包版本 | `2.0.0` | `2.1.0` | 升级版本 |
| Python | `>=3.13,<4.0` | `>=3.14,<4.0` | 与 Registry 同步规划 |
| DB | `psycopg2-binary` | `psycopg[binary]` + `asyncpg` | 检查部署依赖 |
| 结构 | `services.py`, `models.py` | `service.py`, `model.py`, `schema.py` | rebase 时注意 import 名变化 |

---

### 5.2 ACME/EAB 主链路

| 文件 | 当前旧版 | 新版 | 修改动作 |
|---|---|---|---|
| `app/acme/api.py` | challenge 驱动 order ready | EAB 绑定 account，challenge 兼容输出 | 合并新版逻辑 |
| `app/acme/agent_registry.py` | 读取 ACS 的 `x-caChallengeBaseUrl` | 被 `registry_client.py` 替代 | 改调用 Registry EAB consume 和 ACS certificate 字段 |
| `app/acme/http01_validator.py` | 主验证器 | 新版删除 | 删除主流程引用 |
| `app/acme/eab_verifier.py` | 无 | 新增 | 引入 |
| `app/acme/model.py` | 旧 `models.py` | 新 model 字段含 account AIC | 迁移 DB model/import |
| `app/acme/service.py` | 旧 `services.py` | 新 service | 按新版拆分/重命名 |

---

### 5.3 CA 外部接口

| 接口 | 当前 | 新版 | 修改动作 |
|---|---|---|---|
| `/acps-atr-v2/acme/directory` | 有 | 有 | 保持 |
| `/new-nonce` | 有 | 有 | 保持 |
| `/new-account` | JWS，可选外部绑定/旧逻辑 | 必须 EAB 绑定 AIC | 强制校验 EAB |
| `/new-order` | 创建 challenge | 直接生成 valid authorization | 不再要求 HTTP-01 |
| `/challenge/{id}` | 真实验证入口 | 兼容/只读/直接 valid | 保留响应形状，避免旧客户端崩 |
| `/order/{id}/finalize` | CSR 签发 | 使用 ACS certificate 字段签发 | 修改证书参数来源 |
| `/cert/{id}` | 有 | 有 | 保持 |
| `/revoke-cert` | 有 | 有 | 保持 |
| `/acps-atr-v2/ca/trust-bundle` | 有 | 有 | 保持，检查证书链格式 |
| `/passport-sync`, `/revoke-notify` | 旧平台扩展 | 官方新版可能收缩 | 如平台依赖，保留扩展 |

---

### 5.4 Challenge Server 下线

**需要改的文件**

| 文件 | 修改内容 |
|---|---|
| `registry_stack/docker-compose.yml` | 删除/注释 `challenge-server` 服务，或 profile=legacy |
| `registry_stack/scripts/challenge-start.sh` | 标记 legacy，不参与默认启动 |
| `ops/start_stack.sh` | 不再默认启动 challenge |
| `docs/start_all_servers.sh` | 不再把 8004 作为必需健康检查 |
| `frontend_source/src/views/AgentApplyView.vue` | 删除默认 challenge URL |
| `ca-server/app/acme/http01_validator.py` | 删除引用，文件可保留 legacy |
| `ca-server/tests/test_acme.py` | 修改 challenge 断言，改为 EAB 断言 |

**保留方式**

- 如果要兼容历史 Agent，可让旧 challenge server 继续单独跑，但不用于新证书申请。
- 文档明确：v2.1 主流程不依赖 challenge。

---

## 6. 前端与网关改造清单

### 6.1 前端 API baseURL

当前：

```js
const api = axios.create({ baseURL: '/api' })
export const modeRouterApi = axios.create({ baseURL: '/mode-router' })
```

**修改建议**

- 首阶段保留 `/api`。
- 后端/网关负责兼容 `/api` 与新版 Registry。
- 不要首阶段把全部前端调用改成 `/api/v1`。

### 6.2 Agent 申请页

| UI/逻辑 | 当前 | 新版修改 |
|---|---|---|
| 协议版本 | 固定 `02.00` | 改 `02.01` |
| AIC | 前端临时生成非法/占位 AIC | 前端只填 `{AIC}` 占位或空；审批后后端写入 |
| mTLS | 必填 challenge URL | 删除 challenge 必填 |
| transport | `HTTP` | 改为 `JSONRPC`/`HTTP_JSON`/`AMQP` |
| certificate | 无 | 增加 SAN DNS/IP、有效期字段 |
| AMQP | 无 | 增加 Inbox endpoint 模板 |
| 预览 ACS | 旧 schema | 更新到 v02.01 |
| 表单校验 | URL/challenge 校验 | transport 对应校验：JSONRPC URL、HTTP_JSON base URL、AMQP URL |

### 6.3 网关 `server.py`

当前提交包网关代理：

```py
("/api/",           "http://localhost:8001/",  False),
("/mode-router/",   "http://localhost:18080/", True),
("/agent-rpc/",     "http://localhost:19090/", True),
("/acps-atr-v2/",   "http://localhost:8001/",  False),
("/acps-dsp-v2/",   "http://localhost:8001/",  False),
("/acps-adp-v2/",   "http://localhost:8005/",  False),
```

**升级修改**

| 路由 | 短期目标 | 长期目标 |
|---|---|---|
| `/api/` | 继续指向平台 Registry/API | 可拆到 platform-api |
| `/api/v1/` | 可选新增指向新版 Registry | 官方兼容入口 |
| `/acps-atr-v2/acs` | Registry | Registry public |
| `/acps-atr-v2/eab` | Registry | Registry public |
| `/acps-atr-v2/acme` | CA | CA |
| `/acps-atr-v2/ca`, `/crl`, `/ocsp` | CA | CA |
| `/acps-dsp-v2/` | Registry | Registry DSP |
| `/acps-adp-v2/` | Discovery | Discovery |
| `/mq-auth/` | 新增 mq-auth-server | mq-auth-server |
| `/mode-router/` | 保持 | 保持 |

注意：现在 `/acps-atr-v2/` 全部指到 Registry。升级 EAB/CA 后，应按路径细分 Registry 与 CA，否则 ACME 发证接口会走错服务。

---

## 7. Orchestrator / Mode Router 改造清单

### 7.1 Registry discovery / Passport 依赖

当前文件：

- `orchestrator/mode_router/registry_client.py`
- 远端：`/home/johnteller/team_ws/th/...`

当前调用：

```py
passports/discovery
passports/{agent_aic}/dispatch
passports/runtime-review/schedule
/api/points/internal/agent-call
```

新版官方 Registry 不提供这些平台接口。

**需要修改**

| 调用 | 当前用途 | 升级处理 |
|---|---|---|
| `passports/discovery` | 从 Registry 找可调度 Agent | 短期保留；中期改用 Discovery `/acps-adp-v2/discover` |
| `passports/{aic}/dispatch` | 调度前检查 | 保留为 RenTA 平台策略服务，不属于 ACPs 核心 |
| `runtime-review/schedule` | 运行期复核/证书同步 | 改为后台任务或 platform API |
| `points/internal/agent-call` | 积分结算 | 保留 platform API |

### 7.2 Discovery 适配

新版 ADP 返回结构强调：

- `agents`
- `acsMap`
- `routes`
- `agentGroups`
- `forwardChain`

当前适配器文件：

- `orchestrator/mode_router/adapters.py`
- `orchestrator/mode_router/discovery_client.py`

**需要修改**

- 确认 `extract_skills_from_discovery_response()` 完整支持新版 `acsMap`。
- 过滤 transport：优先 JSONRPC/AMQP，HTTP_JSON 作为普通 API endpoint。
- 如果 Discovery 返回 AMQP endpoint，group executor 应优先 Inbox。
- 如果 Discovery 返回 JSONRPC endpoint，仍走 direct RPC fallback。

### 7.3 Group Executor：Direct RPC -> Inbox 优先

当前：

- `rabbitmq_port=5672`
- `rabbitmq_user=guest`
- `rabbitmq_password=guest`
- `rabbitmq_vhost='/'`
- `leader.invite_partner(... partner_rpc_url=...)`

新版：

- `5671` AMQPS
- vhost `acps`
- mTLS EXTERNAL auth
- Inbox 队列 `inbox_{AIC}`
- `mq-auth-server` 管理 ACL

**需要修改**

| 文件 | 修改内容 |
|---|---|
| `generic_group_executor.py` | 配置支持 `amqps`, cert/key/ca, vhost=`acps` |
| `generic_group_executor.py` | 从 ACS 读取 AMQP endpoint，优先 Inbox 邀请 |
| `travel_group_bridge.py` | 兼容新版 `RabbitMQRequest`，`accessToken` 可空 |
| `mode_router_service.py` / `service.py` | 增加 `execution_transport='mq_inbox'` 分支 |
| `.env` / 启动脚本 | 增加 RabbitMQ 5671、证书路径、mq-auth 地址 |

**兼容策略**

```text
if partner ACS has AMQP endpoint:
    use MQ Inbox invitation
elif partner ACS has JSONRPC group endpoint:
    use Direct RPC invitation fallback
else:
    mark unavailable
```

---

## 8. Discovery Server 改造清单

| 当前 | 新版 | 修改动作 |
|---|---|---|
| 当前平台通过 `/acps-adp-v2/discover` 访问已有 Discovery | 官方提供 `discovery-server` | 建议引入官方新版作为主服务 |
| Registry public recent fallback | Discovery 主查询，Registry fallback | Mode Router 调整优先级 |
| DSP 同步可能是旧实现 | 新版 Discovery 从 Registry DSP 拉 ACS | 确认 `/acps-dsp-v2/info/changes/snapshots/webhooks` 可用 |
| Discovery 端口旧为 8005 | 官方默认 9005 | 网关保留 `/acps-adp-v2`，内部端口可继续 8005 或迁 9005 |

**验证**

- Registry 审批通过 Agent 后，Discovery 能拉到 ACS。
- Discovery query 返回 `acsMap`。
- Mode Router 能从 Discovery response 选出 Agent。

---

## 9. MQ / mq-auth-server 改造清单

新版 v2.1 要支持 Inbox 群组，需要新增：

| 组件 | 修改动作 |
|---|---|
| RabbitMQ | 启动 5671 AMQPS，TLS 1.3，加载 CA/服务端证书 |
| RabbitMQ vhost | 建立共享 vhost `acps` |
| RabbitMQ auth backend | 接入 `mq-auth-server` |
| mq-auth-server | 部署 group API 9007、auth API 9008 |
| ACL | Leader 创建 group exchange/queue 前调用 mq-auth-server 配置 ACL |
| Agent 证书 | 用 ACPs CA 签发，支持 clientAuth/serverAuth 按需 |
| ACS | Partner 增加 AMQP endpoint `inbox_{AIC}` |
| CLI | 用 `acps-cli admin mq health` 验证 |

**旧兼容**

- `accessToken` 字段保留但标记 deprecated。
- 如果 `accessToken` 存在，按旧账号密码连接；为空则按 mTLS EXTERNAL 连接。

---

## 10. SDK / CLI 改造清单

### 10.1 SDK

| 当前 | 新版 | 修改动作 |
|---|---|---|
| 编排端依赖旧 `acps_sdk.aip` | 新版 `acps-sdk` 增加 Inbox、AMQP runtime、mTLS config | 更新 PYTHONPATH/依赖版本 |
| `GroupLeader` 旧邀请方式 | 新版支持 AMQP endpoint 与 Inbox | 调用新 API 或兼容封装 |
| `RabbitMQRequest.accessToken` | 常用 | deprecated | 允许为空，走 mTLS |

### 10.2 CLI

新版 `acps-cli` 负责：

- `auth login`
- `agent save/submit/check`
- `cert eab fetch`
- `cert issue --eab-file`
- `entity derive --mtls-url`
- `admin discovery run-sync`
- `admin mq health`

**需要新增到运维文档**

```bash
uv run acps-cli auth login --username alice --password 'S3cret!'
uv run acps-cli agent save --acs-file ./acs.json --json
uv run acps-cli agent submit --agent-id <AGENT_UUID> --json
uv run acps-cli cert eab fetch --aic <AIC> --output ./private/eab.json
uv run acps-cli cert issue --aic <AIC> --eab-file ./private/eab.json --usage clientAuth
```

---

## 11. 部署与启动脚本改造清单

| 文件 | 当前问题 | 修改动作 |
|---|---|---|
| `registry_stack/docker-compose.yml` | 启动 challenge-server；端口旧；CA/Registry 路由混杂 | 移除 challenge 主服务；新增/配置 mq-auth；区分 CA/Registry ATR 路由 |
| `ops/start_stack.sh` | 默认启动 registry/challenge/ca | challenge 改 legacy；增加 discovery/mq-auth 可选启动 |
| `docs/start_all_servers.sh` | 健康检查旧端口 | 更新 9001/9002/9003/9005 或保留旧端口映射 |
| `wyl/server/server.py` | `/acps-atr-v2` 全指 Registry | 按 `/acme`, `/ca`, `/crl`, `/ocsp` 分流到 CA |
| 环境变量 | `CA_CHALLENGE_*`、`CHALLENGE_WRITE_TOKEN` | 删除主链路；新增 EAB/MTLS/MQ 变量 |
| `.py312deps`/`.venv` | 远端当前依赖路径分散 | 记录在启动脚本；长期改成统一 venv/uv |

**建议端口策略**

短期保留用户访问不变：

- 平台入口：`10.126.126.8:8888`
- Registry 内部：继续 `8001` 或映射新版 `9001 -> 8001`
- CA 内部：继续 `8003` 或映射新版 `9003 -> 8003`
- Discovery：继续 `8005` 或映射新版 `9005 -> 8005`
- Registry mTLS：新增 `9002`，不建议代理到普通 HTTP 网关
- RabbitMQ AMQPS：新增/启用 `5671`
- mq-auth：新增 `9007/9008`

---

## 12. 测试用例改造清单

| 测试范围 | 必测点 |
|---|---|
| AIC | v02.01 生成/校验；旧 AIC legacy 兼容；实体 AIC 生成 |
| ACS | v02.01 schema；AMQP endpoint；certificate 字段；废弃 challenge 字段 |
| Registry EAB | EAB 生成、过期、一次性消费、权限校验 |
| CA EAB | new-account 无 EAB 失败；伪造签名失败；正确 EAB 成功 |
| CA 证书 | CN=AIC；SAN=acps://AIC；altNames 生效；有效期裁剪 |
| Challenge legacy | 新发证不访问 challenge-server |
| Entity mTLS | 无证书失败；证书 AIC 与 ontologyAic 不匹配失败；匹配成功 |
| Frontend | Agent 申请、审批、详情、Square、账户、积分仍可用 |
| Mode Router | Registry fallback、Discovery query、dispatch guard、points settlement |
| MQ Inbox | AMQP endpoint 发现；Inbox 邀请；Partner 加入；失败 fallback |
| 网关 | `/api`、`/acps-atr-v2/acme`、`/acps-atr-v2/ca`、`/acps-adp-v2` 路由正确 |
| 数据迁移 | 旧 Agent 可读；新 Agent 可注册；旧日志/积分可查 |

---

## 13. 推荐分支和实施顺序

```text
upgrade/acps-v2.1-baseline
  只固定新版 ACPs-community commit，保存当前远端基线

upgrade/acps-v2.1-aic-acs
  AIC v02.01 + ACS v02.01 + 前端申请页

upgrade/acps-v2.1-eab-ca
  Registry EAB + CA EAB + challenge legacy

upgrade/acps-v2.1-discovery-router
  Discovery v2.1 + Mode Router ADP 适配

upgrade/acps-v2.1-mq-inbox
  RabbitMQ AMQPS + mq-auth-server + Inbox group
```

首个可交付版本建议只做到，并且必须以“不影响原有功能”为验收前提：

1. AIC v02.01。
2. ACS v02.01。
3. EAB 发证。
4. 前端申请页/网关兼容。
5. Challenge Server 不再参与主链路。
6. 旧 `/api`、旧页面、旧 Agent 查询、旧积分/事件/编排流程全部通过回归测试。

---

## 14. 不建议直接修改/覆盖的点

| 不建议动作 | 原因 |
|---|---|
| 直接用 ACPs-community/registry-server 覆盖 `/home/johnteller/team_ws/sds/registry-server` | 会丢失 RenTA 的 points、events、Passport、Supervisor、前端兼容 API |
| 直接删除 `/api` 改 `/api/v1` | 前端大量接口会断 |
| 一次性强制所有旧 AIC 失效 | 历史数据、证书、积分、日志、Discovery 都会断 |
| 一次性切到 MQ Inbox | 当前 Partner/Bridge 未必有 AMQP endpoint 和证书 |
| 继续让新证书依赖 Challenge Server | 与 v2.1 主协议不一致 |
| 让前端生成真实 AIC | AIC 应由 Registry 审批/分配，前端只用占位符或空值 |

---

## 15. 远端复核命令

SSH 可用后执行：

```bash
cd /home/johnteller/team_ws

# 版本和目录
find sds th wyl -maxdepth 3 -type f \
  \( -name '*.py' -o -name '*.js' -o -name '*.vue' -o -name '*.json' -o -name '*.yml' -o -name '*.toml' -o -name '*.md' \) \
  -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/.py312deps/*' \
  | sort > /tmp/renta-source-files.txt

# 关键协议耦合点
grep -RInE 'ACPs|AIC|ACS|ATR|ADP|AIP|EAB|challenge|x-caChallengeBaseUrl|passports|discovery|registry|certificate|mTLS|RabbitMQ|AMQP|Inbox|JSONRPC' \
  sds th wyl \
  --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.py312deps --exclude-dir=dist \
  > /tmp/renta-acps-coupling.txt || true

# 服务端口
ss -ltnp | egrep '(:8888|:8001|:8003|:8004|:8005|:9001|:9002|:9003|:9005|:5671|:5672|:9007|:9008|:18080|:19090)' || true
```

---

## 16. 最终判断

- **短期兼容升级：可控，建议做。** 重点是 AIC/ACS/EAB/CA/前端/网关。
- **前提约束：不能影响原有功能。** 因此升级实现上应“移植协议模块 + 保留平台自定义模块 + 兼容旧 API/旧数据”，不能直接覆盖式替换。
- **完整 v2.1 协议升级：中高难度。** 重点是 mTLS entity、Discovery、MQ Inbox、mq-auth-server、数据迁移。
- **架构建议：协议基础设施与 RenTA 平台能力分层。** Registry/CA/Discovery/MQ Auth 尽量贴近 ACPs-community；points、Passport、dispatch、前端管理、Mode Router 放平台层。
