# RenTA 仓库无用文件清理记录

## 1. 清理结论

本次清理以远端 `/home/johnteller/team_ws` 为主线。活动服务保持原路径不变：

- Registry：`sds/registry-server`
- CA：`sds/ca-server`
- Challenge legacy：`sds/challenge-server`
- Orchestrator / Mode Router：`th/mode_router`
- Discovery / Partner：`yhl`
- Frontend / Gateway：`wyl/frontend`、`wyl/server`
- 当前仍被导入的 SDK：`ACPs_update_code/ACPs-SDK`

`cyf/ACPs-Registry-Server` 没有运行进程、监听端口、启动依赖、systemd/cron/Docker 或源码调用引用，实际 Registry 是 `sds/registry-server`，因此已删除 `cyf` 整体。

## 2. Bundle 过大的原因

阶段 3 完整分支 bundle 为 `232,302,961` 字节，主要原因是 Git 历史中跟踪了 `sds/image-parts`：20 个 10 MiB 分片和 1 个尾部分片，合计 `214,516,705` 字节。这些文件是旧 Docker 镜像归档分片，不参与构建或运行。

阶段 3 增量 bundle 只有 `19,560` 字节，说明阶段代码改动本身很小，体积来自历史大对象而不是升级代码。

本次已从当前代码树删除镜像分片，并在 `.gitignore` 中增加 `*.tar.gz.part*` 和 `sds/image-parts/`。但 `.git` 仍约 227 MiB，因为旧提交仍可达这些对象。完整历史 bundle 不会因普通删除提交立即变小；真正清除历史对象需要单独执行历史重写和 GitHub force push，本次没有进行该高影响操作。

清理后当前暂存代码树的 `git archive --format=tar.gz` 为 `17,363,818` 字节，说明当前版本本身已经明显缩小；它与包含全部历史对象的 full bundle 是两种不同产物。

## 3. 已删除内容

### 3.1 重复或弃用服务

```text
cyf/
ACPs_update_code/ACPs-Registry-Server/
ACPs_update_code/ACPs-CA-Server/
ACPs_update_code/ACPs-CA-Challenge/
ACPs_update_code/ACPs-CA-Client/
ACPs_update_code/ACPs-Discovery-Server/
```

活动 Discovery 配置已统一到 `yhl/ACPs-Discovery-Server/.env`。`ACPs_update_code` 只保留仍被 Mode Router 和 Partner 启动路径使用的 `ACPs-SDK`。

### 3.2 大文件与备份

```text
sds/image-parts/
wyl/frontend_backups/
sds/registry-server/backups/
th/mode_router/backups/
yhl/ACPs-Discovery-Server/backups/
wyl/server/ChatView_backups/
wyl/server/AgentDashboardView_backups/
模块内 *.bak*、*backup*、*.orig、*.old 文件
sds/ca-server/.test-venv/
```

还删除了前端依赖闭包不可达的 25 个旧 Vite 哈希产物，共 `1,075,825` 字节。删除后 `wyl/frontend/assets` 为 39 个资源，39 个均可由当前 `index.html`、JS 懒加载或 CSS 依赖到达。

本轮从远端工作目录释放至少约 1.47 GB；阶段 0-3 数据库备份和迁移证据仍保留在 `_archive/stage*`。

## 4. 配套修改

1. `start_all_servers.sh` 不再启动 CYF Registry、端口 18001 和旧 `my_registry_db`，活动 SDS Registry 启动路径不变。
2. `th/mode_router/literature_workflow.py` 的默认 Discovery 配置改为活动的 `yhl/ACPs-Discovery-Server/.env`。
3. 删除两个失效语义软链接：`legacy_registry_cyf`、`legacy_acps_reference`；保留 `legacy_acps_sdk`。
4. Mode Router 外部路由 LLM 发生受控调用失败时使用已有本地规则 fallback，避免超时直接返回 500；正常 LLM 成功路径不变。
5. `.gitignore` 补充下划线/连字符备份名和镜像分片规则，避免同类文件再次提交。

## 5. 验证结果

- 结构检查：无失效语义软链接，无源码或启动脚本引用已删除路径。
- 前端依赖图：`39/39` 静态资源可达，无悬空旧构建产物。
- HTTP 冒烟：`18/18`。
- Registry：`133 passed`，6 个既有外部场景保持 deselected。
- CA：`131 passed`。
- Challenge：`4 passed`。
- Mode Router：`42 passed`、顺序规划 `1 passed`、根接口 `11 passed`。
- Playwright：首页、广场、登录、受保护路由正常；广场静态资源和 `/api/agent/public/recent` 均为 200；控制台 0 error。
- 生产数据只读复核：Registry 行数仍为 users 17、agents 26、passports 24、reviews 26、points transaction 15、points wallet 4、EAB 0，Alembic 为 `f1a2b3c4d5e6`；CA 旧证书仍为 23，Alembic 为 `d4e5f6a7b8c9`。
- 回归证据：`/home/johnteller/team_ws/_archive/stage0_regression_20260710_180502`。

## 6. Git 体积后续策略

日常同步继续使用相对上一远端提交的增量 bundle，可保持 KB 级。若要让完整 clone/full bundle 也显著缩小，需要在所有升级分支合并后统一执行一次历史重写，删除历史中的 `sds/image-parts` 大对象，再 force push GitHub；该操作会改变历史提交哈希，应作为独立维护任务执行。
