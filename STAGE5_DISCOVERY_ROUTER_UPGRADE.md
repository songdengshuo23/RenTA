# RenTA ACPs v2.1 阶段 5：Discovery 与 Mode Router 兼容升级记录

## 1. 实施结论

阶段 5 已于 2026-07-10 在远端主线完成，分支为 `upgrade/acps-v2.1-discovery-router`，核心代码提交为 `230ccc4d713f8cdce2408802bdf2d87784bb8407`。

本阶段没有替换 RenTA 现有 Discovery，而是在活动的 `yhl/ACPs-Discovery-Server` 和 `th/mode_router` 上增量适配 ACPs v2.1：

- Discovery 保真返回 `agents`/`acsMap`/`routes`/`agentGroups`/`forwardChain`。
- Registry DSP 同步后保留 ACS 的全部 endpoint、`protocolVersion`、certificate 和默认输入输出模式。
- Mode Router 可按开关使用 Discovery 作为候选来源，Discovery 失败或无结果时回退 Registry Passport discovery。
- 当前 HTTP 执行器只选择 `JSONRPC`/`HTTP_JSON`/`HTTP` 的 HTTP(S) endpoint，不会将 AMQP URL 误交给 HTTP 执行器。
- AMQP endpoint 仅在候选元数据中保留，真正的 MQ Inbox/mTLS 执行留到阶段 6。

生产环境保持 Discovery 主链路关闭，现有 Registry-first 路由、Direct RPC、HTTP 调度、回调、积分和运行期复核均未切换。

## 2. 改动范围

| 路径 | 改动 |
|---|---|
| `th/mode_router/adapters.py` | 兼容多层 Discovery response，支持 route-only `agentGroups`，保留 v2.1 协议、路由和传输元数据 |
| `th/mode_router/service.py` | 增加 Discovery-first 开关、Registry 回退开关、异常/空结果回退以及 HTTP endpoint 安全选择 |
| `th/mode_router/tests/` | 增加 v2.1 route-only、开关、回退和 AMQP 隔离测试 |
| `yhl/ACPs-Discovery-Server/app/discovery/service.py` | Registry fallback ACS 保留全部 endpoint、certificate 和 v2.1 字段 |
| `yhl/ACPs-Discovery-Server/tests/test_discovery_workability.py` | 增加 v2.1 ACS 保真测试 |
| `yhl/ACPs-Discovery-Server/start.sh` | 优先使用项目 `venv`，支持显式 Python 覆盖 |
| `yhl/ACPs-Discovery-Server/main.py` | 启动日志不再输出完整数据库连接串 |
| `wyl/start_stack.sh` | 增加默认关闭的 Discovery 启动项，向 Mode Router 写入双轨开关 |

没有修改 Registry 数据模型、CA、Challenge、前端、网关、Passport、Supervisor、points/events 和 Partner Agent 执行逻辑。

## 3. 兼容策略与开关

```text
ACPS_DISCOVERY_V21_ENABLED=false
ACPS_DISCOVERY_LEGACY_FALLBACK_ENABLED=true
ORCHESTRATOR_DISCOVERY_URL=http://127.0.0.1:8005/acps-adp-v2/discover
```

| 状态 | 行为 |
|---|---|
| v2.1 开关关闭 | Mode Router 继续 Registry-first；Discovery `8005` 不由统一脚本启动 |
| v2.1 开关开启 | Mode Router 先请求 `/acps-adp-v2/discover` |
| Discovery 超时、HTTP 错误或返回错误对象 | 转 Registry Passport discovery |
| Discovery 返回空候选 | 转 Registry Passport discovery |
| ACS 同时有 AMQP 和 HTTP endpoint | 保留 AMQP 元数据，当前执行优先 `JSONRPC` > `HTTP_JSON` > `HTTP` |
| ACS 只有 AMQP endpoint | 不把 AMQP URL 传给 HTTP 执行器；等待阶段 6 MQ Inbox |

请求级 `candidate_source`、`prefer_discovery` 可以显式覆盖环境默认值，便于隔离灰度和回滚。

## 4. 数据与备份

本阶段无 schema migration，未写入生产 Registry 数据。Discovery 数库实施前基线为：

```text
agents=35
protocol 02.00=35
protocol 02.01=0
alembic_version=d5215c4a631e
```

备份位于：

```text
/home/johnteller/team_ws/_archive/stage5_discovery_20260710_195432
```

目录内包含 PostgreSQL custom dump、基线计数和 SHA-256 校验文件。

## 5. 验证证据

### 5.1 自动化测试

| 门禁 | 结果 |
|---|---|
| Mode Router adapter 专项 | `5 passed` |
| Mode Router 阶段 5 service 专项 | `4 passed` |
| Discovery 专项 | `4 passed` |
| Registry 全量 | `133 passed, 6 deselected` |
| CA 全量 | `131 passed` |
| Challenge 全量 | `4 passed` |
| Mode Router tests | `44 passed, 3 deselected` |
| Mode Router sequential | `1 passed` |
| Mode Router root | `15 passed, 1 deselected` |
| HTTP 基线 | `18/18` |

阶段 0 总门禁退出码为 `0`，证据目录为：

```text
/home/johnteller/team_ws/_archive/stage0_regression_20260710_200259
```

### 5.2 真实链路

在临时 Discovery `18005` 和 Mode Router 隔离调用中：

- Discovery 从真实 Registry `/acps-dsp-v2` 同步到 sequence `56`。
- 真实 `/acps-adp-v2/discover` 返回 `agents`/`acsMap`/`routes`，包含 10 个 ACS 和 `forwardChain`。
- Mode Router Discovery-first 获得 5 个候选，来源标记为 `discovery`。
- 将 Discovery 指向故障端口后，自动转为 `registry_fallback_after_discovery_error`，仍获得 5 个候选。
- 隔离实例已按 PID 和工作目录校验后停止，临时端口不再监听。

## 6. 生产部署状态

- Mode Router 已使用阶段 5 兼容代码重启。
- `ACPS_DISCOVERY_V21_ENABLED=false`。
- `ACPS_DISCOVERY_LEGACY_FALLBACK_ENABLED=true`。
- Discovery `8005` 保持关闭。
- Registry `8001`、CA `8003`、Challenge `8004`、Mode Router `18080`、Direct RPC `19090` 和网关 `8888` 正常。
- 部署后 HTTP 基线 `18/18`。

因为主开关为 `false`，当前生产请求仍按阶段 4 及之前的 Registry-first 逻辑执行。

## 7. 回滚

1. 无需数据库回滚，本阶段没有 migration。
2. 运行时快速回退：保持 `ACPS_DISCOVERY_V21_ENABLED=false` 并重启 Mode Router。
3. 代码回滚：回退提交 `230ccc4`，再重启 Mode Router。
4. Discovery 即使已启动也可单独停止；Registry Passport discovery 和 Direct RPC/HTTP 仍保留。

## 8. 阶段 6 入口

下一阶段是 MQ Inbox / mTLS，建议从分支 `upgrade/acps-v2.1-mq-inbox` 开始，严格保持新旧 RabbitMQ 双轨：

1. 盘点当前 RabbitMQ `5672` 用户名/密码、group bridge、Direct RPC 和 Partner Agent 调用链。
2. 旁路部署新版 `mq-auth-server`、RabbitMQ `5671` TLS 和 vhost `acps`，不覆盖 `5672` 实例。
3. 使用 ACPs CA 签发的证书验证 mTLS `EXTERNAL` 认证和 ACL。
4. 在 Mode Router/group executor 增加默认关闭的 `mq_inbox` 执行分支，读取 ACS AMQP endpoint 和 `inbox_{AIC}`。
5. MQ 超时、认证失败或 endpoint 不完整时，自动回退现有 Direct RPC/HTTP。
6. 完成隔离端到端、旧 RabbitMQ 回归和总门禁后，生产仍默认关闭，再按 Agent 灰度。

阶段 6 不删除 Challenge、现有 group bridge/proxy、Direct RPC 或 RabbitMQ `5672`。
