# RenTA ACPs v2.1 阶段 2：Registry EAB 旁路能力完成报告

完成时间：2026-07-10

远端主线：`/home/johnteller/team_ws`

分支：`upgrade/acps-v2.1-registry-eab`

阶段 1 基点：`23573588037122b24df15f65dc8284999386239d`

阶段 2 代码提交：`0e8baf4de43e51f215d656a27afff802d6310894`

新版协议基线：ACPs-community `v2.1.0` / `39cc7113f00e80df93b2033224a3b93750c16958`

## 1. 完成结论

阶段 2 已完成。RenTA Registry 已移植 ACPs v2.1 EAB 凭据生成和一次性消费能力，并通过默认关闭开关保持原平台行为不变。

已完成：

- 新增 EAB Credential 数据模型、Schema、异常、服务和 API。
- 新增用户签发接口 `POST /acps-atr-v2/eab/{agent_aic}`。
- 新增 CA 内部消费接口 `POST /internal/eab/consume`。
- 仅允许 CLIENT 登录用户为本人拥有、已审批、active、未删除、未禁用的 ACS/AIC v02.01 Agent 生成 EAB。
- EAB `macKey` 使用 SM4-CBC 加密后落库，明文只在生成和成功消费时返回。
- 消费使用 PostgreSQL `SELECT ... FOR UPDATE`，并发请求只能成功一次。
- 支持过期、重复消费、不存在、非所有者、未审批、inactive、旧协议等错误分支。
- 新增可升降级 Alembic migration，并完成生产库副本和生产库验证。
- CA、Challenge、前端、网关、积分、事件、Passport、Supervisor 和 Mode Router 代码未修改。

当前生产运行态：

```text
ACPS_V21_ENABLED=false
ACPS_LEGACY_API_ENABLED=true
ACPS_AIC_DUAL_READ_ENABLED=true
ACPS_EAB_ISSUANCE_ENABLED=false
```

因此 EAB 两个路由当前返回 `404`，旧平台入口和接口保持不变。阶段 3 完成 CA 双轨接入前，不开启生产 EAB。

## 2. 接口与安全行为

### 2.1 EAB 生成

```http
POST /acps-atr-v2/eab/{agent_aic}
Authorization: Bearer <RenTA user access token>
```

成功返回 HTTP `201`：

```json
{
  "keyId": "一次性凭据 ID",
  "macKey": "Base64URL 编码的 32 字节 MAC key",
  "aic": "v02.01 AIC",
  "expiresAt": "带时区的过期时间"
}
```

签发条件：

1. `ACPS_EAB_ISSUANCE_ENABLED=true`。
2. `SM4_ENCRYPTION_KEY` 是 16 字节/32 位十六进制密钥。
3. 当前用户具有 CLIENT 角色并拥有该 Agent。
4. Agent 已审批、active、未删除、未禁用。
5. Agent ACS 为 `02.01`，AIC 为 v02.01 布局。

### 2.2 EAB 消费

```http
POST /internal/eab/consume
Authorization: Bearer <REGISTRY_SERVICE_TOKEN>
Content-Type: application/json

{"keyId": "..."}
```

成功返回 HTTP `200`：

```json
{
  "macKey": "...",
  "aic": "..."
}
```

消费行为：

- 使用现有 Registry 内部服务令牌，不接受普通用户令牌。
- 查询行加 `FOR UPDATE` 锁。
- 成功后写入 `is_consumed=true` 和 `consumed_at`。
- 第二次消费返回 `EAB_ALREADY_CONSUMED`。
- 过期返回 `EAB_EXPIRED`。
- 解密失败或事务失败时回滚，不把凭据标记为已消费。

## 3. 数据库变化

新增表：`eab_credential`。

| 字段 | 用途 |
|---|---|
| `id` | UUID 主键 |
| `key_id` | 对外一次性 ID，唯一索引 |
| `mac_key_encrypted` | SM4 加密后的 MAC key |
| `aic` | 绑定的 v02.01 AIC |
| `user_id` | 签发用户，外键到 `account_user.id` |
| `is_consumed` | 是否已消费 |
| `consumed_at` | 消费时间 |
| `expires_at` | 过期时间 |
| `created_at` | 创建时间 |

Migration：

```text
e7f6a5b4c3d2 -> f1a2b3c4d5e6
```

阶段 2 开始前发现：代码 head 已是 `e7f6a5b4c3d2`，生产 Alembic 标记仍是 `d9e0f1a2b3c4`，但 `points_wallet` 和 `points_transaction` 已由现有启动逻辑创建。处理方式：

1. 对生产库执行即时 `pg_dump`。
2. 在生产副本核对积分表、列数和数据行数。
3. 在副本把版本标记从 `d9e0...` 对账到 `e7f6...`。
4. 在副本执行 EAB upgrade、生命周期探测、downgrade 和 re-upgrade。
5. 全部通过后，在生产执行相同的版本对账和纯新增表 migration。

生产迁移后：

```text
alembic_version=f1a2b3c4d5e6
eab_credential=0
```

原业务表行数全部未变。

## 4. 实际修改文件

| 文件 | 修改内容 |
|---|---|
| `sds/registry-server/app/eab/model.py` | EAB Credential SQLModel |
| `sds/registry-server/app/eab/schema.py` | 生成和消费请求/响应 Schema |
| `sds/registry-server/app/eab/exception.py` | EAB 错误码和 RenTA 异常适配 |
| `sds/registry-server/app/eab/service.py` | 所有权检查、签发、加密、行锁和一次性消费 |
| `sds/registry-server/app/eab/api.py` | 用户和内部服务 API |
| `sds/registry-server/app/core/crypto.py` | 官方 SM4/SM3 工具适配 |
| `sds/registry-server/app/core/config.py` | EAB 开关、密钥和有效期配置 |
| `sds/registry-server/main.py` | 开关开启时才导入并注册 EAB 路由 |
| `sds/registry-server/alembic/env.py` | 注册 EAB metadata |
| `sds/registry-server/alembic/versions/f1a2b3c4d5e6_add_eab_credential_table.py` | EAB 表 migration |
| `sds/registry-server/pyproject.toml` | 增加 `gmssl>=3.2.2,<4.0.0` |
| `sds/registry-server/.env.example` | 记录 EAB 配置 |
| `wyl/start_stack.sh` | 正式启动默认关闭 EAB |
| `sds/registry-server/tests/test_eab.py` | EAB 单元/API 契约测试 |
| `scripts/stage2_eab_db_probe.py` | 隔离 PostgreSQL 生命周期和并发探测 |
| `scripts/stage2_eab_migration_check.sh` | 迁移、降级和重升级门禁 |

`gmssl 3.2.2` 和 `pycryptodomex 3.23.0` 已安装到 Registry 的 `.py312deps`，原 `.venv` 中的 `xattr` 路径继续同时加载。

## 5. 验证结果

### 5.1 专项和全量测试

```text
阶段 1 + 阶段 2专项：27 passed
EAB 专项：13 passed
Registry 全量：133 passed, 6 个阶段 0 既有失败
```

6 个失败节点与阶段 0、阶段 1 完全一致，没有新增失败。

### 5.2 隔离数据库

生产库副本验证：

```text
SM4 密文存储：通过
两个并发消费者：1 个成功，1 个 EAB_ALREADY_CONSUMED
过期拒绝：通过
migration upgrade：通过
migration downgrade：通过
migration re-upgrade：通过
用户和积分数据：未变化
```

### 5.3 总回归

```text
HTTP smoke: 18/18
Registry: 133 passed, 6 deselected
CA: 119 passed
Challenge legacy: 4 passed
Mode Router: 42 + 11 passed
exit code: 0
```

回归产物：

```text
/home/johnteller/team_ws/_archive/stage0_regression_20260710_112507
```

迁移、备份和生命周期产物：

```text
/home/johnteller/team_ws/_archive/stage2_eab_20260710_112024
```

其中包含：

- `registry_production_before_migration.dump`
- `production_before.log` / `production_after.log`
- 隔离库 upgrade/downgrade/re-upgrade 日志
- 并发消费和过期验证日志
- `SHA256SUMS`

### 5.4 生产重启验证

Registry 使用 `wyl/start_stack.sh` 重启后：

- 四个 ACPs 开关值符合预期。
- EAB 用户和内部路由均未注册，直接请求返回 `404`。
- 原平台 HTTP smoke 仍为 `18/18`。
- `8001`、`8003`、`8004`、`8098`、`8099`、`18080`、`19090`、`8888` 正常监听。

## 6. 回滚

首选回滚只需保持：

```text
ACPS_EAB_ISSUANCE_ENABLED=false
```

此时 EAB 模块不会导入，路由不会注册，原平台继续运行。保留空 EAB 表不会影响旧代码。

如必须回滚数据库和代码：

1. 确认 `eab_credential` 为空，或先备份 EAB 数据。
2. 在当前阶段 2 代码上执行 `alembic downgrade e7f6a5b4c3d2`。
3. 对阶段 2 代码提交执行 `git revert 0e8baf4de43e51f215d656a27afff802d6310894`。
4. 重启 Registry 并执行阶段 0 总门禁。

不要直接回退代码而把 Alembic 标记留在旧代码不认识的 `f1a2b3c4d5e6`。

## 7. 阶段 3 如何继续

下一步是“阶段 3：CA EAB 发证双轨升级”。目标是让新 v02.01 Agent 的 ACME account 使用 EAB 绑定 AIC，同时保留旧 account、旧证书和 HTTP-01 Challenge 链路。

建议顺序：

1. 从阶段 2 最终提交创建 `upgrade/acps-v2.1-ca-eab`。
2. 增加 `ACPS_CA_EAB_ENABLED=false` 和 `ACPS_CHALLENGE_LEGACY_ENABLED=true`。
3. 在 CA 增加 Registry EAB consume client，使用与 Registry 一致的内部服务令牌。
4. 适配官方 `eab_verifier.py`，校验 EAB JWS 的 `alg=HS256`、URL、`kid`、account JWK payload 和 HMAC 签名。
5. 给 ACME account 增加可空 `aic` 字段；旧 account 保持 `NULL`，新 EAB account 写入 v02.01 AIC。
6. `new-account` 双轨：新 v02.01 请求要求 EAB；旧流程在 legacy 开关下继续可用。
7. `new-order` 校验订单 Agent identifier 与 account AIC 一致；EAB account 不再创建 HTTP-01 Challenge。
8. `finalize` 继续校验 Registry ACS、CSR Subject/SAN 和 account AIC，不改变旧证书状态。
9. 增加无 EAB、伪造签名、错误 JWK、错误 URL、重放、过期、AIC 不匹配、Registry 超时和 legacy fallback 测试。
10. 先在隔离 CA/Registry 数据库完成端到端签发，再灰度开启 CA EAB；Challenge Server 继续运行，到全链路稳定后才降为纯 legacy。

阶段 3 验收门槛：

- 开关关闭时 CA 的 119 个原测试和现有 HTTP-01 行为不变。
- 正确 EAB 可创建绑定 AIC 的 account，并完成 order/finalize/证书下载。
- 缺失、伪造、过期或重复消费的 EAB 必须失败。
- EAB account 不能为其他 AIC 下单。
- 旧 account、旧 order、旧证书和 Challenge 流程继续可用。
- Registry EAB 异常时不得误签证书，也不得影响旧链路。
