# RenTA ACPs v2.1 阶段 3：CA EAB 发证双轨升级完成报告

## 1. 结论与生产状态

2026-07-10 已在远端主线 `/home/johnteller/team_ws` 完成阶段 3，分支为 `upgrade/acps-v2.1-ca-eab`，核心代码提交为 `fed618e70b9686942f54bc091838e1b6b36c76fc`。本阶段是对现有 CA 的增量适配，没有用官方新 CA 目录覆盖 RenTA 旧实现。

已实现：

- CA 通过 Registry `/internal/eab/consume` 消费一次性 EAB 凭据。
- `new-account` 校验 `HS256` EAB JWS，将 account 公钥与 Registry 返回的 AIC 绑定。
- EAB account 只能为同一 AIC 下单，Authorization 直接为 `valid`，Order 直接为 `ready`，不创建 HTTP-01 Challenge。
- `finalize` 重新核对 account AIC、Order identifier、Registry ACS 和 CSR Subject/SAN。
- v2.1 新证书使用 `CN={AIC}`、`URI:acps://{AIC}`，DNS/IP SAN 和有效期来自 ACS `certificate`。
- legacy account 仍走原 HTTP-01 Challenge，旧证书、证书管理、CRL 和 OCSP 保持原逻辑。

生产当前仍保持：

```text
ACPS_CA_EAB_ENABLED=false
ACPS_CHALLENGE_LEGACY_ENABLED=true
ACPS_EAB_ISSUANCE_ENABLED=false
AGENT_REGISTRY_MOCK=true
```

CA Directory 当前返回 `externalAccountRequired=false`，因此尚未把生产新账户切换到 EAB。

## 2. 双轨行为

| 场景 | 行为 |
|---|---|
| `ACPS_CA_EAB_ENABLED=false` | 新 account 保持旧行为，不要求 EAB |
| 开关开启后新 account | 必须提供 EAB，绑定 account AIC |
| 已绑定 AIC 的 account | 始终走 EAB Order/finalize，防止回滚准入开关后已有账户失效 |
| `aic IS NULL` 的旧 account | 在 legacy 开关下继续 HTTP-01 Challenge |
| Registry EAB 失败/超时/过期/重放 | 失败关闭，不创建绑定 account |
| EAB account 请求其他 AIC | `INVALID_IDENTIFIER`，不创建 Order |
| Challenge Server | 继续运行，只服务 legacy account |

`AGENT_REGISTRY_MOCK=true` 仍只影响 legacy 校验；EAB account 的 ACS 查询会强制走真实 Registry。

## 3. 代码修改

| 文件 | 修改 |
|---|---|
| `sds/ca-server/app/acme/eab_verifier.py` | EAB JWS 结构、`alg`、URL、`kid`、JWK payload、HMAC 校验 |
| `sds/ca-server/app/acme/agent_registry.py` | Registry EAB consume client，内部 URL 推导，ACS certificate 字段解析 |
| `sds/ca-server/app/acme/api.py` | `directory/new-account/new-order/finalize` 双轨分流 |
| `sds/ca-server/app/acme/models.py` | `acme_accounts.aic` nullable/indexed 模型字段 |
| `sds/ca-server/app/acme/schemas.py` | `AccountCreate.aic` |
| `sds/ca-server/app/acme/services.py` | account AIC 持久化、v2.1 CSR 身份边界校验、证书参数分流 |
| `sds/ca-server/app/core/ca_manager.py` | v2.1 裸 AIC CN、`acps://` URI SAN 和 ACS DNS/IP SAN |
| `sds/ca-server/app/core/config.py` | CA EAB/legacy 开关、Registry internal URL、证书有效期上限 |
| `sds/ca-server/alembic/versions/d4e5f6a7b8c9_add_aic_to_acme_accounts.py` | 纯增量 nullable `aic` 列与索引，支持 downgrade |
| `sds/ca-server/scripts/stage3_ca_migration_check.py` | 生产 SQLite 结构指纹、行数和 Alembic 状态检查 |
| `sds/ca-server/tests/test_eab_transition.py` | 阶段 3 专项和双轨集成测试 |
| `sds/ca-server/.env.example` | 新开关与 Registry internal URL 示例 |
| `wyl/start_stack.sh` | 生产启动默认关闭 CA EAB，保留 legacy |

## 4. 数据库迁移

生产 CA 历史上由 `SQLModel.metadata.create_all()` 建表，升级前没有 `alembic_version`，不能直接执行旧建表 migration。本次处理为：

1. 校验 ACME、通用证书、CRL/OCSP 表的结构指纹。
2. 确认当前结构已等价于旧 head `9b3d2b7c1a6f`。
3. `alembic stamp 9b3d2b7c1a6f`，不重放旧 DDL。
4. `alembic upgrade head`，只增加 `acme_accounts.aic` 和索引。

在生产副本完成了 upgrade/downgrade/re-upgrade，随后生产迁移到：

```text
alembic_version=d4e5f6a7b8c9
acme_accounts=0
acme_orders=0
acme_authorizations=0
acme_challenges=0
acme_certificates=0
certificates=23
integrity_check=ok
```

备份：

```text
/home/johnteller/team_ws/_archive/stage3_ca_eab_20260710_153509
/home/johnteller/team_ws/_archive/stage3_ca_eab_20260710_161005_predeploy
```

## 5. 验证结果

### 5.1 CA 专项与全量

```text
阶段 3 EAB/transition 专项：12 passed
CA 全量：131 passed
其中升级前原测试：119/119 保持通过
```

专项覆盖：正确 EAB、缺失字段、错误 `alg`/URL/`kid`/JWK/HMAC、Registry 失败、重放、AIC 不匹配、legacy fallback、CSR Subject/SAN 以及 v2.1 证书内容。过期与一次性并发消费由阶段 2 Registry 专项持续覆盖。

### 5.2 真实跨服务 E2E

使用临时 PostgreSQL Registry 克隆库、真实 SM4 EAB 密文/消费接口和隔离 SQLite CA，完成：

```text
new-account=201
new-order=ready
finalize=valid
certificate CN=AIC
certificate SAN 包含 URI:acps://AIC 与 ACS DNS/IP
EAB replay=400
```

测试结束后临时数据库、`18001` 进程和 CA 测试库均已删除。

### 5.3 总门禁

```text
HTTP smoke: 18/18
Registry: 133 passed, 6 deselected
CA: 131 passed
Challenge legacy: 4 passed
Mode Router: 41 + 1 + 11 passed
exit code: 0
```

产物：

```text
/home/johnteller/team_ws/_archive/stage0_regression_20260710_161731
```

第一次门禁的 Mode Router 在线分类请求曾出现一次瞬时 HTTP 500；目标用例单独重试通过，第二次完整门禁退出码为 0。

## 6. 回滚

优先只回滚新准入：

```text
ACPS_CA_EAB_ENABLED=false
ACPS_CHALLENGE_LEGACY_ENABLED=true
ACPS_EAB_ISSUANCE_ENABLED=false
```

已绑定 AIC 的 account 仍会继续完成已有 EAB Order，不会因关闭新 account 准入而中断。

如必须回退数据库：

1. 先停止 CA 并备份 `agent_ca.db`。
2. 确认不再需要 `acme_accounts.aic` 的绑定数据。
3. 执行 `python3 -m alembic downgrade 9b3d2b7c1a6f`。
4. 回退阶段 3 代码并重启 CA。
5. 重跑阶段 0 总门禁。

不要在存在非空 `account.aic` 时直接降级，否则会丢失 account-AIC 绑定。

## 7. 阶段 4 如何继续

下一步是“阶段 4：前端与网关兼容适配”，建议从本阶段最终提交创建 `upgrade/acps-v2.1-frontend-gateway`。

1. 先冻结 `wyl/frontend` 当前申请、审批、详情和 Square 页面回归，盘点 `wyl/server/server.py` 现有代理路由。
2. Agent 申请表单增加 ACS 02.01 `certificate.altNames.dns/ip`、`requestedValidity` 和 AMQP endpoint，旧 02.00 表单继续保留。
3. 前端不自行生成 AIC；继续由 Registry 审批后写入 v02.01 AIC。
4. 在 8888 网关增加 Registry EAB 用户接口和 CA ACME/CA 路由的明确转发，保留旧 `/api`、积分、事件、Passport 和 Supervisor 路由。
5. EAB `macKey` 只在凭据创建响应中显示，不记录到前端日志、URL、localStorage 或网关日志。
6. 增加前端/网关双轨测试：旧 Agent 页面、旧 API、新 ACS 预览、EAB 申请和 CA 路由全部覆盖。
7. 阶段 4 隔离端到端通过后，才同时灰度开启 Registry EAB 和 CA EAB；先只对一个新 v02.01 Agent 开放，Challenge 继续保留。

阶段 4 验收门槛：旧前端功能和 18 个 HTTP 入口全部不变，新 Agent 能从页面提交 ACS 02.01、获取 EAB 并调用 CA，且敏感 EAB MAC key 无持久化泄漏。
