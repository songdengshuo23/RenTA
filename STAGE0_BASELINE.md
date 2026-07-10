# RenTA ACPs v2.1 升级阶段 0 基线报告

- 记录时间：2026-07-10
- 远端主线：`/home/johnteller/team_ws`
- 分支：`upgrade/acps-v2.1-baseline`
- 基线代码提交：`a9b0295`
- 文档调整提交：`b36a0d2`

## 1. 阶段 0 结论

阶段 0 已完成。现有平台可以按原启动脚本完整启动，入口、公开 API、鉴权边界、CA、Challenge、Mode Router、Direct RPC 和前端关键页面均可访问。阶段 0 没有修改业务代码、数据库结构或现有接口。

后续升级必须以本报告记录的结果为最低兼容基线：已通过项不得减少，已知失败不得增加，新协议功能必须由默认关闭的兼容开关控制。

## 2. 数据快照

升级前快照保存在：

```text
/home/johnteller/team_ws/_archive/stage0_baseline_20260710_092416
```

快照内容：

- PostgreSQL `registry_db` 完整自定义格式备份：`registry_db.dump`。
- PostgreSQL 纯结构备份：`registry_schema.sql`。
- CA SQLite 数据库副本：`agent_ca.db`。
- 当前 Git 提交、工作区状态和启动前监听端口。
- `SHA256SUMS` 完整性校验文件。

快照目录权限按 `umask 077` 创建，且位于 Git 忽略的 `_archive` 中。

## 3. 运行基线

原启动脚本：`wyl/start_stack.sh`。

| 服务 | 端口 | 基线结果 |
|---|---:|---|
| Registry | 8001 | 正常监听，根接口和 OpenAPI 可访问 |
| CA | 8003 | 正常监听，health、ACME directory、trust bundle 可访问 |
| Challenge legacy | 8004 | 正常监听，ATR health 和 status 可访问 |
| Mode 2 Group Bridge | 8098 | health 正常 |
| Mode 2 Group Proxy | 8099 | health 正常 |
| Mode Router | 18080 | health 正常 |
| Direct RPC | 19090 | health 正常 |
| 前端与网关 | 8888 | 首页、前端路由和代理接口正常 |
| RabbitMQ | 5672 | 正常监听 |
| PostgreSQL | 5432，仅本机 | 正常监听 |

Registry 实际运行时为 Python 3.12.3，并同时加载：

```text
sds/registry-server/.py312deps
sds/registry-server/.venv/lib/python3.13/site-packages
```

前者提供 `asyncpg`，后者提供 `xattr`。升级期间不得擅自删减这两个路径。

## 4. HTTP 与页面基线

新增只读脚本：`scripts/stage0_smoke.py`。脚本不需要登录、不写数据库，覆盖 18 个端点，包括：

- `8888` 首页、公开 Agent、ACS 示例、事件接口。
- 旧 `/api` 网关代理。
- DSP 和 Passport 受保护接口的 `401` 鉴权边界。
- Mode Router 和 Direct RPC 网关代理。
- Registry、CA、Challenge、Group Bridge、Group Proxy 的正向健康接口。

浏览器检查结果：

- `/` 正常显示 RenTA 首页。
- `/square` 正常显示智能体广场，页面显示 12 个智能体、6 个分类。
- `/auth` 正常显示登录和注册表单，控制台无错误。
- 未登录访问 `/agent-apply`，正常跳转到 `/auth?redirect=/agent-apply`。

## 5. 数据行数基线

Registry Alembic 版本：`d9e0f1a2b3c4`。

| 表 | 行数 |
|---|---:|
| `account_role` | 3 |
| `account_user` | 17 |
| `account_user_role_link` | 19 |
| `agent` | 26 |
| `agent_passport` | 24 |
| `agent_supervisor_review` | 26 |
| `change_log` | 32 |
| `points_transaction` | 15 |
| `points_wallet` | 4 |
| `snapshot` | 0 |
| `webhook` | 0 |

这些数值用于发现误删或错误迁移，不要求业务运行期间保持静态。

## 6. 测试基线

第一轮完整测试结果：

| 模块 | 通过 | 已知失败/错误 | 说明 |
|---|---:|---:|---|
| Registry | 106 | 6 | 当前实现与部分 Passport/Supervisor 旧断言不一致 |
| CA | 119 | 0 | 使用隔离 SQLite 测试库，全部通过 |
| Challenge legacy | 4 | 0 | 全部通过 |
| Mode Router `tests/` | 42 | 2 | mode selector 和 plan strategy 旧断言不一致 |
| Mode Router 根测试 | 11 | 1 | final result 文案断言与当前实现不一致 |

一键回归脚本 `scripts/stage0_regression.sh` 会：

1. 运行 18 项只读 HTTP 冒烟检查。
2. 同时加载 Registry 的 `.py312deps` 和 `.venv` 依赖路径。
3. 为 CA 创建独立临时 SQLite 数据库，绝不清理生产 `agent_ca.db`。
4. 分开运行两个同名的 Mode Router 测试文件，避免 pytest 收集冲突。
5. 暂时排除上述 9 个已知基线失败，只把当前通过的测试作为零回归门禁。
6. 单独补跑被 pytest `--deselect` 前缀匹配连带跳过的 Mode Router 顺序依赖用例，确保 42 个原通过用例全部进入门禁。

已知失败保留在完整测试日志中，阶段 1 不得借协议升级顺便修改其业务行为；如需修复，应单独建分支并补充行为确认。

## 7. 重复验证

平台服务启动后，在远端执行：

```bash
cd /home/johnteller/team_ws
bash scripts/stage0_regression.sh
```

日志和隔离测试数据库默认写入：

```text
/home/johnteller/team_ws/_archive/stage0_regression_<timestamp>
```

2026-07-10 最终门禁执行成功，退出码为 `0`，产物目录为：

```text
/home/johnteller/team_ws/_archive/stage0_regression_20260710_094011
```

最终结果为 HTTP `18/18`、Registry `106 passed`、CA `119 passed`、Challenge `4 passed`、Mode Router `42 + 11 passed`。已知失败均被明确排除，没有新增失败。

## 8. 阶段 1 准入条件

阶段 1 从 `upgrade/acps-v2.1-aic-acs` 分支开始，按以下顺序实施：

1. 先加入默认保持旧行为的协议兼容开关。
2. 为 AIC v02.00 固化回归样例，再增加 v02.01 生成和校验。
3. ACS 保留 v02.00 读取，新增 v02.01 schema 和字段归一化。
4. 只让新注册 Agent 默认写入 v02.01；历史 Agent、AIC、ACS 和证书不改写。
5. 阶段 1 每个提交都运行 `scripts/stage0_regression.sh`，并补充 AIC/ACS 新旧双轨测试。

Registry EAB 和 CA EAB 不属于阶段 1，不应在 AIC/ACS 双轨兼容通过前提前接入。
