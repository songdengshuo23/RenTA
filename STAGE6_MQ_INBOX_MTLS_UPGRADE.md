# RenTA ACPs v2.1 阶段 6：MQ Inbox / mTLS 升级记录

## 1. 完成结论

阶段 6 已完成。RenTA 已在不覆盖旧 SDK、不删除旧 RabbitMQ 5672、不切换生产默认路由的前提下，接入 ACPs v2.1 MQ Inbox、mTLS EXTERNAL 认证和动态 group ACL。

- 远端分支：`upgrade/acps-v2.1-mq-inbox`
- 阶段 6 核心提交：`f08912f467fb9c7c8a258d9efddf7bfe37ddec33`
- PC 路由兼容修复：`f854f4a858cb2cca00c82bf1b3086435750a7c95`
- 远端主线：`/home/johnteller/team_ws`
- RabbitMQ/配置备份：`/home/johnteller/team_ws/_archive/stage6_mq_20260710_210017`

生产的 `ACPS_MQ_AUTH_ENABLED` 和 `ACPS_MQ_INBOX_ENABLED` 仍为 `false`。新版链路已真实验证，但不会自动接管旧 Agent。

## 2. 升级前后差异

| 项目 | 升级前 | 阶段 6 后 |
|---|---|---|
| SDK 导入 | `acps_sdk.aip` | 旧导入不变；新增 `acps_sdk.aip_v21` |
| AIC 校验 | RenTA 旧 validator | 旧 validator 不变；新增 `acps_sdk.aic_v21` |
| RabbitMQ | 5672、vhost `/`、用户名密码 | 保留旧链路；新增 5671、vhost `acps`、TLS 1.3、EXTERNAL |
| 群组邀请 | Partner RPC URL | 新分支可从 ACS AMQP endpoint 使用 Inbox 邀请 |
| ACL | 静态 RabbitMQ 权限 | mq-auth-server + Redis 动态 group ACL |
| Mode Router | 旧 RabbitMQ group chat / HTTP | 新增显式 `mq_inbox`，失败可回退 HTTP |
| travel bridge | 旧 RPC/group consumer | 旧 consumer 保留；开关开启时才启动 v2.1 Inbox consumer |
| 生产默认 | 旧链路 | 仍为旧链路 |

## 3. 代码改造

### 3.1 隔离版 v2.1 SDK

新增：

```text
ACPs_update_code/ACPs-SDK/acps_sdk/aic_v21/
ACPs_update_code/ACPs-SDK/acps_sdk/aip_v21/
ACPs_update_code/ACPs-SDK/tests_v21/
```

采用隔离命名空间的原因：

- RenTA 旧 Agent 和 group bridge 仍导入 `acps_sdk.aip`。
- 官方 v2.1 AIC 分段约束与旧 RenTA validator 不同。
- 直接覆盖会使旧 5672/RPC 行为和历史 AIC 失效。

官方源码仅做 Python 3.12 兼容和 LF 行尾规范化，没有把整个官方项目覆盖到 RenTA 活动目录。

### 3.2 mq-auth-server

新增：

```text
sds/mq-auth-server/
  app/
  config/
  deploy/
  scripts/provision-renta-certs.sh
  tests/
  .env.example
  start.sh
  RENTA_INTEGRATION.md
```

运行时 `.env`、证书、私钥、日志、PID、`.venv` 均由根 `.gitignore` 排除，没有提交到 Git。

### 3.3 Mode Router 与 bridge

主要文件：

| 文件 | 修改 |
|---|---|
| `th/mode_router/mq_v21_runtime.py` | 读取 MQ 开关、证书路径、5671/acps 约束并创建 TLS 1.3 client context |
| `generic_group_executor.py` | 按开关选择旧 SDK 或 v2.1 SDK；从 ACS 读取 AMQP endpoint；返回执行 transport |
| `service.py` | 保留完整 ACS；增加 `mq_inbox` transport 和失败回退 |
| `travel_group_bridge.py` | 仅在开关开启时启动 v2.1 Inbox consumers；旧 RPC route 不删除 |
| `wyl/start_stack.sh` | 写入阶段 6 开关和证书路径；mq-auth 仅在开关开启时启动 |
| `scripts/stage6_mq_e2e.py` | 真实 mTLS Inbox 端到端验证 |

## 4. 基础设施

RabbitMQ 3.12.1 采用增量配置：

- 旧 listener：`5672`，保留。
- 新 listener：`5671`，TLS 1.3。
- 新 vhost：`acps`。
- 启用 `rabbitmq_management`、`rabbitmq_auth_mechanism_ssl`、`rabbitmq_auth_backend_http`、`rabbitmq_auth_backend_cache`。
- RabbitMQ 配置：`/etc/rabbitmq/rabbitmq.conf`、`/etc/rabbitmq/advanced.config`。
- mq-auth Group API：`9007` mTLS。
- mq-auth Auth API：`9008` mTLS。
- Redis 7.0.15：只监听 `127.0.0.1:6379` 和 `::1:6379`。

RabbitMQ 3.12 不接受 `auth_http.ssl_options.*` 的现代配置键，因此 TLS HTTP backend 参数放入 `advanced.config`。第一次配置失败后已自动回滚并验证 5672 恢复，最终配置再增量启用 5671。

证书由现有 ACPs CA 签发，运行时文件未提交。私钥权限为 600。

## 5. 兼容开关

```text
ACPS_MQ_AUTH_ENABLED=false
ACPS_MQ_INBOX_ENABLED=false
ACPS_MQ_LEGACY_FALLBACK_ENABLED=true
ACPS_MQ_LEADER_AIC=1.2.156.3088.1.1.34C2.478BDF.3GF546.0JU4
ACPS_MQ_HOST=127.0.0.1
ACPS_MQ_PORT=5671
ACPS_MQ_VHOST=acps
ACPS_MQ_AUTH_URL=https://127.0.0.1:9007
ACPS_MQ_TLS_CHECK_HOSTNAME=false
ACPS_MQ_INVITATION_TIMEOUT_SECONDS=30
```

行为：

- `ACPS_MQ_INBOX_ENABLED=false`：旧 RabbitMQ group chat、Direct RPC 和 HTTP 行为不变。
- 显式选择 `mq_inbox`：使用 v2.1 SDK、5671、mTLS EXTERNAL 和 Inbox。
- MQ 失败且 fallback 开启：Mode Router 回退 HTTP multi-agent。
- bridge 不会把 AMQP URL 误交给 HTTP executor。

## 6. 验证结果

### 6.1 阶段 6 专项

| 验证 | 结果 |
|---|---|
| v2.1 SDK | `27 passed` |
| mq-auth unit | `185 passed`，1 个依赖弃用 warning |
| Mode Router 阶段 6 | 通过 |
| 真实 MQ Inbox E2E | Inbox 邀请、任务、结果和 ACL 清理通过 |
| 旧 5672 | 旧 SDK + group bridge 邀请通过 |
| 无 client certificate | mq-auth mTLS 请求被拒绝 |
| Redis ACL | E2E 后动态 key 清理为 0 |

真实 E2E 输出：

```text
invitation_route=inbox
task_result=mq inbox e2e ok
execution_transport=mq_inbox
```

Partner 退出时官方 SDK 会在 Leader 已删除 exchange 后再尝试发送 leave 状态，产生两条 `RobustChannel closed` 清理日志。E2E 返回码为 0、任务结果正确、ACL 已清理；这是上游关闭顺序日志，不影响功能。

### 6.2 最终总门禁

最终归档：

```text
/home/johnteller/team_ws/_archive/stage0_regression_20260711_091307
```

结果：HTTP 18/18、Registry 133、CA 131、Challenge 4、Mode Router 48+1+17、Discovery 4、Gateway 12、mq-auth 185、v2.1 SDK 27，前端 payload 和真实 MQ E2E 通过。

## 7. 当前部署状态

阶段 6 代码已由当前运行的 Mode Router 和 group bridge 加载，但新路由开关关闭：

```text
Mode Router 18080: ACPS_MQ_INBOX_ENABLED=false
group bridge 8098: mqInboxEnabled=false, mqInboxConsumers=0
RabbitMQ 5672: active
RabbitMQ 5671: active
mq-auth 9007/9008: active sidecar
Redis 6379: localhost only
```

sidecar 和 5671 listener 存在不会改变旧请求路由。

## 8. 回滚

应用级回滚优先：

```text
ACPS_MQ_AUTH_ENABLED=false
ACPS_MQ_INBOX_ENABLED=false
ACPS_MQ_LEGACY_FALLBACK_ENABLED=true
```

如需回滚基础设施：

1. 停止 mq-auth sidecar。
2. 用 `/home/johnteller/team_ws/_archive/stage6_mq_20260710_210017` 恢复 `/etc/rabbitmq` 配置和 definitions。
3. 重启 RabbitMQ，确认 5672、vhost `/` 和旧账户正常。
4. Redis 无其他 RenTA 依赖时可停止；不删除数据前先检查 key。

不要删除旧 SDK、5672、Challenge、Direct RPC、group bridge 或 group proxy。

## 9. 阶段 6 后续

研发阶段已结束，下一步是受控灰度：

1. 为测试 Leader/Partner 签发短期 clientAuth 证书。
2. 只为测试 Agent 发布 02.01 ACS AMQP endpoint。
3. 单独开启 EAB/CA，再开启 Discovery，最后开启 MQ Inbox。
4. 观察 mq-auth 403/5xx、RabbitMQ connection/channel、Redis ACL 和 Mode Router fallback 指标。
5. 指标稳定后再扩大到新 Agent；旧 Agent 长期保留 legacy 路径。
