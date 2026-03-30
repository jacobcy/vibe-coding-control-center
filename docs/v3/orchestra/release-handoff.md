# Orchestra 发布接手手册

本文档面向后续接手发布的 agent，目标是用最少上下文完成验证、发布与风险控制。

更新时间：2026-03-29

## 1. 本次变更摘要

本轮关键改动聚焦 manager 执行闭环：

1. 触发身份配置
- `manager_usernames` 支持专用账号（当前建议包含 `vibe-manager-agent`）。

2. manager 执行稳定性
- 不再切换 `serve` 进程当前分支。
- issue flow 分支不存在 worktree 时自动创建 `.worktrees/issue-<number>`。
- 在目标 worktree 执行 `vibe3 run`，避免污染守护进程上下文。

3. 兼容策略
- 若目标分支 `vibe3 run` 暂不支持 `--worktree`，自动去掉该参数继续执行（兼容旧分支）。

## 2. 发布前检查

1. 配置检查（`config/settings.yaml`）
- `orchestra.enabled: true`
- `orchestra.assignee_dispatch.enabled: true`
- `orchestra.pr_review_dispatch.enabled: true`
- `orchestra.manager_usernames` 包含 `vibe-manager-agent`

2. webhook 检查（GitHub 仓库）
- 事件至少勾选：`Issues`、`Pull requests`
- URL 指向：`https://<public-host>/webhook/github`
- secret 与 `orchestra.webhook_secret` 一致

3. 本地启动检查
- 启动：
```bash
uv run python src/vibe3/cli.py serve start --async -v --port 8080
```
- 状态：
```bash
curl -sS http://127.0.0.1:8080/status
```

## 3. 验证步骤（必须留证据）

### 3.1 干跑（建议先做）

```bash
uv run python src/vibe3/cli.py serve start --async -v --dry-run --port 8080
```

创建并指派 issue 给 `vibe-manager-agent`，预期日志包含：
- `Received: issues/assigned`
- `Webhook: #<n> assigned to 'vibe-manager-agent' (manager)`
- `Parsed webhook to command: uv run python -m vibe3 run ...`
- `Dry run, skipping execution`

### 3.2 真实执行（收口标准）

关闭 `--dry-run` 后再次创建并指派 issue，预期日志包含：
- `Flow ready: branch=task/issue-<n>`
- `Created manager worktree for flow branch`（首次）
- `Dispatching manager: uv run python -m vibe3 run ...`

同时检查：
- `serve` 工作树分支不应被切换
- `ps` 可看到 `codeagent-wrapper` 进程

## 4. 已知 follow-up

1. 临时 worktree 回收尚未完成
- 追踪 issue：[#366](https://github.com/jacobcy/vibe-coding-control-center/issues/366)
- 说明：`do-*` / manager 临时 worktree 自动回收策略需后续落地。

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
