# RenTA ACPs v2.1 全面升级最终验收报告

更新时间：2026-07-11

## 1. 最终结论

RenTA 现在已经是 **ACPs v2.1 升级后的运行版本**，不是仅完成代码集成但仍运行旧协议的状态。

当前结论如下：

| 问题 | 结论 |
|---|---|
| 协议代码是否升级 | 是。AIC/ACS 02.01、EAB、CA、Discovery、MQ Inbox/mTLS 已集成 |
| 线上运行配置是否升级 | 是。v2.1 主链路开关已持久启用并重启生效 |
| 是否还必须灰度 | 否。当前已经正式启用；灰度不再是完成升级的前置步骤 |
| 原有功能是否保留 | 是。02.00、旧 API、Challenge、Registry fallback、RabbitMQ 5672、Direct RPC/HTTP 均保留 |
| 是否完成 PC 端测试 | 是。启用 v2.1 后重新完成 PC 页面和主要业务流程测试 |
| 真实 Agent 业务结果是否纳入门禁 | 否。当前登记的 Agent endpoint 不可用，按验收约定不作为阻塞项 |

平台地址：`http://10.126.126.8:8888`

远端代码状态：

```text
repository=/home/johnteller/team_ws
branch=upgrade/acps-v2.1-mq-inbox
runtime_activation_commit=aee049c7195c9fd38280ba89ced12c7aaebd6edd
```

## 2. 本报告中“已升级”的含义

为了避免“代码已升级”和“线上已启用”混淆，本次验收同时满足以下四项才定义为升级完成：

1. **代码能力已存在**：项目包含 ACPs v2.1 所需的协议模型、接口、数据库 migration 和通信实现。
2. **运行开关已开启**：正在运行的 Registry、CA、前端、Discovery、Mode Router 进程实际读取到新版开关为 `true`。
3. **新版链路已验证**：02.01 ACS、EAB、Discovery 和 MQ Inbox/mTLS 均有专项或端到端测试。
4. **旧功能仍可用**：旧 API、02.00、Challenge、Registry fallback、5672 和 HTTP/RPC 路径未删除。

因此，当前状态不是“等待灰度”，而是“v2.1 正式启用，同时保留旧协议兼容和紧急回退能力”。

## 3. 阶段交付

| 阶段 | 状态 | 核心结果 |
|---|---|---|
| 0 基线 | 完成 | 冻结目录、端口、数据库和回归基线 |
| 1 AIC/ACS | 完成 | 支持 02.00/02.01 双轨 |
| 2 Registry EAB | 完成 | SM4 密文存储、一次性消费和 migration |
| 3 CA EAB | 完成 | EAB account/order/finalize、AIC 绑定和 02.01 证书 |
| 4 前端/网关 | 完成 | 02.01 表单、EAB UI、CA 路由和外部 URL 重写 |
| 5 Discovery | 完成 | `/acps-adp-v2/discover`、Registry 同步和 fallback |
| 6 MQ/mTLS | 完成 | RabbitMQ 5671、mq-auth、Inbox 和隔离版 v2.1 SDK |
| 7 全量回归 | 完成 | PC 路由修复、全服务测试和兼容性验收 |
| 8 正式启用 | 完成 | v2.1 主链路默认开启，旧链路继续保留 |

## 4. 当前运行拓扑

| 服务 | 端口 | 当前状态 | 作用 |
|---|---:|---|---|
| Registry | 8001 | active，v2.1 enabled | Agent 注册、AIC/ACS、EAB 签发与消费 |
| CA | 8003 | active，EAB enabled | ACME account、order、证书签发、CRL/OCSP |
| Challenge legacy | 8004 | active | 为旧 account 保留 HTTP-01 Challenge |
| Discovery v2.1 | 8005 | active | ACPs 02.01 Agent/Skill 发现 |
| Group bridge | 8098 | active，MQ Inbox enabled | 群组任务和 Inbox consumer 管理 |
| Group proxy | 8099 | active | 原平台 Agent 代理兼容路径 |
| 平台网关/前端 | 8888 | active，02.01 default | PC 页面和 API 反向代理 |
| Mode Router | 18080 | active | Discovery 优先、任务编排和 MQ/legacy 回退 |
| Direct RPC | 19090 | active | 原有直接 RPC 路径 |
| RabbitMQ legacy | 5672 | active | 原有明文 AMQP/vhost `/` 兼容路径 |
| RabbitMQ mTLS | 5671 | active | ACPs v2.1 AMQPS Inbox |
| mq-auth Group/Auth | 9007/9008 | active | mTLS 身份、Group ACL 和 RabbitMQ 授权 |
| Redis ACL | 6379 localhost | active | mq-auth 动态群组访问控制 |

## 5. 运行变量及含义

### 5.1 Registry

| 变量 | 当前值 | 含义 | 关闭后的影响 |
|---|---|---|---|
| `ACPS_V21_ENABLED` | `true` | Registry 启用 ACPs 02.01 写入、校验和默认协议行为 | 新写入恢复为旧协议行为；已有 02.01 数据不删除 |
| `ACPS_LEGACY_API_ENABLED` | `true` | 保留旧 API 和 02.00 兼容入口 | 设为 `false` 会影响旧客户端，因此当前必须保持 `true` |
| `ACPS_AIC_DUAL_READ_ENABLED` | `true` | 同时识别旧版和新版 AIC | 关闭后可能无法读取历史 AIC，不应关闭 |
| `ACPS_EAB_ISSUANCE_ENABLED` | `true` | 注册 EAB 签发接口和内部一次性消费接口 | 新 02.01 account 无法从 Registry 获取 EAB |

### 5.2 CA 与前端

| 变量 | 当前值 | 含义 | 关闭后的影响 |
|---|---|---|---|
| `ACPS_CA_EAB_ENABLED` | `true` | 新 02.01 ACME account 必须通过 EAB 绑定 AIC | 新 account 回到旧 Challenge 流程；旧证书不受影响 |
| `ACPS_CHALLENGE_LEGACY_ENABLED` | `true` | 旧 account 继续使用 HTTP-01 Challenge | 关闭会破坏旧 account 续用能力，因此保持开启 |
| `ACPS_FRONTEND_V21_ENABLED` | `true` | Agent 申请页默认选择 ACPs 02.01 | 关闭后前端默认显示兼容 02.00 |
| `ACPS_FRONTEND_EAB_ENABLED` | `true` | 前端显示 EAB 获取区域和 CA Directory | 关闭后 UI 不再提供 EAB 操作，但后端能力仍可存在 |

### 5.3 Discovery 与 MQ

| 变量 | 当前值 | 含义 | 关闭后的影响 |
|---|---|---|---|
| `ACPS_DISCOVERY_V21_ENABLED` | `true` | Mode Router 优先调用 v2.1 Discovery 服务 | 调度恢复为 Registry Passport discovery |
| `ACPS_DISCOVERY_LEGACY_FALLBACK_ENABLED` | `true` | Discovery 空结果、错误或不可用时回退 Registry | 关闭后 Discovery 故障会直接影响 Agent 候选发现 |
| `ACPS_MQ_AUTH_ENABLED` | `true` | 启动并使用 mq-auth 身份与 ACL 服务 | 新 AMQPS 群组授权不可用 |
| `ACPS_MQ_INBOX_ENABLED` | `true` | 群组通信优先使用 ACPs v2.1 MQ Inbox | 群组通信回到 Direct RPC/HTTP 或旧 AMQP 路径 |
| `ACPS_MQ_LEGACY_FALLBACK_ENABLED` | `true` | MQ Inbox 建链失败时允许旧执行路径接管 | 关闭后 MQ 异常可能直接导致任务失败 |

### 5.4 CA 中保留的 legacy mock 变量

当前 CA 还保留：

```text
AGENT_REGISTRY_MOCK=true
HTTP01_VALIDATION_MOCK=true
```

这两个变量属于原平台旧 Challenge 环境，不代表 v2.1 EAB 使用假数据：

- `AGENT_REGISTRY_MOCK=true` 只在 `require_challenge=true` 的旧证书路径返回旧版模拟 Agent 信息。
- v2.1 EAB 的 `/internal/eab/consume` 始终真实调用 Registry，不经过该 mock。
- EAB account 后续 ACS 查询使用 `require_challenge=false`，代码会绕过 legacy Registry mock 并访问真实 Registry。
- `HTTP01_VALIDATION_MOCK=true` 只影响旧 HTTP-01 Challenge；v2.1 EAB account 不依赖 HTTP-01。

因此当前 v2.1 EAB 绑定、一次性消费、HMAC 校验和 ACS 校验仍是真实实现。未来恢复可用的旧 Agent Challenge endpoint 后，可以单独将这两个 legacy mock 变量设为 `false`。

## 6. 新旧请求链路

### 6.1 新注册 Agent

```text
PC 申请页默认 02.01
  -> Registry 创建/校验 02.01 AIC 与 ACS
  -> Registry 签发一次性 EAB
  -> CA 消费 EAB 并绑定 ACME account AIC
  -> CA 校验 order、CSR Subject/SAN 并签发证书
  -> Discovery 发布 02.01 能力
  -> Mode Router 优先 Discovery
  -> 群组任务优先 MQ Inbox/mTLS
```

### 6.2 历史 Agent 和旧客户端

```text
02.00 / 旧 API
  -> Registry dual-read
  -> Challenge legacy
  -> Registry Passport fallback
  -> RabbitMQ 5672 / Direct RPC / HTTP
```

新版链路已成为默认路径，但旧链路并未删除。

## 7. 自动化验收

启用 v2.1 后重新生成的验收归档：

```text
/home/johnteller/team_ws/_archive/stage0_regression_20260711_095633
```

| 套件 | 结果 |
|---|---|
| 只读 HTTP smoke | 18/18 |
| Registry | 133 passed，6 deselected |
| CA | 131 passed |
| Challenge | 4 passed |
| Mode Router tests | 48 passed，3 deselected |
| Mode Router sequential | 1 passed |
| Mode Router root | 17 passed，1 deselected |
| Discovery | 4 passed |
| Gateway | 12 passed |
| mq-auth | 185 passed |
| ACPs v2.1 SDK | 27 passed |
| 前端 02.00/02.01 payload | passed |
| 真实 MQ Inbox mTLS | passed |

真实 MQ Inbox E2E 的关键结果：

```text
invitation_route=inbox
task_result=mq inbox e2e ok
execution_transport=mq_inbox
```

E2E 后 Group bridge 继续健康，`mqInboxEnabled=true`，动态测试连接已退出。

## 8. PC 浏览器验收

测试环境：Chrome/Playwright，视口 `1440x1000`。

| 流程 | 启用 v2.1 后的结果 |
|---|---|
| 首页 | 正常显示，无横向溢出，无 console error |
| Agent 广场 | 加载 12 个实际 Agent，分类和页面布局正常 |
| 注册、登录 | API 和页面流程正常 |
| Agent 申请 | 默认选中 `ACPs 02.01` |
| EAB UI | “获取 EAB”和 CA Directory 正常显示 |
| 02.01 ACS 预览 | 生成 `protocolVersion: 02.01`、mTLS、certificate 等字段 |
| 02.00 兼容切换 | 切换后生成 `protocolVersion: 02.00`，旧表单仍可用 |
| 数据提交 | 本次只预览 ACS，未提交测试 Agent |

截图：

```text
D:/B-EP1/output/playwright/v21-enabled-pc-home.png
D:/B-EP1/output/playwright/v21-enabled-pc-agent-apply-preview.png
```

临时测试用户、角色关联和浏览器会话均已清理。移动端不在本次验收范围内。

## 9. 原有功能保护

- Registry 原有积分、事件、Passport 和 Supervisor 模块未被官方代码覆盖。
- CA 历史 account、证书、CRL、OCSP 和 Challenge 数据保留。
- RabbitMQ 5672 和 vhost `/` 保留，旧邀请链路已验证。
- 原 `acps_sdk.aip` 未被覆盖，v2.1 SDK 使用隔离命名空间。
- Direct RPC、HTTP、group bridge/proxy 未删除。
- 02.00 申请页和 payload 继续通过测试。
- 数据库 migration 已做生产副本 upgrade/downgrade 验证。

## 10. 当前边界

当前 Registry 中被选中的真实 Agent RPC endpoint `10.126.126.1:8026` 不可达，因此没有可用 Agent 返回最终业务内容。已验证请求能够进入平台、完成发现、分类和编排；按验收约定，外部 Agent 的业务输出不作为本次协议升级阻塞项。

Group bridge 健康状态中的 `mqInboxConsumers=0` 表示当前没有真实外部 Agent 长连接，不表示 MQ Inbox 未启用。真实 E2E 使用测试 Leader/Partner 完成了邀请、任务、结果和 ACL 清理。

已知非阻塞日志：官方 MQ SDK 在 Partner 退出时可能在 exchange 已关闭后再次发送 leave 状态，产生两条 `RobustChannel closed` 清理日志。E2E 返回码、任务结果和 ACL 清理均正常。

## 11. 回退变量的定位

现在不需要再执行灰度。以下开关保留的目的，是出现生产故障时按模块快速回退，不是表示升级尚未完成：

| 故障范围 | 临时回退方式 | 保留的旧能力 |
|---|---|---|
| MQ Inbox | `ACPS_MQ_INBOX_ENABLED=false` | Direct RPC、HTTP、5672 |
| Discovery | `ACPS_DISCOVERY_V21_ENABLED=false` | Registry Passport discovery |
| CA/EAB | `ACPS_CA_EAB_ENABLED=false`、`ACPS_EAB_ISSUANCE_ENABLED=false` | Challenge legacy、旧证书 |
| 前端 02.01 | `ACPS_FRONTEND_V21_ENABLED=false`、`ACPS_FRONTEND_EAB_ENABLED=false` | 02.00 申请页 |

正常运行时不需要关闭这些新版开关。

## 12. 最终判定

RenTA 已完成 ACPs v2.1 的代码升级、运行配置切换、服务重启、自动化测试和 PC 端验收。当前线上默认使用 v2.1 主链路，同时保留原平台旧功能兼容及故障回退入口。
