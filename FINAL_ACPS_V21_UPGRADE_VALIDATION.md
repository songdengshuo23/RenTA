# RenTA ACPs v2.1 全面升级最终验收

## 1. 验收结论

RenTA 的 ACPs v2.1 兼容升级已完成到阶段 7。协议代码、数据库 migration、EAB/CA、前端/网关、Discovery、MQ Inbox/mTLS、回滚开关和测试均已落地。

最终远端状态：

```text
branch=upgrade/acps-v2.1-mq-inbox
final_code_commit=f854f4a858cb2cca00c82bf1b3086435750a7c95
validation_docs=the subsequent documentation commit containing this file
platform=http://10.126.126.8:8888
```

“完成升级”不等于“立即强制切换所有生产 Agent”。当前采用兼容上线：代码与基础设施完整，v2.1 主链路默认关闭，旧功能继续运行；后续按 Agent 灰度开启。

## 2. 阶段交付

| 阶段 | 状态 | 核心结果 |
|---|---|---|
| 0 基线 | 完成 | 目录、端口、数据库和回归基线冻结 |
| 1 AIC/ACS | 完成 | 02.00/02.01 双轨，提交 `2e9bd07` |
| 2 Registry EAB | 完成 | SM4 密文、一次消费、migration，提交 `0e8baf4` |
| 3 CA EAB | 完成 | EAB account/order/finalize、v2.1 CN/SAN，提交 `fed618e` |
| 4 前端/网关 | 完成 | 02.01 表单和 EAB/CA 路由，提交 `c467b00` |
| 5 Discovery | 完成 | v2.1 响应保真和 Registry fallback，提交 `230ccc4` |
| 6 MQ/mTLS | 完成 | 5671、mq-auth、Inbox、隔离 SDK，提交 `f08912f` |
| 7 最终验收 | 完成 | PC 路由修复和全量门禁，最终提交 `f854f4a` |

## 3. 最终运行拓扑

| 服务 | 端口 | 状态 |
|---|---:|---|
| Registry | 8001 | active |
| CA | 8003 | active |
| Challenge legacy | 8004 | active |
| group bridge | 8098 | active，MQ Inbox consumer 0 |
| group proxy | 8099 | active |
| 平台网关/前端 | 8888 | active |
| Mode Router | 18080 | active |
| Direct RPC | 19090 | active |
| RabbitMQ legacy | 5672 | active |
| RabbitMQ mTLS | 5671 | active |
| mq-auth Group/Auth | 9007/9008 | active |
| Redis ACL | 6379 localhost | active |
| Discovery v2.1 | 8005 | 默认关闭 |

## 4. 生产兼容开关

```text
ACPS_V21_ENABLED=false
ACPS_LEGACY_API_ENABLED=true
ACPS_AIC_DUAL_READ_ENABLED=true
ACPS_EAB_ISSUANCE_ENABLED=false
ACPS_CA_EAB_ENABLED=false
ACPS_CHALLENGE_LEGACY_ENABLED=true
ACPS_FRONTEND_V21_ENABLED=false
ACPS_FRONTEND_EAB_ENABLED=false
ACPS_DISCOVERY_V21_ENABLED=false
ACPS_DISCOVERY_LEGACY_FALLBACK_ENABLED=true
ACPS_MQ_AUTH_ENABLED=false
ACPS_MQ_INBOX_ENABLED=false
ACPS_MQ_LEGACY_FALLBACK_ENABLED=true
```

关闭新开关时，平台继续使用旧 ACS 02.00、Challenge、Registry discovery、5672 group chat、Direct RPC/HTTP。

## 5. 自动化验收

最终归档：

```text
/home/johnteller/team_ws/_archive/stage0_regression_20260711_091307
```

归档包含日志和 `SHA256SUMS`。

| 套件 | 结果 |
|---|---|
| 只读 HTTP smoke | 18/18 |
| Registry | 133 passed，6 deselected |
| CA | 131 passed |
| Challenge | 4 passed |
| Mode Router tests | 48 passed，3 deselected |
| Mode Router sequential | 1 passed |
| Mode Router root | 17 passed，1 deselected |
| Discovery | 4 passed |
| Gateway | 12 passed |
| mq-auth | 185 passed |
| ACPs v2.1 SDK | 27 passed |
| 前端 02.00/02.01 payload | passed |
| 真实 MQ Inbox mTLS | passed |

警告仅为 Pydantic/Starlette 依赖弃用提示，以及官方 MQ SDK 关闭顺序产生的两条 channel cleanup 日志。

## 6. PC 浏览器验收

测试视口：1440x1000，Chrome/Playwright。

| 流程 | 结果 |
|---|---|
| 首页和四段内容 | 正常，控制台 0 error |
| 全局菜单 | 首页、广场、工作台、出租、账户、退出入口正常 |
| 广场 | 12 个 Agent 加载；搜索、分类和排序控件正常 |
| Agent 详情 | 能力、价格、API、评价和对话区域正常 |
| 注册/登录/退出 | API 200，路由和 local auth 状态正常 |
| 账户 | 资料、积分、账户安全入口正常 |
| 工作台/我的智能体 | 新账户空状态和创建入口正常 |
| Agent 申请 | 02.00 默认表单正常；ACS 预览生成 JSONRPC/mTLS payload；未提交 |
| `/chat` 页面 | 页面和编排请求正常 |
| 普通用户访问管理页 | `/admin/approval`、`/admin/monitor` 正确重定向首页 |
| 未登录保护 | `/chat`、`/agent-apply` 正确跳转登录 |

浏览器截图和快照位于本机：

```text
D:/B-EP1/output/playwright
```

验收中发现并修复了阶段 4 bridge 的 PC 空白页问题：离开 `/agent-apply` 时原逻辑把 `data-agent-apply-bridge` 设为空值，CSS 仍会按属性存在隐藏其他路由。现改为删除属性，并增加静态回归断言及资源缓存版本。

## 7. 实际 Agent 调用说明

聊天请求已到达 Mode Router，Registry discovery、路由分类和编排返回正常。当前选中 Agent 的 RPC endpoint 为 `10.126.126.1:8026`，该端点不可达，因此真实业务输出未作为最终验收门禁。

按当前验收约定：

- 不修改 Registry 中真实 endpoint。
- 不用假响应替换真实主链路。
- 页面、编排、错误展示和 200 响应已验证。
- 待可用 Agent 恢复后，再补一次实际业务结果回归。

测试期间创建的临时普通用户及唯一角色关联已删除，浏览器 token、cookie、session/local storage 已清理。

## 8. 数据与旧功能保护

- Registry 原有 points、events、Passport、Supervisor 未被官方代码覆盖。
- CA 旧 account、旧证书和 Challenge legacy 保留。
- RabbitMQ 5672 和 vhost `/` 保留并真实邀请通过。
- 旧 `acps_sdk.aip` 未覆盖。
- Direct RPC、HTTP、group bridge/proxy 未删除。
- 运行时证书、私钥、`.env`、日志、数据库和虚拟环境未提交 Git。

## 9. 回滚入口

任何灰度异常先关闭对应开关，不回退数据库：

1. MQ 异常：关闭 `ACPS_MQ_INBOX_ENABLED`。
2. Discovery 异常：关闭 `ACPS_DISCOVERY_V21_ENABLED`。
3. CA/EAB 异常：关闭 `ACPS_CA_EAB_ENABLED` 和 `ACPS_EAB_ISSUANCE_ENABLED`。
4. 前端异常：关闭 `ACPS_FRONTEND_V21_ENABLED` 和 `ACPS_FRONTEND_EAB_ENABLED`。
5. 保持 legacy、dual-read 和 fallback 开启。

基础设施回滚使用各阶段 `_archive` 备份，尤其是：

```text
/home/johnteller/team_ws/_archive/stage6_mq_20260710_210017
```

## 10. 升级后的下一步

不再新增协议开发阶段，进入灰度运维：

1. 恢复至少一个真实可用的 02.01 测试 Agent endpoint。
2. 为测试 Agent 开启 Registry EAB 和 CA EAB，验证短期证书续期。
3. 开启 Discovery v2.1，观察 Registry fallback 率。
4. 为该 Agent 发布 AMQP Inbox endpoint，再开启 MQ Inbox。
5. 指标稳定后扩大到新注册 Agent；旧 Agent 不强迁。
6. 建立证书到期、mq-auth 403/5xx、Redis ACL、RabbitMQ channel 和 fallback 告警。
