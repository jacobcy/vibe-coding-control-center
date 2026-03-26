# Agent 工作流规范

> **文档定位**：定义如何使用 AI Agent（通过 `vibe3 run`）执行开发任务
> **适用范围**：所有需要 AI 辅助的开发工作
> **权威性**：本标准为 agent 工作流的权威依据

---

## 概述

Vibe Center 通过 `vibe3 run` 命令集成 codeagent-wrapper，支持 AI Agent 执行开发任务。Agent 工作流适用于：

- 代码实现（根据 plan 执行）
- Bug 修复
- 代码重构
- 测试编写
- 文档生成

---

## 一、前置条件

### 1.1 环境要求

- ✅ `codeagent-wrapper` 已安装（位于 `~/.claude/bin/codeagent-wrapper`）
- ✅ 已配置 API keys（Claude API 或其他）
- ✅ 已配置 `config/settings.yaml` 中的 `run.agent_config`

### 1.2 配置文件

**settings.yaml 配置示例**：
```yaml
run:
  policy_file: ".agent/rules/run-policy.md"
  common_rules: ".agent/rules/common.md"
  agent_config:
    agent: "develop"  # 默认 agent preset
    timeout_seconds: 600  # 默认超时（秒）
```

**Agent Presets**：
- `develop`: 通用开发 agent（推荐）
- `code-reviewer`: 代码审查 agent
- `planner`: 规划 agent
- 其他自定义 presets（见 `~/.codeagent/models.json`）

---

## 二、工作流程

### 2.1 标准流程

```
Plan → Run → Review → Commit
```

**Step 1: 创建 Plan**

```bash
# 从 issue 创建 plan
vibe3 plan task <issue_number>

# 从 spec 文件创建 plan
vibe3 plan spec --file spec.md

# 从 spec message 创建 plan
vibe3 plan spec --msg "Add dark mode support"
```

**Step 2: 执行 Plan（使用 Agent）**

```bash
# 使用现有 plan 执行
vibe3 run --plan

# 使用自定义 instructions 执行
vibe3 run --instructions "Focus on test coverage"

# 使用指定 agent 执行
vibe3 run --agent planner-pro --plan
```

**Step 3: 审查结果**

```bash
# 查看 handoff 记录
vibe3 handoff show

# 查看 agent 做了哪些修改
git status
git diff

# 运行测试验证
uv run pytest tests/vibe3
```

**Step 4: 提交或调整**

```bash
# 如果结果满意，提交
git add -A
git commit -m "feat: implement dark mode"

# 如果需要调整，继续开发或重新运行
vibe3 run --plan  # 恢复 session 继续工作
```

---

### 2.2 Agent Session 管理

**Session 持久化**：
- Agent 执行会创建 session（存储在 `~/.codeagent/sessions/`）
- Session ID 自动记录到 flow 的 `executor_session_id` 字段
- 可以通过 `vibe3 run --plan` 恢复之前的 session

**查看 Session**：
```bash
# Handoff 显示 session 信息
vibe3 handoff show

# 查看当前 flow 状态
vibe3 flow status
```

**清理 Session**：
```bash
# Agent 会自动管理 session 生命周期
# 也可以手动清理旧日志
codeagent-wrapper cleanup
```

---

## 三、使用场景

### 3.1 新功能开发

**推荐流程**：
```bash
# 1. 创建 flow
vibe3 flow new feature/api-v2

# 2. 绑定 task issue
vibe3 issue bind <issue_number>

# 3. 创建 plan
vibe3 plan task

# 4. 执行 plan（agent 实现）
vibe3 run --plan

# 5. 验证结果
uv run pytest tests/vibe3
vibe3 inspect base origin/main  # 查看改动影响

# 6. 创建 PR
vibe3 pr create
```

---

### 3.2 Bug 修复

**推荐流程**：
```bash
# 1. 创建 flow
vibe3 flow new fix/login-bug

# 2. 绑定 bug issue
vibe3 issue bind <bug_issue_number>

# 3. 使用 instructions 直接描述问题
vibe3 run --instructions "Fix the login timeout bug in auth.py"

# 4. 验证修复
uv run pytest tests/vibe3/services/test_auth.py

# 5. 提交修复
git commit -am "fix: resolve login timeout issue"
```

---

### 3.3 代码重构

**推荐流程**：
```bash
# 1. 创建 flow
vibe3 flow new refactor/split-large-file

# 2. 创建 plan（重构需要详细规划）
vibe3 plan spec --file refactor_plan.md

# 3. 执行 plan
vibe3 run --plan

# 4. 验证重构不影响功能
uv run pytest tests/vibe3
uv run mypy src/vibe3

# 5. 提交重构
git commit -am "refactor: split large file into smaller modules"
```

---

## 四、最佳实践

### 4.1 Prompt 编写

**好的 Prompt**：
```markdown
# Task: Implement User Authentication

## Context
- Current codebase uses session-based auth
- Need to migrate to JWT-based auth
- Must maintain backward compatibility

## Requirements
1. Add JWT token generation
2. Add JWT validation middleware
3. Update existing endpoints to use JWT
4. Add tests for new functionality

## Constraints
- Do NOT change the public API
- Maintain existing test coverage
- Follow existing code patterns
```

**避免的写法**：
```markdown
Fix the auth thing
```

**Prompt 要素**：
- ✅ 明确的任务目标
- ✅ 足够的上下文
- ✅ 具体的要求
- ✅ 清晰的约束条件
- ❌ 模糊的描述
- ❌ 缺少上下文

---

### 4.2 Agent 选择

**默认 Agent**：
- `develop`: 通用开发任务（推荐）

**专用 Agents**：
- `planner`: 架构设计、技术方案
- `code-reviewer`: 代码审查、质量检查
- `test-writer`: 测试用例编写

**高级配置**：
```bash
# 使用 planner-pro（更强的规划能力）
vibe3 run --agent planner-pro --plan

# 使用特定 backend 和 model
vibe3 run --backend claude --model claude-sonnet-4-6 --plan
```

---

### 4.3 Timeout 管理

**默认超时**：600 秒（10 分钟）

**调整超时**：
```bash
# 短任务（bug fix）
vibe3 run --instructions "Fix typo" --timeout 300

# 长任务（大型重构）
vibe3 run --plan --timeout 1800  # 30 分钟
```

**超时处理**：
- Agent 会在超时前保存进度
- Session 仍然可用，可以恢复继续
- 检查 handoff 记录了解已完成的工作

---

### 4.4 错误处理

**常见错误**：

1. **codeagent-wrapper not found**
   ```bash
   # 检查安装
   which codeagent-wrapper
   # 应该输出: /Users/<user>/.claude/bin/codeagent-wrapper
   ```

2. **API Key 未配置**
   ```bash
   # 检查环境变量
   echo $ANTHROPIC_API_KEY

   # 或配置在 ~/.codeagent/config.yaml
   ```

3. **Permission denied**
   ```bash
   # 使用 --skip-permissions（谨慎使用）
   vibe3 run --plan --skip-permissions
   ```

4. **Timeout**
   ```bash
   # 增加超时时间
   vibe3 run --plan --timeout 1800
   ```

---

## 五、质量控制

### 5.1 执行前检查

- ✅ Plan 是否清晰完整
- ✅ 是否有足够的上下文
- ✅ 是否指定了正确的 agent
- ✅ 是否设置了合理的 timeout

### 5.2 执行后验证

- ✅ 查看 handoff 记录，了解 agent 完成了什么
- ✅ 检查代码修改，确认符合预期
- ✅ 运行测试，确保功能正确
- ✅ 运行类型检查和 lint

### 5.3 审查要点

**代码质量**：
- 是否符合代码规范
- 是否有足够的测试
- 是否有清晰的注释
- 是否处理了错误情况

**安全性**：
- 是否有潜在的安全漏洞
- 是否正确处理了用户输入
- 是否有敏感信息泄露

**性能**：
- 是否有性能问题
- 是否有内存泄漏
- 是否有并发问题

---

## 六、限制与注意事项

### 6.1 当前限制

- Agent 在正确的项目目录执行（通过 `cwd` 参数）
- Session 自动持久化到 flow
- Agent 只操作当前 worktree（不会跨 worktree）

### 6.2 安全考虑

**禁止操作**：
- ❌ 不要让 agent 操作生产环境配置
- ❌ 不要让 agent 提交到 main 分支
- ❌ 不要让 agent 推送 force

**推荐做法**：
- ✅ 在 feature branch 上使用 agent
- ✅ 审查 agent 的所有修改
- ✅ 运行完整测试套件验证

---

## 七、故障排查

### 7.1 Agent 无响应

**检查步骤**：
1. 检查 API key 是否正确
2. 检查网络连接
3. 检查 agent logs（`~/.codeagent/logs/`）
4. 尝试减少任务复杂度

### 7.2 Agent 超时

**解决方案**：
1. 增加 timeout 参数
2. 拆分任务为更小的子任务
3. 使用 session 恢复继续执行

### 7.3 代码质量不佳

**改进方法**：
1. 提供更详细的 prompt
2. 使用更强大的 agent（如 `planner-pro`）
3. 提供更多上下文信息
4. 使用 `--instructions` 添加具体要求

---

## 八、参考文档

- [SOUL.md](../../SOUL.md) - 项目宪法
- [quality-control-standard.md](./quality-control-standard.md) - 质量检查标准
- [error-handling.md](./error-handling.md) - 错误处理规范
- [.agent/rules/run-policy.md](../.agent/rules/run-policy.md) - Run 命令策略

---

**文档版本**：v1.0
**最后更新**：2026-03-25
**维护者**：Vibe Center Team
