# RenTA ACPs v2.1 协议升级与平台完善模块清单

更新时间：2026-07-14

## 1. 最终状态

RenTA 已完成 ACPs v2.1 协议升级、原功能兼容、公网独立部署和浏览器适配。当前正式入口为：

```text
http://120.27.205.185/
```

兼容入口继续保留：

```text
http://120.27.205.185:8888/
```

当前运行结论：

| 项目 | 状态 |
|---|---|
| ACPs v2.1 主链路 | 已正式启用 |
| ACPs 02.00 和旧 API | 继续保留 |
| Registry、CA、Discovery、编排、MQ | 全部在云主机本地运行 |
| PostgreSQL、Redis、RabbitMQ | 全部在云主机本地运行 |
| 对 `10.126.126.8` 的运行依赖 | 无 |
| 公网首页 | 80 端口直接提供，8888 兼容 |
| PC 与移动端 | 已完成真实浏览器验收 |
| 实际外部 Agent 调用 | 当前无稳定可用 Agent，不作为协议升级阻塞项 |

## 2. 升级模块总览

| 编号 | 模块 | 升级前 | 升级后 |
|---:|---|---|---|
| 1 | AIC 标识 | 只支持 v02.00 布局 | v02.00/v02.01 双轨生成、校验和识别 |
| 2 | ACS 描述 | 只支持旧 Schema 和 HTTP 类端点 | 支持 ACS 02.01、certificate、HTTP_JSON、AMQP 和 `{AIC}` |
| 3 | Registry Agent 生命周期 | 旧协议注册、审批和 Supervisor 校验 | 按协议版本审批、生成 AIC、保留 Passport/Supervisor/积分/事件 |
| 4 | Registry EAB | 不支持 | 支持所有者签发、SM4 密文存储、过期和一次性消费 |
| 5 | CA/ACME | 只走 HTTP-01 Challenge | 新账户走 EAB，旧账户继续走 Challenge |
| 6 | 证书身份约束 | 旧 CN/SAN 逻辑 | AIC 绑定 account/order/CSR，支持 `acps://AIC` URI SAN |
| 7 | 前端申请流程 | 只生成 02.00 ACS | 默认 02.01，可切回 02.00，支持证书、MQ 和 EAB |
| 8 | 统一网关 | Registry 与旧 API 代理 | 增加 CA、EAB、Discovery、Mode Router、Direct RPC 分流和 URL 重写 |
| 9 | Discovery | 旧响应和 Registry-first | 支持 v2.1 ADP 契约、ACS 保真同步和 Registry fallback |
| 10 | Mode Router | HTTP/RPC 与旧群组通信 | Discovery-first、transport 感知、MQ Inbox 和 legacy fallback |
| 11 | MQ Inbox/mTLS | RabbitMQ 5672 用户名密码 | 新增 5671、TLS 1.3、EXTERNAL、vhost `acps` 和 Inbox |
| 12 | MQ 动态授权 | 静态 RabbitMQ 权限 | mq-auth-server + Redis 动态 Group ACL |
| 13 | SDK | 原 RenTA SDK | 保留旧 SDK，新增隔离命名空间 `aic_v21`/`aip_v21` |
| 14 | 数据迁移 | 无 EAB 表，CA account 无 AIC | 新增 EAB 表和 account AIC，迁移可升降级 |
| 15 | 公网部署 | 依赖源服务器目录和启动脚本 | `/opt/renta` 独立部署、systemd 管理、Nginx 80 入口 |
| 16 | 前端体验 | PC 优先，移动端有溢出和遮挡 | PC 保持原布局，移动端重排、折叠、抽屉和触控适配 |
| 17 | 测试与回退 | 分散手工检查 | 分阶段门禁、全量回归、真实 E2E 和模块级开关回退 |

## 3. 协议模块详细变化

### 3.1 AIC v02.00/v02.01 双轨

升级前：

- 只生成和校验 v02.00 AIC。
- AIC 各段位置按旧布局固定解释。
- 历史查询和派生实体前缀只适配旧布局。

升级后：

- 支持 v02.00 和 v02.01 两种分段布局。
- 增加 `get_aic_spec_version()` 判断版本。
- 生成、CRC 校验、本体/实体转换和查询前缀按版本选择。
- 模糊布局优先按 legacy 解释，避免历史 AIC 失效。

兼容保护：历史 AIC 不重算，`ACPS_AIC_DUAL_READ_ENABLED=true` 持续双读。

### 3.2 ACS 02.01 Schema 与端点模型

升级前：

- 只使用旧 `acsSchema.json`。
- `x-caChallengeBaseUrl` 必填。
- 端点主要为 JSONRPC、HTTP、SSE、WebSocket。
- 不支持证书申请参数和 AMQP endpoint。

升级后：

- 引入官方 ACS 02.01 Schema，并保留旧 Schema。
- 02.01 支持 `certificate.altNames` 和 `requestedValidity`。
- 支持 `HTTP_JSON`、`AMQP`、`amqp://` 和 `amqps://`。
- 支持 `inbox_{AIC}` 及 `{AIC}` 占位符在审批后替换。
- 02.01 不再要求旧 Challenge URL。
- Supervisor 不会把 AMQP 地址错误当作 HTTP 健康检查目标。

兼容保护：02.00 继续执行原 Challenge、transport 和 Supervisor 规则。

### 3.3 Registry 注册、审批与平台业务

升级前：Registry 只按旧协议创建 Agent 和 AIC。

升级后：

- 创建、更新和审批根据 `protocolVersion` 分流。
- 02.01 Agent 审批时生成 v02.01 AIC，并替换 ACS 占位符。
- 读取已存 02.01 ACS 不受新写入开关影响。
- Registry DSP 可以同步完整 02.01 ACS。

保持不变的 RenTA 自有能力：

- 用户、角色和登录认证。
- Agent 草稿、提交、审批、上下架。
- Passport、Supervisor 和运行期复核。
- 积分钱包、积分流水和计费。
- 事件中心、变更日志、评论和评分。
- 原 `/api` 和历史 ATR/DSP 接口。

### 3.4 Registry EAB 签发与消费

升级前：Registry 没有 External Account Binding。

升级后：

- 新增 `POST /acps-atr-v2/eab/{agent_aic}`。
- 新增内部 `POST /internal/eab/consume`。
- 只允许 Agent 所有者为已审批、active 的 02.01 Agent 签发。
- `macKey` 使用 SM4-CBC 加密落库，明文只在签发和成功消费时返回。
- PostgreSQL `SELECT ... FOR UPDATE` 保证并发下只能消费一次。
- 支持过期、重放、非所有者、错误状态和旧协议拒绝。

数据库新增 `eab_credential`，未修改积分、事件、Passport 或 Supervisor 表。

### 3.5 CA EAB 与 ACME 双轨发证

升级前：所有 ACME account 依赖 HTTP-01 Challenge。

升级后：

- `new-account` 校验 EAB JWS 的 `alg=HS256`、URL、`kid`、JWK 和 HMAC。
- CA 从 Registry 一次性消费 EAB，并把 AIC 写入 ACME account。
- EAB account 只能为相同 AIC 创建 order。
- EAB Authorization 直接为 `valid`，Order 直接为 `ready`，不创建 HTTP-01 Challenge。
- `finalize` 再次核对 account AIC、order identifier、Registry ACS 和 CSR。
- 02.01 证书使用 `CN={AIC}` 和 `URI:acps://{AIC}`，并加入 ACS 指定的 DNS/IP SAN。
- 证书有效期受 ACS 请求和 CA 上限共同约束。

兼容保护：

- `acme_accounts.aic` 为 nullable，旧 account 保持 `NULL`。
- 旧 account、旧 order、旧证书、CRL、OCSP 和证书管理逻辑不变。
- Challenge Server 继续运行，只服务 legacy account。

### 3.6 Discovery v2.1

升级前：Mode Router 以 Registry Passport discovery 为主要候选来源。

升级后：

- 支持 `/acps-adp-v2/discover`。
- Discovery 保真返回 `agents`、`acsMap`、`routes`、`agentGroups` 和 `forwardChain`。
- Registry DSP snapshot/change/webhook 同步时保留 protocol、certificate 和全部 endpoint。
- Discovery 异常、超时或空结果时回退 Registry Passport discovery。
- HTTP 执行器只选择 HTTP(S) endpoint，不误用 AMQP URL。

### 3.7 Mode Router 与编排

升级前：主要使用旧 Registry 候选、Direct RPC、HTTP 和旧群组调用。

升级后：

- 支持 Discovery-first 候选选择。
- 请求级可覆盖候选来源，便于故障隔离。
- 保留完整 ACS 和 transport 元数据。
- 新增 `mq_inbox` 执行 transport。
- MQ 建链、认证或 endpoint 失败时可回退 Direct RPC/HTTP。
- 保留原有模式分类、计划生成、串并行依赖、回调、积分和运行期复核。

### 3.8 MQ Inbox、mTLS 与动态 ACL

升级前：

- RabbitMQ 5672、vhost `/`、用户名密码认证。
- 群组邀请依赖旧 RPC 或静态权限。

升级后：

- 新增 RabbitMQ 5671、TLS 1.3 和 vhost `acps`。
- 使用客户端证书和 SASL `EXTERNAL` 完成 Agent 身份认证。
- 从 ACS AMQP endpoint 建立 `inbox_{AIC}` 消费。
- 新增 mq-auth-server 的 Group API 和 RabbitMQ Auth API。
- Redis 保存动态 Group ACL，任务完成后清理临时授权。
- RabbitMQ management、Redis、mq-auth API 仅供云主机内部访问。

兼容保护：5672、vhost `/`、旧 SDK、旧 group bridge/proxy、Direct RPC 和 HTTP 均未删除。

### 3.9 隔离版 v2.1 SDK

升级前：原 Agent 和群组功能导入 `acps_sdk.aip`。

升级后：

```text
acps_sdk.aic_v21
acps_sdk.aip_v21
```

采用隔离命名空间，没有覆盖旧 SDK，避免旧 AIC、5672 和 RPC 客户端行为改变。

## 4. 前端与网关完善

### 4.1 Agent 申请页

- 默认选择 ACPs 02.01，同时保留“兼容 02.00”切换。
- 02.01 可配置 HTTP_JSON、AMQP、消息队列版本、DNS/IP SAN 和证书有效期。
- 提供 EAB 获取和 CA Directory 入口。
- EAB `macKey` 不写入 localStorage、sessionStorage、URL 或日志，5 分钟后自动清除。
- 02.00 Challenge URL 按 `window.location.origin` 生成，不再硬编码服务器 IP。

### 4.2 统一网关

| 外部路径 | 内部服务 |
|---|---|
| `/api/*`、ATR、DSP、EAB | Registry `127.0.0.1:8001` |
| ACME、CA、CRL、OCSP | CA `127.0.0.1:8003` |
| ADP | Discovery `127.0.0.1:8005` |
| `/mode-router/*` | Mode Router `127.0.0.1:18080` |
| `/agent-rpc/*` | Direct RPC `127.0.0.1:19090` |

网关会保留 ACME Host、Replay-Nonce 和 Location，并把 CA 内部 URL 改写为当前公网 origin。

### 4.3 PC 与移动端

- PC 继续保持四屏首页和原工作流。
- 移动端改为正常纵向滚动，无横向溢出。
- 首页流程默认显示 3 步，可展开到 5 步。
- 精选 Agent 默认显示 3 个，可展开到 6 个。
- 广场分类支持“更多分类”展开，排序按钮为 44px 触控目标。
- 聊天历史改为全屏抽屉，不再挤压聊天区域。
- Agent 申请页操作区改为文档流布局，不遮挡表单。
- Chat、Agent Detail、Challenge 和编排请求均使用当前 origin，不依赖旧服务器地址。

## 5. 数据库变化

| 数据库 | 变化 | 兼容方式 |
|---|---|---|
| Registry PostgreSQL | 新增 `eab_credential` 表和索引 | 纯新增，不改原业务表 |
| CA SQLite | `acme_accounts` 新增 nullable `aic` 和索引 | 历史 account 保持 NULL |
| Discovery PostgreSQL | 保留现有表，通过同步保存 02.01 ACS | 无破坏性迁移 |
| Redis | 新增运行期 Group ACL | 临时 key 在 E2E 后清理 |
| RabbitMQ | 新增 vhost `acps`、5671 和权限定义 | 原 vhost `/`、5672 保留 |

Registry 和 CA migration 均在生产数据副本完成 upgrade、downgrade 和 re-upgrade 验证。

## 6. 当前关键开关及含义

| 变量 | 当前值 | 含义 |
|---|---|---|
| `ACPS_V21_ENABLED` | `true` | Registry 启用 02.01 写入和校验 |
| `ACPS_LEGACY_API_ENABLED` | `true` | 保留旧 API |
| `ACPS_AIC_DUAL_READ_ENABLED` | `true` | 同时读取 v02.00/v02.01 AIC |
| `ACPS_EAB_ISSUANCE_ENABLED` | `true` | Registry 提供 EAB 签发与消费 |
| `ACPS_CA_EAB_ENABLED` | `true` | CA 为新 account 启用 EAB |
| `ACPS_CHALLENGE_LEGACY_ENABLED` | `true` | 旧 account 保留 HTTP-01 |
| `ACPS_FRONTEND_V21_ENABLED` | `true` | 前端默认 02.01 |
| `ACPS_FRONTEND_EAB_ENABLED` | `true` | 前端显示 EAB 工具 |
| `ACPS_DISCOVERY_V21_ENABLED` | `true` | Mode Router 优先 Discovery |
| `ACPS_DISCOVERY_LEGACY_FALLBACK_ENABLED` | `true` | Discovery 故障时回退 Registry |
| `ACPS_MQ_AUTH_ENABLED` | `true` | 启用 MQ 身份和 ACL 服务 |
| `ACPS_MQ_INBOX_ENABLED` | `true` | 启用 v2.1 MQ Inbox |
| `ACPS_MQ_LEGACY_FALLBACK_ENABLED` | `true` | MQ 故障时回退旧执行路径 |

这些开关当前不是灰度状态。新版主链路已经正式启用；开关保留用于模块级故障回退。

## 7. 公网独立部署完善

升级前主要运行目录为 `/home/johnteller/team_ws`，访问入口为源服务器 `:8888`。

公网部署后：

- 项目根目录为 `/opt/renta`。
- Registry、CA、Challenge、Discovery、Mode Router、Direct RPC、MQ Auth、Group Bridge/Proxy 和网关均由 systemd 管理。
- PostgreSQL、Redis、RabbitMQ、数据库文件、CA 证书和 MQ 证书均位于云主机。
- 业务后端只监听 loopback；公网只开放 HTTP 80、兼容网关 8888 和按需 MQ 端口。
- Nginx 80 端口透明代理到 `127.0.0.1:8888`，支持 API、长连接和流式响应。
- `renta.target` 纳入 Nginx 和 10 个 RenTA 服务，可开机自启。
- 活动配置、挂载和网络连接均不包含 `10.126.126.8`。

独立性验证方法：临时拒绝云主机所有发往 `10.126.126.8` 的流量，重启 10 个 RenTA 服务，等待全部端口就绪后执行冒烟。结果为 `18/18`，且无旧服务器连接。

## 8. 最终测试结果

2026-07-14 云端最终回归：

| 测试范围 | 结果 |
|---|---|
| 旧服务器隔离后 HTTP smoke | `18/18` |
| Registry | `133 passed, 6 deselected` |
| CA | `131 passed` |
| Challenge | `4 passed` |
| Discovery | `4 passed` |
| Gateway | `12 passed, 7 subtests passed` |
| Mode Router | `48 + 1 + 17 passed` |
| MQ Auth | `202 passed, 16 skipped` |
| ACPs v2.1 SDK | `27 passed` |
| MQ Inbox/mTLS E2E | 通过，`execution_transport=mq_inbox` |
| 前端 02.00/02.01 payload | 通过 |
| PC 1440x900 | 无横向溢出，控制台 0 错误 |
| iPhone 15 | 无横向溢出，控制台 0 错误 |

云端日志和校验和：

```text
/opt/renta/backups/cloud_full_acceptance_20260714_082507
```

## 9. 原功能保护清单

以下能力在升级后继续可用：

1. 用户注册、登录、角色和权限。
2. Agent 创建、提交、审批、上下架和广场展示。
3. Passport、Supervisor、健康探测和运行期复核。
4. 积分钱包、积分流水、计费、评论和评分。
5. 事件中心、SSE、变更日志和 webhook。
6. 原 `/api`、ATR、DSP 和 02.00 ACS。
7. 旧 ACME account、证书、CRL、OCSP 和 HTTP-01 Challenge。
8. RabbitMQ 5672、旧 SDK 和旧群组通信。
9. Direct RPC、HTTP、group bridge 和 group proxy。
10. 原 PC 页面、账户、管理、审批、监控和聊天入口。

## 10. 当前边界

平台核心服务已经完全迁移并独立运行。Registry 中部分历史 Agent 的业务 endpoint 属于外部 Agent 服务，不属于 RenTA 核心服务；当前没有稳定可用的实际 Agent 时，真实业务内容返回不作为协议升级验收条件。平台入口、注册、发现、编排、回退、发证和 MQ 协议链路已经完成验证。
