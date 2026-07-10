# ca-server 本地启动说明

这份说明对应 `ACPs-CA-Client` 本地联调用的最小可用启动方式，目标是快速起一个 mock `ca-server` 来跑客户端 E2E。

## 1. 环境准备

```powershell
cd D:\B-EP1\ca-server
..\ACPs-CA-Client\acps_ca\Scripts\poetry.exe install --with dev
```

## 2. 本地配置

推荐使用仓库中的 `.env` 本地开发配置，关键点如下：

- `DATABASE_URL=sqlite:///./agent_ca.db`
- `AGENT_REGISTRY_MOCK=true`
- `HTTP01_VALIDATION_MOCK=true`
- `UVICORN_PORT=8003`

这套配置适合本地联调，不适合生产部署。

## 3. 启动服务

```powershell
cd D:\B-EP1\ca-server
..\ACPs-CA-Client\acps_ca\Scripts\poetry.exe run python main.py
```

启动后可验证：

```powershell
curl http://localhost:8003/acps-atr-v2/acme/directory
```

## 4. 与客户端联调

在客户端仓库中执行：

```powershell
cd D:\B-EP1\ACPs-CA-Client
.\scripts\run-e2e-mock-ca.ps1 -CaServerDir ..\ca-server
```

脚本会：

1. 启动 `ca-server`
2. 等待目录接口可访问
3. 执行客户端 `tests/e2e`
4. 测试结束后自动停止服务

## 5. 说明

- 当前客户端 E2E 已启用 `CHALLENGE_DEPLOY_MOCK=true`，因此本地联调时不需要额外部署 challenge server。
- mock 模式启动时，服务会自动初始化一个默认 OCSP responder，便于客户端 OCSP 场景通过。
- 如果端口 `8003` 已被占用，请先释放端口，再启动本地服务。
