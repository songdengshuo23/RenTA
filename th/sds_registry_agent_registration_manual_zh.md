# Agent 上传与注册用户手册

更新时间：2026-06-11 01:21 CST

本手册面向 Agent 提供方或普通上传用户，按步骤说明如何把自己的 Agent 上传到新版 Registry，并提交平台审核。

当前使用的 Registry 地址：

```text
http://10.126.126.8:8001
```

如果你在服务器 `10.126.126.8` 本机操作，也可以使用：

```text
http://127.0.0.1:8001
```

> 注意：`18001` 是旧注册端，不用于新版 Supervisor/Passport 审核流程。上传新 Agent 请使用 `8001`。

## 一、你需要准备什么

上传前请准备好 4 类信息：

| 准备项 | 说明 |
|---|---|
| Agent 名称 | 例如：`云南亲子旅行规划 Agent` |
| Agent 版本 | 例如：`1.0.0` |
| Agent 描述 | 说明 Agent 能做什么、不能做什么 |
| Agent 服务地址 | 真实可调用的 RPC endpoint，例如 `http://10.126.126.1:8021/agents/poi_collector/rpc` |

建议 Agent 服务同时提供健康检查接口：

```text
GET http://你的主机:端口/health
```

最小返回示例：

```json
{
  "status": "healthy"
}
```

如果没有 `/health`，平台审核时可能出现 `endpoint_health_route` warning，需要人工复核或退回修改。

请特别注意：这里的“可访问”不是只要求你在自己的机器上能 `curl` 成功，而是要求新版 Registry/Supervisor 所在网络也能访问。当前 `8001` 运行在 Docker `sds-registry` 中，审核时会从 Registry 服务侧访问你的 RPC endpoint，并按 endpoint 的主机和端口推导健康检查地址：

```text
RPC:    http://你的主机:端口/agents/xxx/rpc
Health: http://你的主机:端口/health
```

如果你本机访问 `/health` 是 200，但审核结果仍提示 `endpoint_health_route`，通常说明 Registry 容器或 Registry 服务器访问不到这个地址。

## 二、整体上传流程

```text
1. 注册或登录账号
2. 准备 Agent ACS 信息
3. 创建 Agent 草稿
4. 提交审核
5. 查看 Supervisor 审核结果
6. 如有问题，修改后重新提交
7. 审核通过后，获取 AIC 和 Passport
8. 验证 Agent 是否出现在公开列表
```

下面按步骤操作。

## 三、第一步：设置 Registry 地址

在命令行中设置：

```bash
export REGISTRY_URL="http://10.126.126.8:8001"
```

如果在 Registry 服务器本机操作：

```bash
export REGISTRY_URL="http://127.0.0.1:8001"
```

## 四、第二步：注册账号

如果你还没有账号，先注册：

```bash
curl -sS -X POST "$REGISTRY_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "DemoPass123!",
    "email": "your_email@example.com",
    "name": "你的姓名或团队名",
    "org_name": "你的组织名称",
    "org_code": "ORG-001",
    "org_address": "Beijing"
  }'
```

密码建议满足：

- 8 到 20 位
- 包含大写字母
- 包含小写字母
- 包含数字
- 包含特殊字符

注册成功后会返回 token。你也可以继续执行下一步登录来获取 token。

## 五、第三步：登录并保存 Token

```bash
export CLIENT_TOKEN="$(
  curl -sS -X POST "$REGISTRY_URL/api/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=your_username&password=DemoPass123!" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
)"
```

检查 token 是否成功保存：

```bash
echo "$CLIENT_TOKEN" | cut -c1-24
```

如果能输出一段字符，说明登录成功。

后续所有上传、提交、查看自己 Agent 的操作都需要这个 token。

## 六、第四步：准备 Agent ACS

ACS 是 Agent Capability Spec，用来告诉平台：

- 这个 Agent 是谁
- 它能做什么
- 它的服务地址在哪里
- 它支持什么输入输出格式
- 它由谁提供和维护

你可以先获取平台提供的完整示例：

```bash
curl -sS "$REGISTRY_URL/api/agent/public/acs_example"
```

如果只想快速上传，可以从下面这个最小模板开始。

注意：当前 `8001` 后端会先按 ACS Schema 校验 `acs`。因此 `acs` 根节点必须包含 `aic`、`active`、`lastModifiedTime`。这三个字段语义上由 Registry 维护，但当前创建草稿接口仍要求提交时提供占位值，否则会返回 `invalid_acs`。

如果你看到下面这种错误：

```json
{
  "status_code": 400,
  "error_group": "agent",
  "error_name": "invalid_acs",
  "error_msg": "Json path: [ $ ]; Error message: [ 'aic' is a required property ]"
}
```

说明你上传文件里的 `acs` 根节点缺少 `aic`。请按本手册模板补上 `acs.aic`、`acs.active`、`acs.lastModifiedTime` 后再提交。`acs.aic` 这里可以先填临时占位值；审核通过后请以 Registry 返回的最终 `aic` 为准。

还要注意：当前创建草稿接口的 ACS Schema 不允许在 `endPoints[]` 中写自定义扩展字段，例如 `x-supervisorRuntime`。如果必填字段已经补齐，但仍保留该字段，会返回：

```json
{
  "status_code": 400,
  "error_group": "agent",
  "error_name": "invalid_acs",
  "error_msg": "Json path: [ $.endPoints[0] ]; Error message: [ Additional properties are not allowed ('x-supervisorRuntime' was unexpected) ]"
}
```

健康检查请直接在 Agent 服务根路径暴露 `GET /health`，并保证 Registry/Supervisor 所在网络可访问。

## 七、第五步：创建上传文件

创建文件 `agent-create.json`：

```json
{
  "name": "云南亲子旅行规划 Agent",
  "version": "1.0.0",
  "description": "为云南大理、丽江等目的地提供亲子旅行 POI、路线、预算和行程规划建议。",
  "is_ontology": false,
  "acs": {
    "aic": "1.2.156.3088.0001.00001.DEMOAG.DEMO01.1.0001",
    "active": true,
    "lastModifiedTime": "2026-06-10T11:45:00+08:00",
    "protocolVersion": "02.00",
    "name": "云南亲子旅行规划 Agent",
    "description": "为云南大理、丽江等目的地提供亲子旅行 POI、路线、预算和行程规划建议。",
    "version": "1.0.0",
    "provider": {
      "countryCode": "CN",
      "organization": "你的组织名称",
      "department": "Agent 团队",
      "url": "https://example.com",
      "license": "demo-license",
      "name": "维护人姓名",
      "email": "owner@example.com"
    },
    "securitySchemes": {
      "mtls": {
        "type": "mutualTLS",
        "description": "Agent 调用使用 mTLS 双向认证",
        "x-caChallengeBaseUrl": "http://10.126.126.8:8004/acps-atr-v2"
      }
    },
    "endPoints": [
      {
        "url": "http://10.126.126.1:8021/agents/demo_agent/rpc",
        "transport": "JSONRPC",
        "security": [
          {
            "mtls": []
          }
        ]
      }
    ],
    "capabilities": {
      "streaming": false,
      "notification": false,
      "messageQueue": []
    },
    "defaultInputModes": [
      "text/plain",
      "application/json"
    ],
    "defaultOutputModes": [
      "text/plain",
      "application/json",
      "text/markdown"
    ],
    "skills": [
      {
        "id": "travel.family.plan",
        "name": "亲子旅行规划",
        "description": "根据目的地、天数、同行人数和儿童需求生成旅行路线、POI、预算和注意事项。",
        "version": "1.0.0",
        "tags": [
          "travel",
          "family",
          "itinerary",
          "poi",
          "budget"
        ],
        "examples": [
          "帮我规划 5 天大理丽江亲子游",
          "生成云南亲子自由行预算和路线"
        ],
        "inputModes": [
          "text/plain",
          "application/json"
        ],
        "outputModes": [
          "text/plain",
          "application/json",
          "text/markdown"
        ]
      }
    ]
  }
}
```

你必须根据自己的 Agent 修改这些字段：

| 字段 | 必改吗 | 怎么填 |
|---|---|---|
| `name` | 是 | Agent 名称 |
| `version` | 是 | Agent 版本 |
| `description` | 是 | Agent 能力说明 |
| `acs.aic` | 是 | 当前后端创建草稿时必填。可先填临时占位 AIC；审核通过后以 Registry 返回的最终 `aic` 为准 |
| `acs.active` | 是 | 当前后端创建草稿时必填，通常填 `true` |
| `acs.lastModifiedTime` | 是 | 当前后端创建草稿时必填，使用 ISO 8601 时间，如 `2026-06-10T11:45:00+08:00` |
| `acs.provider` | 是 | 提供方信息 |
| `acs.endPoints[0].url` | 是 | 真实 RPC 地址 |
| `acs.skills` | 是 | Agent 技能列表 |

当前可提交的 `acs.endPoints[]` 字段只有：

| 字段 | 必填吗 | 说明 |
|---|---|---|
| `url` | 是 | 完整 RPC endpoint URL |
| `transport` | 是 | 通常填 `JSONRPC` |
| `security` | 否 | 安全要求，例如 `[{"mtls": []}]` |

不要在 `endPoints[]` 中填写 `x-supervisorRuntime`、`healthPath`、`healthUrl` 等扩展字段；当前 Schema 会拒绝这些字段。健康检查统一使用服务根路径 `/health`，并且必须从 Registry/Supervisor 所在网络可访问。

## 八、第六步：创建 Agent 草稿

执行：

```bash
curl -sS -X POST "$REGISTRY_URL/api/agent/client" \
  -H "Authorization: Bearer $CLIENT_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @agent-create.json \
  | tee create-response.json
```

成功后会返回 Agent 信息，其中最重要的是 `id`。

提取 Agent ID：

```bash
export AGENT_ID="$(python3 -c 'import json; print(json.load(open("create-response.json"))["id"])')"
echo "$AGENT_ID"
```

此时 Agent 只是草稿，状态通常是：

```text
approval_status = DRAFT
```

草稿还不会出现在公开发现列表中。

## 九、第七步：提交审核

确认草稿无误后，提交审核：

```bash
curl -sS -X POST "$REGISTRY_URL/api/agent/client/$AGENT_ID/submit" \
  -H "Authorization: Bearer $CLIENT_TOKEN" \
  | tee submit-response.json
```

提交后平台会自动进行 Supervisor 审核，包括：

- ACS 字段完整性检查
- endpoint 地址检查
- 健康检查路径检查
- 安全配置检查
- 风险等级判断
- Passport 草稿生成

提交后状态可能变成：

| 状态 | 含义 |
|---|---|
| `PENDING` | 等待审核或需要人工复核 |
| `APPROVED` | 已通过 |
| `REJECTED` | 已驳回 |

## 十、第八步：查看审核结果

查询最新 Supervisor 审核结果：

```bash
curl -sS "$REGISTRY_URL/api/agent/client/$AGENT_ID/supervisor-review/latest" \
  -H "Authorization: Bearer $CLIENT_TOKEN" \
  | python3 -m json.tool
```

重点看这些字段：

| 字段 | 说明 |
|---|---|
| `decision` | 审核决策，如 `APPROVE`、`MANUAL_REVIEW`、`REJECT` |
| `risk_level` | 风险等级，如 `LOW`、`MEDIUM`、`HIGH` |
| `permission_tier` | 派发权限等级 |
| `checks` | 审核检查项 |
| `required_fixes` | 需要修改的问题 |
| `passport_draft` | 平台生成的 Passport 草稿 |

如果看到类似下面的 warning：

```text
endpoint_health_route
```

通常说明你的 Agent 健康检查地址不可用。请先检查：

```bash
curl -i http://你的主机:端口/health
```

确保返回 HTTP 200。

如果你自己执行上面的命令是 HTTP 200，但审核仍然 warning，请让平台维护方从 Registry 服务器或 `sds-registry` 容器内再测同一个地址。原因是 Supervisor 审核以 Registry 服务侧网络为准，不以你本机网络为准。

## 十一、第九步：修改后重新提交

如果审核结果要求修改，先更新 `agent-create.json` 中的问题字段，然后调用更新接口。

```bash
curl -sS -X PUT "$REGISTRY_URL/api/agent/client/$AGENT_ID" \
  -H "Authorization: Bearer $CLIENT_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @agent-create.json \
  | tee update-response.json
```

然后再次提交：

```bash
curl -sS -X POST "$REGISTRY_URL/api/agent/client/$AGENT_ID/submit" \
  -H "Authorization: Bearer $CLIENT_TOKEN" \
  | tee submit-response.json
```

## 十二、第十步：查看 Passport

审核通过后，查询最新 Passport：

```bash
curl -sS "$REGISTRY_URL/api/agent/client/$AGENT_ID/passport/latest" \
  -H "Authorization: Bearer $CLIENT_TOKEN" \
  | python3 -m json.tool
```

重点看：

| 字段 | 说明 |
|---|---|
| `status` | Passport 状态，正常应为 `VALID` |
| `decision` | 正常应为 `APPROVE` |
| `permission_tier` | 平台允许的派发等级 |
| `passport_payload` | 给发现和派发系统使用的 Passport 内容 |

## 十三、第十一步：确认 Agent 是否公开可见

查询公开已通过 Agent：

```bash
curl -sS "$REGISTRY_URL/api/agent/public/recent?limit=100" \
  | python3 -m json.tool
```

在返回结果中查找你的 Agent 名称。

如果审核通过，返回中会出现类似：

```json
{
  "name": "云南亲子旅行规划 Agent",
  "approval_status": "APPROVED",
  "is_active": true,
  "aic": "1.2.156....",
  "acs": {
    "endPoints": [
      {
        "url": "http://10.126.126.1:8021/agents/demo_agent/rpc"
      }
    ]
  }
}
```

保存其中的 `aic`，后续平台发现、派发和证书流程会用到它。

## 十四、第十二步：平台内部按 AIC 查询 ACS

普通上传用户完成到“公开列表可见”和“Passport 为 VALID”即可。下面这个 ATR 接口主要给 Discovery、Mode Router、编排端或 Registry 内部服务使用，需要平台配置的服务令牌；普通用户 token 或匿名访问通常会返回 `401 Missing bearer token` 或 `403 Invalid token`。

如果你是平台维护方，可以这样验证：

```bash
export AGENT_AIC="你的 Agent AIC"
export REGISTRY_SERVICE_TOKEN="平台维护方提供的服务令牌"

curl -sS "$REGISTRY_URL/acps-atr-v2/acs/$AGENT_AIC" \
  -H "Authorization: Bearer $REGISTRY_SERVICE_TOKEN" \
  | python3 -m json.tool
```

如果能查到 ACS，说明 Registry 内部 ATR 接口已经可以通过 AIC 识别你的 Agent。

## 十五、上传成功的判断标准

满足下面条件，可以认为上传成功：

| 检查项 | 成功标准 |
|---|---|
| Agent 草稿创建 | 返回 `id` |
| 已提交审核 | `approval_status` 不再只是 `DRAFT` |
| Supervisor 审核 | 有 `review_id` 和 `decision` |
| 平台审批 | `approval_status = APPROVED` |
| AIC 分配 | 返回非空 `aic` |
| Passport | `status = VALID`，`decision = APPROVE` |
| 公开列表 | `/api/agent/public/recent` 能看到该 Agent |
| 内部 ATR 查询 | 平台维护方使用服务令牌访问 `/acps-atr-v2/acs/{aic}` 能返回 ACS |

## 十六、常见问题

| 问题 | 原因 | 解决办法 |
|---|---|---|
| `401 Missing bearer token` | 没带登录 token | 增加 `Authorization: Bearer $CLIENT_TOKEN` |
| `403 insufficient permissions` | 当前账号没有权限 | 使用上传账号登录；Staff 接口普通用户不能调用 |
| `/acps-atr-v2/acs/{aic}` 返回 `401` 或 `403` | 这是内部 ATR 接口，需要 Registry 服务令牌，不是普通用户 token | 普通上传用户不需要调用；平台维护方应使用 `REGISTRY_SERVICE_TOKEN` |
| `invalid_acs` 且提示 `'aic' is a required property` | `acs` 根节点缺少当前 Schema 要求的 `aic` | 在 `acs` 根节点补 `aic`、`active`、`lastModifiedTime`，其中 `aic` 可先填临时占位值 |
| `invalid_acs` 且提示 `x-supervisorRuntime was unexpected` | `endPoints[]` 里写了当前 Schema 不允许的扩展字段 | 删除 `x-supervisorRuntime`、`healthPath`、`healthUrl`，健康检查统一使用服务根路径 `/health` |
| 创建草稿后找不到公开 Agent | 草稿还没提交或没通过 | 继续提交审核并等待通过 |
| 没有 AIC | AIC 审核通过后才分配 | 等待审核通过 |
| `endpoint_health_route` warning | Registry/Supervisor 访问 `/health` 失败 | 给 Agent 服务根路径补 `GET /health`，并确保 Registry 服务侧网络可访问；当前创建草稿接口不要填写 `healthPath`、`healthUrl`、`x-supervisorRuntime` |
| 一直是 `PENDING` | 需要人工复核 | 根据 `required_fixes` 修改，或等待平台审核员处理 |
| `REJECTED` | 审核被驳回 | 查看 `process_comments` 和 `required_fixes` 后修改重提 |

## 十七、已实测通过的范围

2026-06-11 已按本手册模板在新版 `8001` Registry 实测：

| 操作 | 实测结果 |
|---|---|
| 注册上传用户 | 成功 |
| 登录并获取 token | 成功 |
| 创建 Agent 草稿 | 成功，返回 `id` 和 `approval_status = DRAFT` |
| 提交审核 | 成功，可返回 `approval_status = PENDING`；当所有自动检查通过时可直接 `APPROVED` |
| 查询 Supervisor 审核结果 | 成功，能返回 `decision`、`checks`、`passport_draft` |
| 查询 Passport | 成功；自动审核通过时 `status = VALID`、`decision = APPROVE` |
| 公开列表检查 | 成功，审核通过后 `/api/agent/public/recent?limit=100` 可见 |
| 中文字段保真 | 成功，UTF-8 JSON 上传后中文 Agent 名称在公开列表中保持不变 |
| 缺少 `aic` 的错误复现 | 成功复现 `invalid_acs` / `'aic' is a required property` |
| endpoint 扩展字段错误复现 | 成功复现 `invalid_acs` / `x-supervisorRuntime was unexpected` |
| ATR ACS 匿名/普通用户访问 | 已验证匿名返回 `401`，普通用户 token 返回 `403`，该接口需服务令牌 |
| 删除测试 Agent | 成功 |

实测结论：

1. 当 `acs` 包含 `aic`、`active`、`lastModifiedTime`，且 `endPoints[]` 不包含额外扩展字段时，创建草稿接口通过 Schema 校验。
2. 当 endpoint 和根路径 `/health` 能从 `sds-registry` 容器网络访问时，Supervisor 自动审核可直接 `APPROVE`，Passport 为 `VALID`。
3. `/acps-atr-v2/acs/{aic}` 是内部服务接口，不应作为普通上传用户的必做步骤；普通用户以创建、提交、审核、Passport、公开列表为准。
4. 当 endpoint 或 `/health` 只在 Agent 机器本机可访问、但 Registry 服务侧不可访问时，Supervisor 会进入 `MANUAL_REVIEW`，并提示 `endpoint_health_route`。这不是上传接口失败，而是 Agent 服务网络可达性或健康检查未通过。

## 十八、给 Agent 服务方的最低要求

为了提高审核通过率，请确保：

1. RPC endpoint 可从 Registry/Supervisor 所在网络访问。
2. endpoint 使用完整 URL，包括协议、主机、端口、路径。
3. Agent 服务实现 `/health`，并且从 Registry/Supervisor 所在网络访问时返回 HTTP 200。
4. ACS 中的 `name`、`description`、`skills` 能清楚说明能力边界。
5. `provider.email` 是可联系的维护邮箱。
6. `skills[].examples` 提供真实调用场景。
7. 不要把测试地址、不可访问地址、空 endpoint 提交到生产审核。

## 十九、用户不需要操作的内部接口

下面这些接口主要给 Discovery、Mode Router 或内部服务使用，普通上传用户通常不需要直接调用：

```text
/acps-atr-v2/passports/discovery
/acps-atr-v2/passports/{agent_aic}/dispatch
/acps-atr-v2/passports/runtime-review/schedule
/acps-dsp-v2/changes
/acps-dsp-v2/snapshots
```

你只需要完成：

```text
注册/登录 -> 创建草稿 -> 提交审核 -> 查看审核结果 -> 审核通过后保存 AIC
```
