# RenTA 云迁移与升级验收报告

**验收日期：** 2026-07-13  
**源代码修订：** `a18d721a68ad8138e89aa10e4571fcb2171f5e7c` (`upgrade/acps-v2.1-mq-inbox`)  
**源服务器：** `10.126.126.8`  
**目标服务器：** `120.27.205.185`（阿里云，Alibaba Cloud Linux 3）  
**运行目录：** `/opt/renta`

## 1. 结论

RenTA 已从源服务器完整迁入目标云主机，ACPs v2.1 已保持启用，同时保留旧 API、HTTP-01 与旧消息通道的兼容回退。数据库、CA SQLite 数据、私有 CA 证书、RabbitMQ 定义和消息证书均已迁入；服务由 `systemd` 管理并设置为开机自启。

平台内部、网关、PC 浏览器隧道、协议同步和 RabbitMQ mTLS 均已通过验收。主机防火墙已放行公网入口，但阿里云安全组尚未放行，因此外部设备暂时不能直接访问公网 IP；需在控制台添加本报告第 8 节的三条入站规则。

## 2. 目标部署结构

```text
/opt/renta/
  sds/                         Registry、CA、Challenge、MQ Auth
  th/mode_router/              编排、群组桥接与代理
  yhl/ACPs-Discovery-Server/   Discovery 与 DRC 同步
  yhl/direct_rpc_server.py     直连对话/多角色 RPC
  wyl/frontend/                Web 前端
  wyl/server/server.py         前端与统一 API 网关
  ACPs_update_code/ACPs-SDK/   ACPs v2.1 SDK
  runtime/                     私有运行配置（权限 0600）
  venv/                        各服务独立 Python 3.13 环境
  backups/                     数据库恢复与回归测试产物
```

基础组件：PostgreSQL 13、Redis 6、RabbitMQ 3.12.14、Erlang 26、Python 3.13.11。

## 3. 数据与证书迁移

| 项目 | 验收结果 |
| --- | --- |
| `registry_db` | 已恢复；17 用户、26 智能体、24 Passport、26 审核记录、0 条 EAB 凭据 |
| `discovery_db` | 已恢复；Discovery/DRC 表可由 `admin` 账户读写 |
| CA SQLite | `sds/ca-server/agent_ca.db` 已迁入 |
| CA 证书 | `ca.crt`、`ca.key` 与服务端证书已迁入 |
| RabbitMQ | `/`、`acps` vhost、用户、交换机与权限定义已导入 |
| MQ mTLS | Root CA、Broker、Leader、Partner 客户端证书已迁入 |

导入后已将 PostgreSQL `public` 模式内的业务对象恢复给 `sds` 或 `admin`，以避免应用账户无权读取导入表。PostgreSQL 的 MD5 口令认证只允许 `127.0.0.1` 和 `::1`，数据库端口不对公网开放。

## 4. 服务与端口

| 服务 | systemd 单元 | 监听位置 | 作用 |
| --- | --- | --- | --- |
| Registry | `renta-registry.service` | `127.0.0.1:8001` | ATR、DSP、账户、智能体、Passport、事件、EAB |
| CA | `renta-ca.service` | `127.0.0.1:8003` | ACME、证书、CRL、OCSP |
| Challenge | `renta-challenge.service` | `127.0.0.1:8004` | 旧 HTTP-01 Challenge 兼容服务 |
| Discovery | `renta-discovery.service` | `127.0.0.1:8005` | ADP v2.1、DRC 同步与发现 |
| MQ Auth | `renta-mq-auth.service` | `127.0.0.1:9007/9008` | 群组 ACL、RabbitMQ HTTP 鉴权 |
| Group Bridge/Proxy | `renta-group-bridge.service`、`renta-group-proxy.service` | `127.0.0.1:8098/8099` | 编排群组通信兼容层 |
| Mode Router | `renta-mode-router.service` | `127.0.0.1:18080` | 编排模式选择与计划生成 |
| Direct RPC | `renta-direct-rpc.service` | `127.0.0.1:19090` | 对话与多角色直连入口 |
| Web Gateway | `renta-frontend.service` | `0.0.0.0:8888` | PC 前端和所有 HTTP API 统一入口 |
| RabbitMQ TLS | `rabbitmq-server.service` | `0.0.0.0:5671` | ACPs v2.1 EXTERNAL/mTLS 消息通道 |
| RabbitMQ Legacy | `rabbitmq-server.service` | `0.0.0.0:5672` | 旧 AMQP 兼容通道 |

RabbitMQ 管理端口 `15672` 仅监听本机；Redis、PostgreSQL、所有业务后端同样不对公网开放。

## 5. ACPs v2.1 变量说明

这些变量均由 `/opt/renta/runtime/*/.env` 和对应 systemd 服务加载。报告不记录密钥或令牌实际值。

| 变量 | 当前策略 | 含义 |
| --- | --- | --- |
| `ACPS_V21_ENABLED` | `true` | 启用 Registry 的 ACPs v2.1 路由与数据模型行为。 |
| `ACPS_LEGACY_API_ENABLED` | `true` | 保留旧 Registry API，已有客户端无需立刻迁移。 |
| `ACPS_AIC_DUAL_READ_ENABLED` | `true` | AIC 读取同时兼容旧字段和 v2.1 字段。 |
| `ACPS_EAB_ISSUANCE_ENABLED` | `true` | Registry 可签发一次性 EAB 凭据。 |
| `ACPS_CA_EAB_ENABLED` | `true` | CA 的 v2.1 `new-account` 校验 EAB，并把 AIC 绑定到账户。 |
| `ACPS_CHALLENGE_LEGACY_ENABLED` | `true` | 旧 ACME 账户继续走 HTTP-01，不删除 Challenge Server。 |
| `ACPS_DISCOVERY_V21_ENABLED` | `true` | 启用 ADP v2.1 Discovery 路径。 |
| `ACPS_DISCOVERY_LEGACY_FALLBACK_ENABLED` | `true` | Discovery 失败时仍可回退旧发现路径。 |
| `ACPS_MQ_INBOX_ENABLED` | `true` | 启用 v2.1 RabbitMQ Inbox/Group 通道。 |
| `ACPS_MQ_LEGACY_FALLBACK_ENABLED` | `true` | v2.1 MQ 不可用时保留旧 AMQP 流程。 |
| `ACPS_MQ_TLS_CERT_FILE` / `ACPS_MQ_TLS_KEY_FILE` / `ACPS_MQ_TLS_CA_FILE` | 已配置 | Leader/Partner 连接 `5671` 时使用的 mTLS 客户端证书、私钥与 CA。 |
| `ACPS_MQ_AUTH_URL` | 已配置 | 群组 ACL API；必须为 HTTPS 并仅由本机访问。 |
| `ACPS_FRONTEND_V21_ENABLED` | `true` | 前端加载 v2.1 协议能力与统一 CA Directory。 |
| `ACPS_FRONTEND_EAB_ENABLED` | `true` | 前端显示 EAB 发放能力。 |
| `DATABASE_URL` | 私有配置 | Registry/Discovery 的数据库连接；仅本机 PostgreSQL 可达。 |
| `CA_INTERNAL_SERVICE_TOKEN`、`REGISTRY_SERVICE_TOKEN`、`DSP_SERVICE_TOKEN` | 私有配置 | 服务间鉴权令牌，不能写入浏览器或文档。 |

`true` 与兼容开关并存是本次升级的关键：新协议可以工作，但旧用户、旧证书和旧调用路径不会被强制切断。

## 6. 验收结果

| 范围 | 结果 |
| --- | --- |
| 平台原功能冒烟 | 18/18 通过（前端、Registry、CA、Challenge、Group Bridge/Proxy、Mode Router、Direct RPC） |
| Registry 回归 | 133 通过，6 项原有依赖真实外部端点的测试按既定门禁排除 |
| CA 回归 | 131 通过（临时 SQLite schema） |
| Challenge 回归 | 4 通过 |
| MQ Auth 回归 | 202 通过；16 项需单独 E2E 环境变量的测试跳过 |
| Mode Router 回归 | 66 通过，4 项按既定门禁排除 |
| DRC 同步 | Registry Snapshot 带服务令牌返回 200，Discovery 可正常拉取数据 |
| RabbitMQ v2.1 | TLS 1.3 + EXTERNAL mTLS 已建立连接并成功创建 AMQP Channel |
| PC 页面 | 首页、智能体广场、登录页通过本机真实浏览器访问；广场显示迁入的 12 个上架智能体 |
| 网关代理 | PC 隧道下的智能体列表、ACME Directory、Discovery `stats/discover`、Mode Router、Direct RPC 均返回 200 |
| 重启恢复 | 云主机重启后所有 10 个应用服务、PostgreSQL、Redis、RabbitMQ、firewalld 自动恢复；18/18 冒烟与 mTLS 再次通过 |

实际外部智能体调用未作为验收前置条件：源环境配置的外部智能体并不保证可用，按项目约定仅验证调用入口、健康检查、编排与回退路径。

## 7. 运维命令

```bash
# 查看整体状态
systemctl status renta.target
systemctl --failed

# 重启全部 RenTA 应用服务
systemctl restart renta.target

# 查看单个服务日志
journalctl -u renta-registry -f
journalctl -u renta-ca -f
journalctl -u renta-frontend -f

# 本机冒烟
cd /opt/renta
/opt/renta/venv/registry/bin/python -B scripts/stage0_smoke.py --host 127.0.0.1

# 防火墙确认
firewall-cmd --zone=public --list-all
```

回归日志与校验和保存在 `/opt/renta/backups/cloud_regression_*`。

## 8. 必须完成的阿里云安全组操作

主机 `firewalld` 已允许这些端口，但阿里云安全组目前只允许 SSH，导致 PC 直接访问 `http://120.27.205.185:8888` 超时。请在实例 `i-bp11rpqjbrickp0u9rt5Z` 所属安全组添加入方向规则：

| 协议 | 端口 | 建议来源 | 用途 |
| --- | --- | --- | --- |
| TCP | `8888` | 业务用户网段，演示期间可 `0.0.0.0/0` | RenTA PC 平台与统一 HTTP API |
| TCP | `5671` | 接入 ACPs v2.1 Partner 的网段 | RabbitMQ TLS 1.3 + EXTERNAL/mTLS |
| TCP | `5672` | 仅旧客户端网段 | 旧 AMQP 兼容；无旧客户端时可不放行 |

不要开放 `8001`、`8003`、`8004`、`8005`、`8098`、`8099`、`9007`、`9008`、`15672`、`5432` 或 `6379`。安全组放行后，外部入口为：`http://120.27.205.185:8888`。

## 9. 本次云端适配

1. 用独立 systemd 单元替代源服务器的硬编码启动脚本。
2. 将运行路径从 `/home/johnteller/team_ws` 改为 `/opt/renta`，私有环境变量集中到 `runtime/`。
3. 以源端 `aio-pika 9.6.2` 固定 MQ 客户端版本，避免 10.x 的兼容差异。
4. 启用 `rabbitmq_auth_mechanism_ssl`，使 Broker 对 mTLS 客户端通告并验证 EXTERNAL SASL。
5. 修复 MQ Auth 测试中两处不符合 Python 3 语法的多异常捕获，运行服务代码未改变。
