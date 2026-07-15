# RenTA 云端后续开发对接文档

更新时间：2026-07-15  
当前生产运行代码基线：`8b0997a880b15ed789b36728ca8c79879e704708`

GitHub 开发基线：最新 `main`（在上述运行代码基线上仅追加了本对接文档）

## 0. 新会话可直接使用的任务说明

将下面内容连同本文件一起交给新会话：

```text
继续开发已迁移到公网云主机的 RenTA 平台。

先完整阅读 docs/NEXT_SESSION_CLOUD_DEVELOPMENT_HANDOFF.md、
ACPS_V21_PLATFORM_UPGRADE_MODULES.md 和
docs/CLOUD_MIGRATION_ACCEPTANCE_20260713.md，再开始操作。

当前正式生产地址是 http://120.27.205.185/，生产部署目录是
/opt/renta。云端实际运行代码基线是 8b0997a；开发时从 GitHub 最新
main 开始。云端部署目录没有
.git，禁止直接把云端当源码仓库，也不能重新依赖 10.126.126.8。

开始修改前先完成：
1. 核对 GitHub、本地代码和生产基线。
2. 核对 renta.target、10 个 RenTA 服务、Nginx、PostgreSQL、Redis、
   RabbitMQ 的状态。
3. 对本次需求涉及的文件、数据库和配置先做时间戳备份。
4. 从 main 创建独立功能分支，先测试再部署。
5. 部署后运行 18 项 smoke、相关模块测试和 PC 浏览器测试；涉及响应式
   页面时再补移动端测试。
6. 不覆盖 /opt/renta/runtime、/opt/renta/venv、数据库、证书和备份目录。
7. 保持 ACPs 02.00、旧 API、旧 ACME/Challenge、旧 RabbitMQ 5672 和
   原 RenTA 平台功能兼容，除非本次需求明确要求改变。

SSH 密码和 GitHub 凭据由用户在新会话单独提供，不得写入代码或 Git。
```

## 1. 当前结论

- RenTA 已完成 ACPs v2.1 升级并正式启用，不处于灰度状态。
- 原 ACPs 02.00、旧 API、旧 ACME/HTTP-01、旧 SDK 和 RabbitMQ 5672 仍保留。
- 平台已经完整迁移到 `120.27.205.185`，运行时不依赖旧服务器。
- 2026-07-15 复核时，10 个 RenTA 服务以及 Nginx、PostgreSQL、Redis、RabbitMQ 全部为 `active`。
- 云主机到 `10.126.126.8` 的活动连接为 `0`。
- 当前没有稳定可用的外部 Agent，实际外部 Agent 内容调用不作为现有基线的阻塞项；平台内部注册、发现、编排、发证和 MQ 链路已验收。

正式入口：

```text
http://120.27.205.185/
```

兼容入口：

```text
http://120.27.205.185:8888/
```

## 2. 主机、仓库与版本

### 2.1 生产云主机

```text
SSH: root@120.27.205.185:22
部署目录: /opt/renta
服务用户: renta:renta
操作系统: Alibaba Cloud Linux 3
```

认证密码由用户在新会话单独提供。不要把密码、PAT、API Key、数据库口令、服务 Token 或私钥写入本文件、代码、提交记录、命令历史或测试日志。

### 2.2 GitHub

```text
仓库: https://github.com/songdengshuo23/RenTA
生产运行代码基线: 8b0997a880b15ed789b36728ca8c79879e704708
main: 获取 origin/main 最新提交；当前只比生产运行代码多本对接文档
upgrade/acps-v2.1-mq-inbox: 8b0997a880b15ed789b36728ca8c79879e704708
fix/mobile-responsive-home: 8b0997a880b15ed789b36728ca8c79879e704708
```

可用下面的命令获取不可歧义的最新开发基线：

```bash
git ls-remote https://github.com/songdengshuo23/RenTA.git refs/heads/main
```

后续功能应从最新 `main` 创建独立分支。不要从 `8b0997a` 重新分叉而遗漏本对接文档，也不要继续把新功能堆叠到历史阶段分支。

### 2.3 当前本机工作区

```text
裸仓库: D:/B-EP1/_analysis/RenTA-publish.git
现有工作树: D:/B-EP1/_analysis/RenTA-mobile-ui
生产运行代码父提交: 8b0997a880b15ed789b36728ca8c79879e704708
```

现有工作树使用 sparse checkout，只展开了前端、部署和文档等部分。开发后端前先扩展路径：

```powershell
git -C D:/B-EP1/_analysis/RenTA-mobile-ui sparse-checkout add `
  ACPs_update_code renta_platform sds th yhl
```

更推荐为新需求建立新的完整 worktree：

```powershell
git --git-dir=D:/B-EP1/_analysis/RenTA-publish.git fetch origin
git --git-dir=D:/B-EP1/_analysis/RenTA-publish.git worktree add `
  D:/B-EP1/RenTA-dev -b feature/<功能名> main
```

如果直接从 GitHub clone，认证信息仍由用户临时提供，不得保存到 remote URL。

### 2.4 旧源服务器

```text
SSH: johnteller@10.126.126.8:2222
历史仓库: /home/johnteller/team_ws
当前历史分支: upgrade/acps-v2.1-mq-inbox
生产运行代码基线: 8b0997a880b15ed789b36728ca8c79879e704708
历史仓库 HEAD: 在运行代码基线上追加本对接文档
```

旧服务器只作为历史副本和核对来源，不是生产依赖，也不应重新进入任何运行配置、前端 URL、服务发现地址或数据库连接。

### 2.5 云端不是 Git 工作树

`/opt/renta` 当前没有 `.git`。因此：

- 不要在 `/opt/renta` 执行 `git pull`。
- 不要直接在生产目录长期开发。
- GitHub `main` 是代码基线；云端是部署产物加运行数据。
- 紧急热修如果必须在云端完成，修复后必须立即回填功能分支、测试、提交并重新规范部署。

## 3. 生产架构

```text
公网浏览器
  -> Nginx :80
  -> renta-frontend :8888
       -> Registry :8001
       -> CA :8003
       -> Discovery :8005
       -> Mode Router :18080
       -> Direct RPC :19090

Mode Router
  -> Group Bridge :8098
  -> Group Proxy :8099
  -> RabbitMQ :5671/5672
  -> MQ Auth :9007/9008

Registry -> PostgreSQL registry_db
Discovery -> PostgreSQL discovery_db
CA -> SQLite agent_ca.db
MQ Auth -> Redis
```

### 3.1 systemd 服务

| 服务 | 工作目录 | Python/启动方式 | 监听地址 |
|---|---|---|---|
| `renta-registry` | `/opt/renta/sds/registry-server` | `/opt/renta/venv/registry/bin/python main.py` | `127.0.0.1:8001` |
| `renta-ca` | `/opt/renta/sds/ca-server` | `/opt/renta/venv/ca/bin/python main.py` | `127.0.0.1:8003` |
| `renta-challenge` | `/opt/renta/sds/challenge-server` | `/opt/renta/venv/challenge/bin/python main.py` | `127.0.0.1:8004` |
| `renta-discovery` | `/opt/renta/yhl/ACPs-Discovery-Server` | `/opt/renta/venv/discovery/bin/python main.py` | `127.0.0.1:8005` |
| `renta-group-bridge` | `/opt/renta/th/mode_router` | mode-router venv + Uvicorn | `127.0.0.1:8098` |
| `renta-group-proxy` | `/opt/renta/th/mode_router` | mode-router venv + Uvicorn | `127.0.0.1:8099` |
| `renta-mq-auth` | `/opt/renta/sds/mq-auth-server` | `/opt/renta/venv/mq-auth/bin/python -m app.main` | `127.0.0.1:9007/9008` |
| `renta-mode-router` | `/opt/renta/th/mode_router` | mode-router venv + `service.py` | `127.0.0.1:18080` |
| `renta-direct-rpc` | `/opt/renta/yhl` | discovery venv + Uvicorn | `127.0.0.1:19090` |
| `renta-frontend` | `/opt/renta/wyl/server` | `/opt/python/3.13/bin/python3.13 server.py` | `0.0.0.0:8888` |

统一启动单元：

```bash
systemctl status renta.target --no-pager
systemctl start renta.target
```

`renta.target` 用于统一拉起服务；仅重启 target 本身不会可靠重启它已经运行的依赖。常规开发发布应只重启受影响服务。确需重启整套应用时，应显式重启 10 个 `renta-*.service` 并逐一等待端口恢复。

### 3.2 公网和内部端口

| 端口 | 用途 | 暴露范围 |
|---:|---|---|
| `80` | Nginx 正式首页和统一入口 | 公网 |
| `8888` | 兼容首页和 Python 网关 | 公网兼容 |
| `5671` | RabbitMQ ACPs v2.1 mTLS | 公网按需 |
| `5672` | RabbitMQ legacy | 公网按需兼容 |
| `8001/8003/8004/8005` | Registry/CA/Challenge/Discovery | loopback |
| `8098/8099` | Group Bridge/Proxy | loopback |
| `9007/9008` | MQ Auth | loopback |
| `18080/19090` | Mode Router/Direct RPC | loopback |
| `5432/6379` | PostgreSQL/Redis | loopback |

除非需求明确需要，不要把内部端口开放到公网。

### 3.3 网关路由

| 公网路径 | 内部服务 |
|---|---|
| `/api/*`、ATR、DSP、EAB | Registry `127.0.0.1:8001` |
| ACME、CA、CRL、OCSP | CA `127.0.0.1:8003` |
| `/acps-adp-v2/*` | Discovery `127.0.0.1:8005` |
| `/mode-router/*` | Mode Router `127.0.0.1:18080` |
| `/agent-rpc/*` | Direct RPC `127.0.0.1:19090` |

Nginx 配置：

```text
仓库: deployment/cloud/nginx/
生产: /etc/nginx/nginx.conf
生产: /etc/nginx/conf.d/renta.conf
```

## 4. 运行配置、数据与证书

### 4.1 不可覆盖的运行目录

```text
/opt/renta/runtime
/opt/renta/venv
/opt/renta/backups
/opt/renta/sds/ca-server/agent_ca.db
/etc/rabbitmq/stage6-certs
```

`/opt/renta/runtime` 权限为 `700`，保存生产 `.env` 和 RabbitMQ 配置。仓库里的 `deployment/cloud` 只保存非敏感模板，不能替代生产 runtime 文件。

环境文件：

```text
/opt/renta/runtime/registry/.env
/opt/renta/runtime/ca/.env
/opt/renta/runtime/challenge/.env
/opt/renta/runtime/discovery/.env
/opt/renta/runtime/mode-router/.env
/opt/renta/runtime/direct/.env
/opt/renta/runtime/mq-auth/.env
```

修改环境变量前应备份文件、记录变量名变化、执行最小服务重启。输出配置时只能输出变量名，不能把值写进日志或对接文档。

### 4.2 数据库

| 组件 | 数据位置 | 当前 migration |
|---|---|---|
| Registry | PostgreSQL `registry_db` | `f1a2b3c4d5e6` |
| Discovery | PostgreSQL `discovery_db` | `d5215c4a631e` |
| CA | `/opt/renta/sds/ca-server/agent_ca.db` | `d4e5f6a7b8c9` |
| MQ Auth | Redis `127.0.0.1:6379` | 运行期 ACL |

数据库迁移要求：

1. 先备份真实数据库。
2. 用备份副本完成 upgrade、downgrade、re-upgrade。
3. 新列默认 nullable 或具备兼容默认值。
4. 不破坏历史 AIC、ACS、Agent、Passport、证书、积分和事件数据。
5. 生产迁移后立即运行专项测试和 smoke。

### 4.3 RabbitMQ 与证书

- RabbitMQ vhost `/` 和 5672 是 legacy 兼容链路。
- vhost `acps` 和 5671 是 ACPs v2.1 mTLS/EXTERNAL 链路。
- 证书位于 `/etc/rabbitmq/stage6-certs`，私钥不进入 Git、不打入普通发布包。
- 当前启用了 management、HTTP auth backend、auth cache 和 SSL auth mechanism 插件。
- 修改 MQ 配置前同时备份 `/etc/rabbitmq` 和 `/opt/renta/runtime/rabbitmq`。

### 4.4 当前备份与验收证据

```text
/opt/renta/backups/cloud_full_acceptance_20260714_082507
/opt/renta/backups/public_release_20260714_091139
/opt/renta/backups/frontend_mobile_20260713_233959
/opt/renta/backups/nginx_before_public_20260714_081841
```

新的发布备份使用独立时间戳目录，不覆盖这些基线证据。

## 5. ACPs v2.1 与兼容开关

当前正式启用：

```text
ACPS_V21_ENABLED=true
ACPS_EAB_ISSUANCE_ENABLED=true
ACPS_CA_EAB_ENABLED=true
ACPS_FRONTEND_V21_ENABLED=true
ACPS_FRONTEND_EAB_ENABLED=true
ACPS_DISCOVERY_V21_ENABLED=true
ACPS_MQ_AUTH_ENABLED=true
ACPS_MQ_INBOX_ENABLED=true
```

当前兼容保护：

```text
ACPS_LEGACY_API_ENABLED=true
ACPS_AIC_DUAL_READ_ENABLED=true
ACPS_CHALLENGE_LEGACY_ENABLED=true
ACPS_DISCOVERY_LEGACY_FALLBACK_ENABLED=true
ACPS_MQ_LEGACY_FALLBACK_ENABLED=true
```

这些开关现在用于模块级故障回退，不表示平台仍在灰度。新功能不能通过删除兼容分支来实现。

CA 当前还保留 `AGENT_REGISTRY_MOCK=true` 和 `HTTP01_VALIDATION_MOCK=true` 的既有运行配置。它们关系到现有无外部 Agent 环境和 legacy Challenge 行为；除非需求明确要求切换并完成隔离验证，不要顺手修改。

## 6. 标准开发流程

### 6.1 开始前

1. 阅读本文件和升级验收文档。
2. 确认 GitHub `main`、本地分支和生产基线。
3. 从 `main` 创建功能分支。
4. 记录本次改动会影响的服务、端口、数据表、环境变量和页面。
5. 检查工作树，不能覆盖用户已有未提交修改。

建议分支名：

```text
feature/<功能名>
fix/<问题名>
ops/<部署变更名>
```

### 6.2 修改原则

- 优先复用现有 Registry、CA、Discovery、Mode Router、MQ 和网关边界。
- 不把新协议逻辑塞入旧路径而改变 legacy 行为；新增逻辑应按协议版本或功能开关分流。
- 前端所有平台 URL 使用当前 origin 或统一 API client，不硬编码服务器 IP。
- 不修改生产数据来制造测试条件；需要写操作时使用隔离数据库或明确可清理的测试实体。
- 不把 runtime `.env`、数据库、日志、证书、上传文件或备份提交到 Git。
- 云端服务以 `renta` 用户运行，发布后恢复 `renta:renta` 所有权。

### 6.3 前端开发

源码与构建产物：

```text
源码: wyl/frontend-source
运行产物: wyl/frontend
```

本机构建：

```powershell
cd D:/B-EP1/RenTA-dev/wyl/frontend-source
npm ci
npm run build:runtime
node ../frontend/test_agent_apply_bridge.js
```

云主机当前没有 Node.js，前端必须在本地构建后上传运行产物。部署前检查 `wyl/frontend/index.html` 引用的全部哈希资源存在，并扫描旧服务器地址：

```powershell
rg "10\.126\.126\.8" wyl/frontend wyl/frontend-source
```

### 6.4 后端测试

至少运行改动模块自己的测试。完整兼容门禁入口：

```bash
cd /opt/renta
PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/stage0_smoke.py
```

全量阶段 0 回归脚本应在具备完整测试依赖的开发/验收环境运行：

```bash
cd <完整源码工作树>
PYTHONDONTWRITEBYTECODE=1 bash scripts/stage0_regression.sh
```

不要假设生产主机的系统 Python 包含所有测试依赖；生产主机直接执行只读 smoke，专项测试则使用对应 `/opt/renta/venv/*`，并避免连接生产数据库执行写测试。

涉及 MQ Inbox 时补充：

```text
scripts/stage6_mq_e2e.py
```

涉及浏览器页面时使用真实浏览器检查：

- 正式入口必须使用 `http://120.27.205.185/`。
- PC 至少检查 `1440x900`。
- 响应式变更补测 `393x852` 或同级 iPhone 视口。
- 检查横向溢出、控制台错误、接口失败、导航、登录态和主要表单。
- 不使用生产账号执行不可逆写操作。

## 7. 安全部署流程

### 7.1 部署前备份

在云主机创建时间戳目录，只备份本次会覆盖的文件和相关数据库：

```bash
stamp=$(date +%Y%m%d_%H%M%S)
backup=/opt/renta/backups/dev_release_$stamp
install -d -m 0755 "$backup"
```

示例：前端发布时备份 `wyl/frontend`；Registry 变更时备份 Registry 文件、runtime 配置和 `registry_db`；CA 变更时必须备份 `agent_ca.db`。

### 7.2 发布产物

推荐从已测试提交生成 Git 归档，在 `/tmp` 解压后再同步。不要直接把工作树、`.git`、`node_modules` 或本机虚拟环境上传到生产。

发布时必须排除：

```text
runtime/
venv/
backups/
*.db
*.sqlite*
node_modules/
.git/
```

禁止对 `/opt/renta` 使用无排除规则的 `rsync --delete`。删除废弃文件时必须逐项确认，并在备份后显式删除。

### 7.3 最小重启

```bash
systemctl daemon-reload                 # 仅 unit 变化时
systemctl restart renta-<受影响服务>
systemctl is-active renta-<受影响服务>
journalctl -u renta-<受影响服务> -n 100 --no-pager
```

前端或网关代码变化：

```bash
systemctl restart renta-frontend
nginx -t
systemctl reload nginx
```

部署配置发生变化时，同步更新仓库内 `deployment/cloud`，不能只改 `/etc/systemd/system` 或 `/etc/nginx`。

### 7.4 发布后门禁

```bash
systemctl is-active renta.target nginx postgresql redis rabbitmq-server
systemctl --no-pager --state=failed
python3 -B /opt/renta/scripts/stage0_smoke.py
curl -fsS http://127.0.0.1/
curl -fsS http://127.0.0.1:8888/
ss -lntp
```

公网再检查：

```text
http://120.27.205.185/
http://120.27.205.185/square
http://120.27.205.185/renta-config
http://120.27.205.185/acps-atr-v2/acme/directory
```

同时扫描：

```bash
grep -RIl --exclude-dir=.git --exclude-dir=node_modules \
  '10\.126\.126\.8' /opt/renta/wyl/frontend /opt/renta/wyl/frontend-source
ss -ntp | grep '10\.126\.126\.8'
```

两个命令都不应产生有效运行依赖。

### 7.5 回滚

出现以下任一情况立即停止扩大发布并回滚：

- 生产数据库 migration 失败。
- `renta.target` 或基础中间件异常。
- smoke 不再是 `18/18`。
- 旧 API、02.00、旧 account/证书或 5672 兼容链路出现回归。
- 首页、登录、Agent 广场、申请、审批或管理页面出现阻断问题。

回滚顺序：

1. 停止受影响服务。
2. 恢复时间戳备份中的文件和数据库。
3. 恢复对应 runtime 配置或 systemd/Nginx 配置。
4. `daemon-reload` 后启动最小服务集合。
5. 重新运行 smoke 和专项测试。
6. 记录失败原因，不修改或删除既有验收证据。

## 8. 快速状态检查

登录云主机后执行：

```bash
systemctl is-active renta.target nginx postgresql redis rabbitmq-server

for s in registry ca challenge discovery group-bridge group-proxy \
  mq-auth mode-router direct-rpc frontend; do
  systemctl is-active "renta-$s"
done

ss -lntp | grep -E ':(80|8888|8001|8003|8004|8005|8098|8099|9007|9008|18080|19090|5432|6379|5671|5672)\b'

python3 -B /opt/renta/scripts/stage0_smoke.py
```

日志：

```bash
journalctl -u renta-registry -n 100 --no-pager
journalctl -u renta-ca -n 100 --no-pager
journalctl -u renta-discovery -n 100 --no-pager
journalctl -u renta-mode-router -n 100 --no-pager
journalctl -u renta-mq-auth -n 100 --no-pager
journalctl -u renta-frontend -n 100 --no-pager
journalctl -u nginx -n 100 --no-pager
```

## 9. 现有验收基线

最后一次完整回归：

| 范围 | 结果 |
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
| PC `1440x900` | 无横向溢出，控制台 0 错误 |
| iPhone 15 | 无横向溢出，控制台 0 错误 |

后续每次发布都应与这份基线比较，不能只证明新功能可用而忽略原功能回归。

## 10. 必读资料

```text
ACPS_V21_PLATFORM_UPGRADE_MODULES.md
ACPs_v2_1_upgrade_change_points.md
FINAL_ACPS_V21_UPGRADE_VALIDATION.md
docs/CLOUD_MIGRATION_ACCEPTANCE_20260713.md
PROJECT_LAYOUT.md
deployment/cloud/README.md
平台数据查询说明.md
```

协议升级前后模块差异以 `ACPS_V21_PLATFORM_UPGRADE_MODULES.md` 为最终汇总；云迁移证据以 `docs/CLOUD_MIGRATION_ACCEPTANCE_20260713.md` 和 `/opt/renta/backups/cloud_full_acceptance_20260714_082507` 为准。

## 11. 交接原则

1. GitHub `main` 是代码基线，云端 `/opt/renta` 是生产部署目录。
2. 生产环境不再依赖旧服务器，任何新改动都不能重新引入该依赖。
3. 先建立回滚点，再修改；先测试，再部署；部署后必须冒烟和浏览器验收。
4. 兼容 ACPs 02.00 和 RenTA 原功能是长期约束，不是一次性升级任务。
5. 密钥、密码、Token、数据库口令和证书私钥永远不进入 Git。
6. 代码、部署模板、升级文档和实际生产配置变化必须保持同步。
