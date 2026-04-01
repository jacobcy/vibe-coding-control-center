# Fix Plan: Orchestra & Review Bug Fixes (Issues #401/#402/#403/#404)

**Date**: 2026-04-01  
**Base**: origin/main (2a8cb4f2)  
**Branch**: fix/orchestra-review-bugs  
**Issues**: #401, #402, #403, #404

---

## Bug Summary

### #401 / #402 (重复 issue): CommentReplyService 自触发循环

**文件**: `src/vibe3/orchestra/services/comment_reply.py`

**根因**: `handle_event` 收到 `issue_comment/created` 后，检测到 manager mention 就调 `_post_ack`。但 ack 内容包含 `` `@username` `` 格式的文字，GitHub 不会触发 mention 事件；然而 ack body 中若不小心含裸 `@username`（如 f-string 变更），GitHub 会再次 emit `issue_comment` 事件，导致无限循环。

**加固措施（两层防御）**:

1. **Sentinel 标记**: ack body 中加入固定标记 `<!-- vibe-ack -->`，在 `handle_event` 入口检测若 comment body 含此 sentinel 则直接 return。
2. **作者过滤**: 从 event payload 的 `comment.user.login` 读取评论者，若等于 bot/viewer 配置的用户名（`config.bot_username`）则跳过。（若无 `bot_username` 配置则回退到只靠 sentinel）

**改动范围**:
- `src/vibe3/orchestra/services/comment_reply.py`
  - `handle_event`: 加 sentinel 检测 + 作者检测（early return）
  - `_post_ack`: body 中插入 `<!-- vibe-ack -->` sentinel
- `src/vibe3/orchestra/config.py`（可选）: 若无 `bot_username` 字段可按需添加，默认 `None`

---

### #403: async PR review 写状态到错误分支

**文件**: `src/vibe3/commands/review.py`、`src/vibe3/services/async_execution_service.py`

**根因**: 在 `pr()` 命令中：
```python
branch = get_current_branch() if async_mode and not dry_run else None
```
这里用的是**调用者当前分支**，不是 PR 的 head branch。当用户从非 PR 对应 worktree 触发 `vibe3 review pr N --async` 时，async 生命周期事件会写到错误的 flow state 下。

**修复思路**:
1. 在 `build_pr_review` 之后，若 `async_mode=True`，通过 GitHub API（已有 `GitHubClient`）获取 PR 的 head branch。
2. 将 PR head branch 传给 `execute_review` 作为 `branch` 参数。
3. 若获取失败（API 错误），refuse async 并返回友好错误信息。

**改动范围**:
- `src/vibe3/commands/review.py`
  - `pr()` 函数：async mode 时先解析 PR head branch，再传 `branch`
- `src/vibe3/agents/review_agent.py`（可能）: 若 `build_pr_review` 已返回 head branch 信息则直接复用，无需再次 API 调用
- `src/vibe3/services/async_execution_service.py`: 无需改动（branch 注入正确即可）

---

### #404: review parser 失败开放（缺 VERDICT 时默认 PASS）

**文件**: `src/vibe3/agents/review_parser.py`

**根因**:
```python
verdict = verdict_match.group(1).upper() if verdict_match else "PASS"
```
当 agent 输出截断、为空或格式错误时，`verdict_match` 为 None，直接 fallback 到 `"PASS"`，产生假绿结果。

**修复思路**:
- 无 verdict 时抛出 `ReviewParserError`，区分两种情况：
  - `raw` 完全为空 → `"Empty or missing review output"`
  - `raw` 有内容但无 VERDICT → `"No parseable VERDICT found in output"`
- 调用方（`review_agent.py` 或上层）catch `ReviewParserError` 后映射成 `UNKNOWN` 或 `ERROR` verdict，不允许进入正常 PASS 路径。

**改动范围**:
- `src/vibe3/agents/review_parser.py`
  - `parse_codex_review`: 移除 fallback to PASS，改为 raise `ReviewParserError`
- `src/vibe3/agents/review_agent.py`（或 `review.py`）: catch `ReviewParserError`，verdict = `"ERROR"`，emit 明确失败信息

---

## 实现顺序

```
Phase 1 (独立，无依赖)
  - Fix #401/#402: comment_reply.py sentinel + author filter
  - Fix #404: review_parser.py fail closed

Phase 2 (依赖 Phase 1 review_agent 接口稳定)
  - Fix #403: review.py async branch resolution
```

---

## 测试覆盖

### #401/#402
- `tests/vibe3/orchestra/test_comment_reply.py`
  - `test_ignores_own_ack_by_sentinel`: 含 sentinel 的 comment → 不 post
  - `test_ignores_bot_author`: comment.user.login == bot → 不 post
  - `test_replies_to_valid_mention`: 正常 mention → post ack 且含 sentinel

### #403
- `tests/vibe3/commands/test_review.py`
  - `test_async_pr_uses_pr_head_branch`: 确认 branch 参数来自 PR head，不是当前分支
  - `test_async_pr_refuses_when_head_fetch_fails`: API 错误时 refuse 而不静默

### #404
- `tests/vibe3/agents/test_review_parser.py`
  - `test_empty_output_raises`: 空 raw → ReviewParserError
  - `test_no_verdict_raises`: 有内容但无 VERDICT → ReviewParserError
  - `test_valid_verdict_pass/major/block`: 正常解析不受影响

---

## 验收标准

- [ ] `uv run ruff check src` 通过
- [ ] `uv run mypy src` 通过
- [ ] 上述新增测试全部绿
- [ ] `uv run pytest tests/vibe3 -q` 全量通过
- [ ] PR closes #401 #402 #403 #404
