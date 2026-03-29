# Reviewer Webhook 调试手册

本手册用于调试 Orchestra 的 reviewer 触发链路（`pull_request/review_requested`）。

目标：确认 GitHub webhook 事件能够触发本地 `vibe3 review pr <number>`，并生成可观测产物。

边界说明：这里调试的是 webhook -> 本机执行链路，不是 GitHub Actions self-hosted runner。

## 1. 配置基线（reviewer-only 模式）

`config/settings.yaml` 的 `orchestra` 建议如下：

```yaml
orchestra:
  enabled: true
  repo: "jacobcy/vibe-coding-control-center"
  port: 8080
  webhook_secret: "your-secret"
  manager_usernames:
    - "your-github-login"

  polling:
    enabled: false
  assignee_dispatch:
    enabled: false
  pr_review_dispatch:
    enabled: true
    async_mode: false
  comment_reply:
    enabled: false
  master_agent:
    enabled: false
```

## 2. 启动与状态检查

建议用 `-v` 启动，确保能看到触发日志：

```bash
uv run python src/vibe3/cli.py serve start -v --port 8080 --repo jacobcy/vibe-coding-control-center
```

后台模式（tmux）：

```bash
uv run python src/vibe3/cli.py serve start --async -v --port 8080 --repo jacobcy/vibe-coding-control-center
```

检查健康状态：

```bash
curl -sS http://127.0.0.1:8080/health
curl -sS http://127.0.0.1:8080/status
```

期望关键字段：
- `services` 包含 `PRReviewDispatchService`
- `polling_enabled` 为 `false`

## 3. 触发链路（签名请求）

当 `webhook_secret` 已配置时，必须带 `X-Hub-Signature-256`。

示例（本地模拟 `review_requested`）：

```bash
payload='{"action":"review_requested","requested_reviewer":{"login":"your-github-login"},"pull_request":{"number":347,"requested_reviewers":[{"login":"your-github-login"}]}}'
sig=$(uv run python - <<'PY'
import hmac, hashlib
payload=b'{"action":"review_requested","requested_reviewer":{"login":"your-github-login"},"pull_request":{"number":347,"requested_reviewers":[{"login":"your-github-login"}]}}'
secret=b'your-secret'
print("sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest())
PY
)
curl -sS -i -X POST "http://127.0.0.1:8080/webhook/github" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: ${sig}" \
  --data "${payload}"
```

成功返回应为 `200` 且 `{"status":"accepted","event":"pull_request"}`。

## 4. 控制台预期日志

典型成功链路日志：

```text
Received: pull_request/review_requested (source=webhook)
PR review dispatch triggered (requested_reviewer=your-github-login)
Resolved PR review to matching worktree
Dispatching review: uv run python -m vibe3 review pr 347 (cwd=...)
Review execution completed successfully
```

说明：
- `Resolved PR review to matching worktree` 表示已根据 PR `head_branch` 找到对应 worktree。
- 找不到时会回退到 `serve` 进程启动目录。
- 若 `pr_review_dispatch.async_mode=true`，命令会追加 `--async` 并转入 tmux 后台执行。

## 5. 结果验收

检查 handoff：

```bash
uv run python src/vibe3/cli.py handoff list -b task/issue250-orchestra-manager -k review
```

检查 flow 时间线：

```bash
uv run python src/vibe3/cli.py flow show
```

期望：
- 出现新的 `handoff_review` 事件
- `audit_ref` 更新到最新 review artifact

## 6. 常见问题

1. `401 Missing webhook signature`
- 原因：配置了 `webhook_secret` 但请求没带签名头。

2. `403 Invalid webhook signature`
- 原因：GitHub 端 secret 与本地 `orchestra.webhook_secret` 不一致。

3. Funnel 看起来好了，但 `tailscale funnel status` 报本地 socket 错误
- 如果用的是 userspace 模式，需使用 `scripts/tsu.sh` 的命令通道：
  - `scripts/tsu.sh funnel status`
  - `scripts/tsu.sh serve list`

## 7. 概念澄清：`manager_usernames` vs `code-reviewer`

- `requested_reviewer=<your-github-login>`：GitHub 侧“触发身份”（用户名匹配条件）。
- `code-reviewer`：本地执行 `vibe3 review pr` 时使用的 agent preset（由 `review.agent_config.agent` 决定）。

两者不是同一个概念：
- 前者负责“是否触发”
- 后者负责“触发后由谁执行”
