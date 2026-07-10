# Registry 端健康检查修复记录

更新时间：2026-06-09 23:25 CST

## 结论

10.126.126.1 上那 9 个 agent 是按正常 ACS/Registry 流程注册进平台的；它们的业务入口是 `endPoints[].url` 中的 JSON-RPC 地址，例如 `http://10.126.126.1:8021/agents/poi_collector/rpc`。之前注册端只校验 endpoint URL、安全引用、mTLS 等静态信息，没有把服务根路径 `/health` 作为注册证据，所以“正常注册”和“没有 `/health` 路由”可以同时发生。

注册端已修复：新提交/复审时会为每个 endpoint 派生 `healthCheckUrl`，默认探测服务根路径 `/health`；如果返回 404、超时或非 2xx，会产生 `endpoint_health_route` warning，并进入人工复核，不再静默放行。

## 已修改位置

- 源码：`/home/johnteller/team_ws/sds/registry-server/app/agent/supervisor.py`
- 已同步容器：`sds-registry-passport-source`，映射端口 `18002`
- 已同步容器：`sds-registry`，映射端口 `18001`
- 远端备份：`/home/johnteller/team_ws/sds/registry-server/app/agent/supervisor.py.bak_before_health_fix_20260609_231450`

## 前端可读字段

注册审查结果：

```json
{
  "checks": [
    {
      "checkId": "endpoint_health_route",
      "status": "warning",
      "evidence": ["Unhealthy endpoint health checks: ..."]
    }
  ],
  "passportDraft": {
    "acp": {
      "endpoints": [
        {
          "url": "http://host:port/agents/name/rpc",
          "healthCheckUrl": "http://host:port/health"
        }
      ]
    }
  }
}
```

Discovery/Passport 摘要也会透传：

```text
passport.acp.endpoints[].url
passport.acp.endpoints[].healthCheckUrl
passport.reviewEvidence.warningChecks
```

## 运行时 RPC 修复

注册端的运行时探测默认 JSON-RPC 方法已从旧的 `tasks.run` 改为 AIP v2 要求的 `rpc`，并默认生成 `params.command: TaskCommand`：

```json
{
  "jsonrpc": "2.0",
  "method": "rpc",
  "params": {
    "command": {
      "type": "task-command",
      "id": "cv_probe",
      "senderRole": "leader",
      "senderId": "registry-supervisor",
      "command": "start",
      "dataItems": [{"type": "text", "text": "..."}]
    }
  }
}
```

## 当前探测状态

- `http://10.126.126.8:8021/health`、`8022/health`、`8023/health` 当前返回 HTTP 200。
- 2026-06-09 23:34 CST 从 `10.126.126.8` 再测 `10.126.126.1:8021-8029`：9 个 agent 的 TCP、`/openapi.json`、AIP `method: "rpc"` 调用均成功；业务 RPC 当前可用。
- `/health` 路由仍未作为业务可用性的判断条件。注册端现在会在注册/复审阶段独立记录 `endpoint_health_route`，后续补 `/health` 后该 warning 才会消失。
