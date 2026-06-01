# [DEPRECATED] Vibe 3.0 User Guide

⚠️ **本文档已废弃。请立即前往 V3 官方命令标准：**

👉 **[docs/standards/v3/command-standard.md](v3/command-standard.md)** 👈

---

## 📖 现行真源 (Current Truth)

所有 Vibe 3.0 操作指南与命令规范请以上述文档为准。本文件仅保留为历史兼容路径，不再承载正文。

**项目全局导航与 Agent 协作入口：**

👉 **[AGENTS.md](../../AGENTS.md)**

---

### V3 推荐操作模型 (Quick Reference)

- **Branch 管理**：直接使用 `git` (如 `git checkout -b <name>`)
- **Issue/PR 操作**：直接使用 `gh` (如 `gh issue view`, `gh pr create`)
- **Flow 注册**：`vibe3 flow update` (幂等同步)
- **Task 绑定**：`vibe3 flow bind <issue_number>`
- **状态核查**：`vibe3 flow show` (当前现场) 或 `vibe3 flow status` (全局面板)
- **执行任务**：`vibe3 task show`
- **协作交接**：`vibe3 handoff show` / `vibe3 handoff append`
