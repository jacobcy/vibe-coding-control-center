# Orchestra 发布接手手册

本文档面向后续接手发布的 agent，目标是用最少上下文完成验证、发布与风险控制。

更新时间：2026-05-16

## 1. 当前架构

Orchestra 采用**主动轮询 + 被动 webhook 混合架构**：

### 主动调度（核心）
- **GlobalDispatchCoordinator**：frozen queue + assignee pool
- 每个 tick 周期收集 ready issues，按优先级排序后逐个派发
- 通过 `vibe3 serve start` 启动的 heartbeat 驱动

### 被动响应（辅助）
- Webhook 事件处理：通过 `POST /webhook/github` 接收 GitHub 事件，验签后由 Orchestra Driver 直接路由到对应 handler
- 所有角色（manager / planner / executor / reviewer）均通过 `GlobalDispatchCoordinator` 冻结队列统一派发，无独立的 service 模块

### 关键配置（`config/v3/settings.yaml`）
- `orchestra.enabled: true`
- `orchestra.assignee_dispatch.enabled: true`
- `orchestra.pr_review_dispatch.enabled: true`
- `orchestra.manager_usernames` 包含目标管理账号（例如 `vibe-manager-agent`）
- `orchestra.webhook_secret`: GitHub webhook 签名密钥

## 2. 发布前检查

1. 配置检查
   - 以上配置项均已正确设置

2. webhook 检查（GitHub 仓库）
   - 事件至少勾选：`Issues`、`Pull requests`、`Issue comments`
   - URL 指向：`https://<public-host>/webhook/github`
   - secret 与 `orchestra.webhook_secret` 一致

3. 本地启动检查
   - 启动：
   ```bash
   uv run python src/vibe3/cli.py serve start -v --port 8080
   ```
   - 状态：
   ```bash
   curl -sS http://127.0.0.1:8080/status
   ```

## 3. 验证步骤（必须留证据）

### 3.1 干跑（建议先做）

```bash
uv run python src/vibe3/cli.py serve start -v --dry-run --port 8080
```

创建并指派 issue 给 `manager_usernames` 中的账号，预期行为：
- tick 周期触发后，coordinator 收集 ready issues
- 日志包含 `dispatch intent: manager for #<n>`
- dry-run 模式下跳过实际执行

### 3.2 真实执行（收口标准）

关闭 `--dry-run` 后再次创建并指派 issue，预期日志包含：
- `Flow ready: branch=task/issue-<n>`
- `Created manager worktree for flow branch`（首次）
- `Dispatching manager: uv run python -m vibe3 run ...`

同时检查：
- `serve` 工作树分支不应被切换
- `ps` 可看到 `codeagent-wrapper` 进程

## 4. 已知 follow-up

1. 临时 worktree 回收
   - PR 关闭后的 worktree 自动清理待实现
   - 追踪 issue：[#366](https://github.com/jacobcy/vibe-coding-control-center/issues/366)

## 5. 发布 agent 交付清单

1. 提交与 PR
- 包含代码 + 文档 + 测试证据
- PR 描述附上 dry-run 与非 dry-run 的日志片段

2. 验证结果记录
- 标注执行时间（绝对日期）
- 标注测试 issue 编号
- 标注是否出现回退/降级路径（如 `--worktree` 兼容降级）

3. 合并后复查
- 再做一次最小 issue 触发验证
- 确认 webhook 端到端仍可执行
