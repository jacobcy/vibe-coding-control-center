---
task_id: "2026-03-02-command-slash-alignment"
document_type: implementation_plan
title: "Command vs Slash Alignment Plan V2"
author: "Antigravity Agent"
created: "2026-03-02"
last_updated: "2026-03-02"
status: review-ready
---

# Command vs Slash Alignment Plan V2

## 1. 核心变更计划 (Core Changes)

### 📈 规则调整 (Governance)
- **LOC 限制**: 将 `lib/` + `bin/` 的总行数限制从 1200 提升至 **1800 行**，以容纳新增的结构化功能。
- **逻辑下沉与剥离**:
    - **MVC 分离**: Shell 作为数据层 (Model/API)，Skill 作为视图与控制器 (View/Controller)。
    - **逻辑外迁**: 超过 150 行且非核心的数据操作逻辑迁移到 `scripts/`。

### 🔌 Shell API & JSON 接口 (Data APIs)
- **`vibe task list --json`**: 
    - 输出 `registry.json` + `worktrees.json` + `OpenSpec` 状态的合并 JSON。
    - 统一 Skill 的读取事实来源，避免解析格式化字符串。
- **`vibe task update <task-id> [options]`**:
    - 必须支持 `--status`, `--next-step`, `--bind-current`, `--unassign`。
    - 控制 JSON 写入的唯一入口。

### 🔍 诊断命令重组 (Diagnostics)
- **`vibe doctor`**: 
    - 负责环境检查：工具的存在性、版本、环境变量、API Keys 状态。
- **`vibe check`**: 
    - 拆分为 `vibe check json <file>`。
    - **极简主义**: 只校验 `jq` 是否能解析该文件，以及是否包含关键顶层字段 (如 `tasks` 或 `worktrees`)。移除复杂 Schema 逻辑。

### 🏗️ 跨系统兼容 (OpenSpec Integration)
- **不重造轮子**: 直接使用 `openspec status --json` 获取 OpenSpec 变更状态。
- **轻量桥接**: 
    - 在 `scripts/vibe-openspec-bridge.sh` 中调用 `openspec status` 并将其映射为 Vibe 的任务模型。
    - `vibe task list` 时调用此脚本获取外部任务，打上 `[OpenSpec]` 标记。

## 2. 实施细节 (Implementation Details)

### Phase 1: 基础设施重整
1. 修改 `CLAUDE.md` 中的 HARD RULES（LOC 限制）。
2. 将 `lib/check.sh` 重名为 `lib/doctor.sh`，仅保留环境检查逻辑。
3. 创建新的 `lib/check.sh`，仅支持极简 JSON 校验。
4. 移动 `lib/skills_sync.sh` 到 `scripts/skills_sync.sh`。

### Phase 2: 增强 Task API
1. 为 `vibe task list` 补齐 `--json` 选项。
2. 简化 `_vibe_task_collect_openspec_tasks`：
    - 调用 `openspec status --json --change NAME`。
    - 若 `openspec` 未安装，静默跳过或降级。
3. 实现 `vibe task update --unassign <task-id>`（清除 `assigned_worktree`）。

### Phase 3: Help 系统与测试
1. **强制 Help**: 确保所有子命令均有 `-h/--help`。
2. **自动化验证**: 编写 `tests/check_help.sh`，遍历 `bin/vibe` 子命令并检查输出。
3. **Skill 调用示例**: 在 `docs/standards/skill-shell-interface.md` 中为 Skill 提供明确的 Shell 调用文档。

## 3. 对 Skill 的 API 契约示例 (API Contract)

### 任务状态流转
- **/vibe-save/continue**: `vibe task update <task-id> --next-step "Doing something"`
- **/vibe-done**: 
    1. `vibe task update <task-id> --status completed --unassign`
    2. `git flow push` (通过 Shell)

### 环境自检 (Skill 逻辑)
1. 运行 `vibe doctor --json` (如果有) 或 `vibe doctor`。
2. 获取依赖状态。

## 4. 行数预估 (Estimated LOC)

- `lib/task.sh`: ~180 行 (精简逻辑，删除密集代码)
- `lib/doctor.sh`: ~100 行
- `lib/check.sh`: ~40 行
- `lib/flow.sh`: ~150 行
- **总计 lib/**: 预期控制在 **1000-1200 行** 左右，远低于 1800 行预算。

---

## 5. 待办事项 (Todos)

- [ ] 更新 `CLAUDE.md` LOC 限制
- [ ] 重构 `lib/doctor.sh` & `lib/check.sh`
- [ ] 实现 `vibe task list --json`
- [ ] 集成 `openspec status --json`
- [ ] 补齐 Help 信息并编写测试
- [ ] 编写 Skill 接入文档
