# RenTA ACPs v2.1 阶段 4：前端与网关兼容升级完成报告

## 1. 完成结论

阶段 4 已于 2026-07-10 在远端主线完成。

```text
分支：upgrade/acps-v2.1-frontend-gateway
基线：5a14acec625aab952f23467cd4c9b16e6239aa97
代码提交：c467b00cf456ed85f421d4e3b6f6298cc4c44aeb
远端目录：/home/johnteller/team_ws
```

本阶段实现了 ACS 02.00/02.01 前端双轨、EAB 一次性凭据获取界面、CA/Registry 网关分流和 CA 外部 URL 重写。生产仍保持新前端与 EAB 关闭，因此原 02.00 页面、旧 `/api`、Registry、积分、事件、Passport、Supervisor、Mode Router 和 Challenge 行为不变。

## 2. 修改范围

| 文件 | 修改内容 |
|---|---|
| `wyl/frontend/assets/agent-apply-bridge.js` | 增加运行时开关、02.00/02.01 双轨 payload、certificate/AMQP、EAB 获取与内存清除、离开路由清理 |
| `wyl/frontend/assets/agent-apply-bridge.css` | 增加协议 segmented control、证书/AMQP 和 EAB 响应式样式 |
| `wyl/frontend/test_agent_apply_bridge.js` | 验证 02.00 兼容 payload、02.01 payload、transport 和表单校验 |
| `wyl/server/server.py` | 增加 CA 子路由、外部 Host/URL/Location 重写、`/renta-config` 和环境变量开关 |
| `wyl/server/test_server.py` | 网关路由边界、开关默认值、CA URL 重写单元测试 |
| `wyl/server/test_gateway_integration.py` | 用隔离 Registry/CA HTTP 上游验证 EAB/CA 分流、Host、Location、Replay-Nonce |
| `wyl/start_stack.sh` | 增加两个默认关闭的前端开关 |

未修改 Registry/CA 数据模型或数据库，未删除 Challenge Server，未修改编排、积分、事件、Passport 和 Supervisor。

## 3. 前端双轨实现

### 3.1 开关关闭

`ACPS_FRONTEND_V21_ENABLED=false` 时：

- 不显示协议版本、certificate、AMQP 等新控件。
- 继续生成 `protocolVersion=02.00`。
- 继续使用旧 AIC 临时值和 `x-caChallengeBaseUrl`。
- transport 继续支持 `JSONRPC`、`HTTP`、`SSE`、`WEBSOCKET`。
- 原 `/api/agent/client` 创建和 submit 调用不变。

### 3.2 开关开启

`ACPS_FRONTEND_V21_ENABLED=true` 时默认选择 02.01，同时保留“兼容 02.00”切换：

- 02.01 使用 `aic: "{AIC}"`，审批后由 Registry 写入真实 AIC。
- 主端点支持 `JSONRPC` 和 `HTTP_JSON`。
- 可增加 `AMQP` endpoint，支持 `inbox_{AIC}` 占位符。
- 可填写 certificate DNS SAN、IP SAN 和 `requestedValidity`。
- AMQP endpoint 存在时写入 `capabilities.messageQueue`。
- 02.01 不写 `x-caChallengeBaseUrl`。
- 切回 02.00 后立即恢复旧 transport 和 Challenge 字段。

### 3.3 EAB 凭据

`ACPS_FRONTEND_EAB_ENABLED=true` 时显示 EAB 工具：

```http
POST /acps-atr-v2/eab/{aic}
Authorization: Bearer <access_token>
```

安全处理：

- `macKey` 只保存在当前 bridge DOM 对象内存中。
- 不写 `localStorage`、`sessionStorage`、URL 或日志。
- 用户可主动复制或清除；5 分钟后自动清除。
- 页面卸载、离开 `/agent-apply` 或重置表单时立即清除。
- Clipboard API 不可用时使用一次性隐藏 textarea，复制后立即移除。
- 未登录跳到 `/auth` 后主动移除 bridge，避免 EAB UI 泄漏到登录页。

## 4. 网关分流

8888 外部入口保持不变，路由变为：

| 外部路径 | 内部服务 | 说明 |
|---|---|---|
| `/api/*` | Registry `8001` | 原平台 API 不变 |
| `/acps-atr-v2/eab/*` | Registry `8001` | EAB 用户签发 |
| `/acps-atr-v2/agent/*` 等 | Registry `8001` | ACS/ATR 路径不变 |
| `/acps-atr-v2/acme/*` | CA `8003` | ACME Directory/account/order/finalize |
| `/acps-atr-v2/ca/*` | CA `8003` | CA 扩展 API |
| `/acps-atr-v2/crl/*` | CA `8003` | CRL |
| `/acps-atr-v2/ocsp/*` | CA `8003` | OCSP |
| `/acps-dsp-v2/*` | Registry `8001` | DSP 不变 |
| `/acps-adp-v2/*` | Discovery `8005` | Discovery 不变 |
| `/mode-router/*` | Mode Router `18080` | 编排不变 |

CA 代理额外完成：

- 保留外部 Host，使 CA 的 ACME JWS protected URL 校验看到 8888 地址。
- 把 CA JSON 和 `Location` 中的 `localhost:8003`/`127.0.0.1:8003` 改写为请求的外部 origin。
- 保留 `Replay-Nonce` 等 ACME 响应头。
- 重写 body 后重新计算 `Content-Length`。
- 不记录请求体或 EAB `macKey`。

新增只读配置端点：

```http
GET /renta-config
```

## 5. 开关与生产状态

新增：

```text
ACPS_FRONTEND_V21_ENABLED=false
ACPS_FRONTEND_EAB_ENABLED=false
```

生产当前仍为：

```text
ACPS_V21_ENABLED=false
ACPS_EAB_ISSUANCE_ENABLED=false
ACPS_CA_EAB_ENABLED=false
ACPS_CHALLENGE_LEGACY_ENABLED=true
ACPS_FRONTEND_V21_ENABLED=false
ACPS_FRONTEND_EAB_ENABLED=false
```

启用顺序不能反转：先在隔离环境同时启用 Registry v2.1、Registry EAB 和 CA EAB 并通过真实签发，再开启 EAB 前端，最后开启 02.01 默认表单。

## 6. 验证结果

### 6.1 阶段 4 专项

```text
网关单元/隔离 HTTP 集成：12 passed
前端 payload 测试：passed
Python/JavaScript/Bash 语法检查：passed
```

覆盖：

- CA 子路径和 Registry EAB 路径边界。
- EAB 只到 Registry，ACME/CA/CRL/OCSP 只到 CA。
- CA Directory JSON、Location、Host、Replay-Nonce。
- 02.00 原 Challenge/transport/AIC payload。
- 02.01 `{AIC}`、HTTP_JSON、AMQP、messageQueue、SAN 和有效期。
- 02.01 错误 transport、AMQP 和有效期校验。
- EAB 不写 Web Storage。

### 6.2 浏览器验证

临时 18888 实例仅用于开启状态验证，完成后已关闭：

```text
桌面：1440 x 1000
移动：390 x 844
console errors：0
```

已验证 02.01 表单、ACS 预览、HTTP_JSON 自动选择、AMQP/SAN、EAB 工具、02.00 切换和离开路由清理。

### 6.3 总门禁与生产

```text
HTTP smoke：18/18
Registry：133 passed，6 deselected
CA：131 passed
Challenge legacy：4 passed
Mode Router：42 + 1 + 11 passed
总门禁：exit code 0
```

产物：

```text
/home/johnteller/team_ws/_archive/stage0_regression_20260710_185235
```

默认关闭重启 8888 后：

```text
/renta-config -> 两个开关均 false
/agent-apply -> 200
/acps-atr-v2/eab/{aic} -> 404（Registry EAB 路由未注册）
/acps-atr-v2/acme/directory -> 200，URL 为 http://10.126.126.8:8888/...
HTTP smoke -> 18/18
```

## 7. 回滚

代码回滚：

```bash
cd /home/johnteller/team_ws
git revert c467b00cf456ed85f421d4e3b6f6298cc4c44aeb
```

运行态快速回滚不需要回退数据库：

```text
ACPS_FRONTEND_V21_ENABLED=false
ACPS_FRONTEND_EAB_ENABLED=false
```

如果只需关闭新 UI，不需要回退 CA 路由；CA 路由不影响旧 Registry `/api` 和 `/acps-atr-v2/eab`。

## 8. 下一步：阶段 5

阶段 5 建议创建分支：

```text
upgrade/acps-v2.1-discovery-router
```

按以下顺序继续：

1. 冻结现有 `yhl/ACPs-Discovery-Server`、Registry DSP 和 Mode Router discovery 响应样例。
2. 对比官方 v2.1 Discovery 的 `agents`、`acsMap`、`routes`、`agentGroups`、`forwardChain` 契约。
3. 给新版 Discovery client 和 Mode Router 适配器增加默认关闭开关。
4. 查询顺序改为“新版 Discovery 优先，Registry `passports/discovery` fallback”。
5. 保留 `passports/{aic}/dispatch`、runtime review 和积分结算等 RenTA 平台策略接口。
6. 验证 Registry DSP snapshot/change/webhook 能把 02.00/02.01 ACS 同步到 Discovery。
7. 在隔离数据中验证 JSONRPC、HTTP_JSON、AMQP endpoint 解析；阶段 5 不切换 MQ 执行链路。
8. 跑 Discovery、Mode Router、Registry 和阶段 0 全量门禁，生产仍默认关闭新 Discovery 优先级。

阶段 5 完成后再进入阶段 6 MQ Inbox/mTLS，不能在 Discovery 契约尚未稳定时同时切换执行 transport。
