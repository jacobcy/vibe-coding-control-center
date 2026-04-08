---
name: vibe-rules
description: Use when rules files change, when checking for duplicate or conflicting rules across ~/.claude/rules/common/, .claude/rules/, .agent/rules/, and CLAUDE.md, or when an agent has created new rules that may overlap with existing ones. Do not use for skill authoring or flow governance.
---

# Vibe Rules - Rules 冲突检测与清理

> 维护 Claude Code rules 分层体系，检测重复和冲突，提供清理建议。

## Rules 分层体系

```yaml
# Rules 分层体系（优先级从低到高）

tier_1_global:
  path: ~/.claude/rules/common/
  description: 全局规则（外部导入，如 ECC）
  characteristics:
    - 适用所有项目
    - 项目中不应重复，除非项目规定不一致
  priority: 基础层

tier_2_project:
  path: .claude/rules/
  description: 项目规则（可能由 agents 创建）
  characteristics:
    - 除非确有必要，否则应该清理
    - 覆盖全局规则
  priority: 中等

tier_3_claudemd:
  path: CLAUDE.md
  description: 项目最高标准
  characteristics:
    - 项目级硬规则和上下文
    - 不应重复全局已规定的 rules
    - 引用 .agent/rules/ 的权威来源
  priority: 最高

tier_4_compressed:
  path: .agent/rules/
  description: 压缩规则（详细定义）
  characteristics:
    - 压缩 CLAUDE.md 不常驻的详细规则
    - Agent 按需读取，通过引用
    - 必须在 CLAUDE.md 中引用
  priority: 详细定义层
```

## 使用方式

### 1. 快速检查

```bash
/vibe-rules check
```

检查当前项目的 rules 冲突和重复。

### 2. 生成报告

```bash
/vibe-rules report
```

生成详细的 rules 分析报告，包括：

- 分层结构统计
- 重复内容检测
- 冲突配置识别
- 清理建议

### 3. 自动清理

```bash
/vibe-rules clean [--dry-run]
```

自动清理重复和冲突的 rules。

- `--dry-run`: 只显示将要执行的操作，不实际删除

### 4. 交互式修复

```bash
/vibe-rules fix
```

交互式修复配置冲突（如 pyproject.toml 与 rules 不一致）。

## 执行步骤

### Step 1: 扫描所有 rules 文件

```bash
# 全局规则
ls ~/.claude/rules/common/*.md 2>/dev/null

# 项目规则
ls .claude/rules/*.md 2>/dev/null

# 项目压缩规则
ls .agent/rules/*.md 2>/dev/null

# CLAUDE.md 引用
grep -E '\.agent/rules/.*\.md|\.claude/rules/.*\.md' CLAUDE.md
```

### Step 2: 检测重复内容

**检测同名文件**：

```bash
comm -12 <(ls ~/.claude/rules/common/) <(ls .claude/rules/)
```

**检测内容重复**：

- 使用 `diff` 对比同名文件
- 使用 `grep` 查找相似内容
- 使用文本相似度算法（如 difflib）

### Step 3: 识别配置冲突

**检查点**：

- [ ] Python 版本要求是否一致
- [ ] mypy 配置是否一致
- [ ] black/ruff 行宽是否一致
- [ ] 测试框架要求是否一致
- [ ] uv 使用是否一致

**验证方法**：

```bash
# 对比 pyproject.toml 和 rules 中的配置
grep "line-length" pyproject.toml
grep "line-length" .agent/rules/python-standards.md

grep "mypy" pyproject.toml
grep "mypy" .agent/rules/python-standards.md
```

### Step 4: 分析必要性

**判断标准**：

#### 全局规则（~/.claude/rules/common/）

- ✅ 保留：通用编码原则、git 工作流、性能优化
- ❌ 删除：使用频率低的内容

#### 项目规则（.claude/rules/）

- ✅ 保留：项目特定的扩展（如 Python 特定实践）
- ❌ 删除：与全局完全相同的内容
- ❌ 删除：与 .agent/rules/ 重复的内容

#### 项目压缩规则（.agent/rules/）

- ✅ 保留：详细的技术标准、架构定义
- ✅ 必须在 CLAUDE.md 中引用
- ❌ 删除：未引用的孤立规则

#### CLAUDE.md

- ✅ 保留：项目硬规则、最小不可协商规则
- ❌ 删除：重复全局规则的内容
- ✅ 必须引用 .agent/rules/ 作为详细定义

### Step 5: 生成清理建议

**输出格式**：

````markdown
# Vibe Rules 分析报告

生成时间: {timestamp}

## 统计信息

| 层级     | 文件数 | 行数 | Token 估算 |
| -------- | ------ | ---- | ---------- |
| 全局规则 | {n}    | {n}  | {n}        |
| 项目规则 | {n}    | {n}  | {n}        |
| 压缩规则 | {n}    | {n}  | {n}        |
| **总计** | {n}    | {n}  | {n}        |

## 重复检测

### 1. 同名文件重复

| 文件名          | 全局 | 项目 | 建议                   |
| --------------- | ---- | ---- | ---------------------- |
| coding-style.md | ✅   | ✅   | 删除项目规则，使用全局 |

### 2. 内容重复

| 项目文件                 | 重复源                           | 重复行数 | 建议               |
| ------------------------ | -------------------------------- | -------- | ------------------ |
| .claude/rules/testing.md | .agent/rules/python-standards.md | 39 行    | 删除，使用权威来源 |

## 配置冲突

### ⚠️ mypy 配置不一致

- `.agent/rules/python-standards.md`: `strict = true`
- `pyproject.toml`: 未设置 `strict`
- **建议**: 在 pyproject.toml 中添加 `strict = true`

## 清理建议

### 删除文件（节省 ~{n} tokens）

```bash
# 项目规则与全局重复
rm .claude/rules/coding-style.md

# 项目规则与压缩规则重复
rm .claude/rules/testing.md
rm .claude/rules/patterns.md
rm .claude/rules/hooks.md
```
````

### 修复配置

```bash
# 更新 pyproject.toml
# 添加 strict = true 到 [tool.mypy]
```

## 验证步骤

清理后运行：

```bash
# 检查 mypy
uv run mypy src/vibe3

# 检查 black
uv run black --check src/

# 检查 ruff
uv run ruff check src/
```

````

## 清理策略

### 策略 A：完全删除重复（推荐）

**适用场景**：权威来源明确定义

**操作**：
1. 删除 `.claude/rules/` 中与 `.agent/rules/` 重复的文件
2. 删除 `.claude/rules/` 中与全局完全相同的文件
3. 保留项目特定的扩展（如 security.md）

**优点**：
- 单一事实来源
- 无维护负担
- 节省 token

### 策略 B：精简为引用（备选）

**适用场景**：需要快速提醒

**操作**：
```markdown
---
paths: ["**/*.py"]
---
# Python 编码提醒

详见权威标准：[.agent/rules/python-standards.md](../../.agent/rules/python-standards.md)

## 快速检查清单
- Python >= 3.10
- 类型注解必须完整
````

**优点**：

- 保留提醒
- 避免完全丢失

### 策略 C：保留项目特定扩展

**适用场景**：项目有特殊要求

**操作**：

- 只保留项目特定的内容
- 删除与全局/权威来源重复的部分

**示例**：

```markdown
---
paths: ["**/*.py"]
---

# Python 项目特定要求

> 扩展 [.agent/rules/python-standards.md](../../.agent/rules/python-standards.md)

## 本项目特有

- 使用 direnv（不使用 dotenv）
- 使用 loguru（不使用 print）
- pre-commit 配置见 .pre-commit-config.yaml
```

## 最佳实践

### ✅ DO

1. **保持分层清晰**
   - 全局规则：通用原则
   - 项目规则：特定扩展
   - 压缩规则：详细定义
   - CLAUDE.md：硬规则 + 引用

2. **单一事实来源**
   - 每个规定只在一个地方定义
   - 其他地方通过引用

3. **定期清理**
   - 每周运行 `/vibe-rules check`
   - Agent 创建 rules 后立即检查

4. **配置一致性**
   - rules 中的配置必须与实际配置文件一致
   - 定期验证（pre-commit + CI）

### ❌ DON'T

1. **不要重复**
   - 不要在多个地方定义相同规则
   - 不要复制粘贴全局规则

2. **不要孤立规则**
   - .agent/rules/ 必须在 CLAUDE.md 中引用
   - 未引用的规则应删除

3. **不要忽略冲突**
   - 配置冲突必须修复
   - 版本不一致必须同步

4. **不要过度维护**
   - 能用 skill 解决的不写规则
   - 使用频率低的转为 skill

## 集成建议

### 1. Pre-commit Hook

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: vibe-rules-check
      name: Vibe Rules Check
      entry: /vibe-rules check
      language: system
      pass_filenames: false
      files: \.claude/rules/|\.agent/rules/|CLAUDE\.md$
```

### 2. CI 检查

```yaml
# .github/workflows/rules-check.yml
name: Rules Consistency Check
on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Check rules consistency
        run: |
          # 检查同名文件
          if comm -12 <(ls ~/.claude/rules/common/) <(ls .claude/rules/); then
            echo "❌ Found duplicate rules files"
            exit 1
          fi

          # 检查 CLAUDE.md 引用
          if ! grep -q "\.agent/rules/python-standards\.md" CLAUDE.md; then
            echo "❌ Missing reference to .agent/rules/python-standards.md"
            exit 1
          fi
```

### 3. 定期提醒

```bash
# 使用 crontab 或 GitHub Actions schedule
# 每周一提醒检查 rules
/vibe-rules check --report > .agent/reports/rules-report.md
```

## 常见问题

### Q1: Agent 自动创建的 rules 要保留吗？

**答**：评估必要性：

- ✅ 保留：项目特定、无重复、有实际作用
- ❌ 删除：与全局/权威来源重复、无实际作用

### Q2: 全局规则和项目规则冲突怎么办？

**答**：项目规则优先级更高：

1. 评估是否真的需要不同的规定
2. 如果需要，保留项目规则并添加说明
3. 如果不需要，删除项目规则使用全局

### Q3: 如何判断一个 rule 是否必要？

**答**：判断标准：

1. 是否被引用或使用？
2. 是否定义了项目特定的要求？
3. 是否比现有规则更详细或更合适？
4. 删除后是否会影响开发效率？

### Q4: .agent/rules/ 和 .claude/rules/ 的区别？

**答**：

- `.agent/rules/`: 权威定义，详细标准，按需读取
- `.claude/rules/`: 快速提醒，项目特定扩展，常驻上下文

理想情况：`.claude/rules/` 只保留项目特定扩展，其他引用 `.agent/rules/`

## 相关文档

- [docs/standards/v3/skill-standard.md](../../docs/standards/v3/skill-standard.md) - Skill 结构规范
- [CLAUDE.md](../../CLAUDE.md) - 项目最高标准
- [SOUL.md](../../SOUL.md) - 项目宪法
- [docs/standards/glossary.md](../../docs/standards/glossary.md) - 术语真源
