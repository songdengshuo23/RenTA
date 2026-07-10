# RenTA ACPs v2.1 阶段 1：AIC/ACS 双轨兼容升级完成报告

完成时间：2026-07-10

远端主线：`/home/johnteller/team_ws`

分支：`upgrade/acps-v2.1-aic-acs`

阶段 0 基点：`1a85c52cbe0617c628b76d67d608888a0166b94c`

阶段 1 代码提交：`2e9bd07af7449ff1c7cbb87557e923009d68593c`

新版协议基线：ACPs-community `v2.1.0` / `39cc7113f00e80df93b2033224a3b93750c16958`

## 1. 完成结论

阶段 1 已完成。RenTA Registry 现在具备 AIC v02.00/v02.01 和 ACS 02.00/02.01 双轨能力，同时保持生产运行态默认走旧写入链路：

- 历史 AIC、ACS、Agent、证书和接口没有迁移或改写。
- `ACPS_V21_ENABLED=false` 时，新 ACS 02.01 写入返回 `409`，旧 ACS 02.00 行为不变。
- `ACPS_V21_ENABLED=true` 时，ACS 02.01 Agent 可创建，并在审批时生成 v02.01 AIC。
- AIC 双读默认开启，v02.00 与 v02.01 均可识别。
- ACS 02.01 支持 `certificate`、AMQP endpoint，且不再要求旧 `x-caChallengeBaseUrl`。
- ACS 02.00 仍保留 Challenge URL 格式、可达性和 Supervisor 检查。
- Registry EAB、CA EAB 和数据库迁移没有提前进入阶段 1。

当前运行配置：

```text
ACPS_V21_ENABLED=false
ACPS_LEGACY_API_ENABLED=true
ACPS_AIC_DUAL_READ_ENABLED=true
```

## 2. 协议行为前后差异

### 2.1 AIC

旧 v02.00 布局：

```text
1.2.156.3088.<ARSP>.<VENDOR>.<ONTOLOGY_SN>.<INSTANCE_SN>.<VER>.<CRC16>
```

新 v02.01 布局：

```text
1.2.156.3088.<VER>.<ARSP>.<VENDOR>.<ONTOLOGY_SN>.<INSTANCE_SN>.<CRC16>
```

| 行为 | 升级前 | 阶段 1 后 |
|---|---|---|
| 默认生成 | 只生成 v02.00 | 开关关闭生成 v02.00，开启后按 ACS 版本生成 |
| 校验 | 只识别 v02.00 | 默认双读 v02.00/v02.01 |
| 版本判断 | 无 | `get_aic_spec_version()` 返回 `02.00` 或 `02.01` |
| 本体/实体转换 | 固定旧段位 | 自动按布局选择 instance 段位 |
| 派生实体查询前缀 | 固定旧段位 | 自动按布局生成 LIKE 前缀 |
| 模糊布局 | 无明确策略 | 优先按 legacy 解释，保护历史数据 |

### 2.2 ACS

| 行为 | ACS 02.00 | ACS 02.01 |
|---|---|---|
| Schema | 原 `acsSchema.json` | 官方 v2.1 `acsSchema.json` 以 `acsSchema-v02.01.json` 引入 |
| `x-caChallengeBaseUrl` | 必填并检查格式、可达性 | 可缺省，不参与新协议审批阻断 |
| `certificate.altNames` | 不支持 | 支持 |
| `certificate.requestedValidity` | 不支持 | 支持 |
| AMQP endpoint | 不支持 | 支持 `amqp://`、`amqps://` |
| `{AIC}` 占位符 | 无 | 审批分配 AIC 后替换 |
| Supervisor 健康探测 | HTTP/HTTPS | AMQP 不进入 HTTP 健康探测 |
| 新写入 | 默认允许 | 受 `ACPS_V21_ENABLED` 控制 |
| 已存数据读取 | 保持可读 | 即使写开关关闭也保持可读 |

阶段 1 Schema 的 Git blob 为 `e987c3370b52e078b16b56b19107907693bc3e30`，与 ACPs-community v2.1 官方 `registry-server/app/agent/acsSchema.json` 完全一致。

## 3. 实际修改文件

| 文件 | 修改内容 | 兼容措施 |
|---|---|---|
| `sds/registry-server/app/core/config.py` | 增加三个阶段 1 开关 | 默认保持旧写入行为 |
| `sds/registry-server/.env.example` | 记录开关和值 | 不覆盖生产 `.env` |
| `sds/registry-server/app/utils/aic.py` | 增加 v02.00/v02.01 生成、校验、版本识别和派生逻辑 | 保留原 API，新增参数为可选 |
| `sds/registry-server/app/utils/acs.py` | 按 `protocolVersion` 选择 Schema 和校验规则 | 读路径双版本，写路径受开关控制 |
| `sds/registry-server/app/agent/acsSchema-v02.01.json` | 引入官方 ACS 02.01 Schema | 原 Schema 文件不改、不删除 |
| `sds/registry-server/app/agent/service.py` | 创建/更新使用写入门禁；审批按 ACS 版本生成 AIC；替换 AMQP `{AIC}` | 历史 Agent 不重算 AIC |
| `sds/registry-server/app/agent/supervisor.py` | 02.01 不要求 Challenge；按 transport 校验 endpoint | 02.00 检查 ID、结果和行为保持不变 |
| `wyl/start_stack.sh` | 正式启动入口固定三个开关默认值 | 保留原令牌、数据库和联合依赖路径 |
| `sds/registry-server/tests/test_acps_v21_compat.py` | 新旧 AIC/ACS、开关、审批、AMQP、Supervisor 契约测试 | 独立测试文件，不改既有断言 |
| `sds/registry-server/tests/fixtures/acs/v02_01_example.json` | ACS 02.01 官方示例夹具 | 只用于测试 |

Registry 启动仍同时加载：

```text
sds/registry-server/.py312deps
sds/registry-server/.venv/lib/python3.13/site-packages
```

## 4. 验证结果

### 4.1 阶段 1 专项

```text
tests/test_acps_v21_compat.py: 14 passed
```

覆盖：

- v02.00 默认生成与校验。
- v02.01 新布局生成与校验。
- 两种布局的本体/实体派生。
- 双读开关与旧写入默认值。
- ACS 02.00 Challenge 校验。
- ACS 02.01 certificate、AMQP 和无 Challenge 校验。
- 02.01 写入开关门禁。
- 审批按 ACS 版本选择 AIC。
- AMQP `{AIC}` 替换且不修改原始输入对象。
- Supervisor 对 02.00/02.01 Challenge 的分流。
- AMQP URL 合法且不进入 HTTP 健康探测。

### 4.2 Registry 全量

```text
126 collected
120 passed
6 failed
```

6 个失败节点与阶段 0 完全一致，没有新增失败：

```text
tests/test_atr_api.py::test_get_passport_dispatch_returns_eligible_view
tests/test_atr_api.py::test_get_passport_dispatch_blocks_failed_health_probe
tests/test_supervisor.py::test_review_executes_runtime_validation_against_real_endpoint
tests/test_supervisor.py::test_runtime_repeat_count_updates_reliability
tests/test_supervisor.py::test_llm_approved_warning_review_auto_publishes_for_discovery
tests/test_supervisor.py::test_manual_staff_approval_publishes_manual_review_passport
```

### 4.3 阶段 0 总门禁复跑

```text
HTTP smoke: 18/18
Registry: 120 passed, 6 deselected
CA: 119 passed
Challenge legacy: 4 passed
Mode Router: 42 + 11 passed
exit code: 0
```

产物：

```text
/home/johnteller/team_ws/_archive/stage0_regression_20260710_103350
```

Registry 使用正式启动脚本重启后再次执行 HTTP smoke，结果仍为 `18/18`。

### 4.4 开关与数据验证

- 开关关闭：ACS 02.01 新写入返回 HTTP `409`。
- 临时开启：ACS 02.01 草稿创建返回 HTTP `200`，v02.01 AIC 生成布局验证正确，certificate 和 AMQP 字段可持久化。
- 临时 Agent 和账号已清理，Registry 已恢复 `ACPS_V21_ENABLED=false`。
- 没有新增 Alembic migration，版本仍为 `d9e0f1a2b3c4`。

阶段 1 完成后的数据行数：

| 表 | 行数 | 与阶段 0 |
|---|---:|---|
| `account_user` | 17 | 一致 |
| `account_user_role_link` | 19 | 一致 |
| `agent` | 26 | 一致 |
| `agent_passport` | 24 | 一致 |
| `agent_supervisor_review` | 26 | 一致 |
| `change_log` | 32 | 一致 |
| `points_transaction` | 15 | 一致 |
| `points_wallet` | 4 | 一致 |

## 5. 运行与回滚

正常启动：

```bash
cd /home/johnteller/team_ws
bash wyl/start_stack.sh
```

运行态回滚不需要回退数据库：

```text
ACPS_V21_ENABLED=false
ACPS_LEGACY_API_ENABLED=true
ACPS_AIC_DUAL_READ_ENABLED=true
```

然后只重启 Registry 并执行：

```bash
cd /home/johnteller/team_ws
python3 scripts/stage0_smoke.py
bash scripts/stage0_regression.sh
```

如代码级回滚，可在独立回滚分支对 `2e9bd07af7449ff1c7cbb87557e923009d68593c` 执行 `git revert`。阶段 1 没有数据库结构变化，因此不需要降级 migration。

## 6. 阶段 2 如何继续

下一步是“阶段 2：Registry EAB 旁路能力”，范围只到 Registry 生成和一次性消费 EAB 凭据，不切换 CA 主链路。

建议按以下顺序实施：

1. 从当前阶段 1 提交创建 `upgrade/acps-v2.1-registry-eab` 分支。
2. 先新增 `ACPS_EAB_ISSUANCE_ENABLED=false`，关闭时不注册或拒绝 EAB 生成接口。
3. 适配官方 `app/eab/{model,schema,exception,service,api}.py`，沿用 RenTA 当前 `BaseException`、登录态、角色和 `REGISTRY_SERVICE_TOKEN`，不能直接覆盖认证层。
4. 增加 `eab_credential` 表 migration，只新增表和索引，不修改 `agent`、积分、事件、Passport、Supervisor 表。
5. 增加 `SM4_ENCRYPTION_KEY` 和 EAB 有效期配置；`macKey` 只在生成和成功消费时返回，数据库只存密文。
6. 增加用户接口 `POST /acps-atr-v2/eab/{agent_aic}`，仅允许已登录的 Agent 所有者为已审批、active、未删除、未禁用的 v02.01 Agent 生成。
7. 增加内部接口 `POST /internal/eab/consume`，使用独立内部服务令牌，事务内 `SELECT ... FOR UPDATE`，确保并发下只能成功消费一次。
8. 测试生成、所有权、状态、过期、重复消费、并发消费、密文存储、开关关闭、migration upgrade/downgrade。
9. 复跑阶段 1 专项、Registry 全量和阶段 0 总门禁。
10. 阶段 2 完成后仍保持 CA 使用旧 Challenge；到阶段 3 才让 CA 旁路调用 EAB consume。

阶段 2 的验收门槛：

- `ACPS_EAB_ISSUANCE_ENABLED=false` 时现有平台行为与阶段 1 完全一致。
- migration 在生产数据副本上 upgrade/downgrade 成功，原表行数和数据不变。
- EAB 只能由 Agent 所有者生成，只能消费一次，过期后不可消费。
- EAB 密钥不明文落库、不写日志。
- CA、Challenge、前端、网关、Mode Router 不需要因阶段 2 改动即可继续运行。
- 阶段 0 总门禁继续通过且没有新增失败。
