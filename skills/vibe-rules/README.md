# Vibe Rules - Rules 冲突检测与清理工具

> 维护 Claude Code rules 分层体系，检测重复和冲突，提供清理建议。

## 快速开始

### 1. 检查 Rules 冲突

```bash
./skills/vibe-rules/vibe-rules.sh check
```

输出示例：
```
[INFO] 开始检查 rules 冲突...
[WARNING] 发现同名文件重复：
  - coding-style.md (全局 + 项目)
[WARNING] coding-style.md 可能与 python-standards.md 重复 (关键词重合 83%)
[ERROR] 配置冲突：rules 要求 mypy --strict，但 pyproject.toml 未配置
[SUCCESS] 检查完成！
```

### 2. 生成详细报告

```bash
./skills/vibe-rules/vibe-rules.sh report
```

报告保存到：`.agent/reports/rules-report.md`

### 3. 自动清理重复

```bash
# 预览模式（不实际删除）
./skills/vibe-rules/vibe-rules.sh clean --dry-run

# 实际执行清理
./skills/vibe-rules/vibe-rules.sh clean
```

### 4. 交互式修复

```bash
./skills/vibe-rules/vibe-rules.sh fix
```

## Rules 分层体系

```
Tier 1: ~/.claude/rules/common/ (全局规则)
  ↓ 适用所有项目，外部导入，项目不应重复

Tier 2: .claude/rules/ (项目规则)
  ↓ 可能由 agents 创建，需评估必要性

Tier 3: CLAUDE.md (项目最高标准)
  ↓ 不应重复全局规则，引用 .agent/rules/

Tier 4: .agent/rules/ (压缩规则)
  → 通过引用方式，agent 按需读取
```

## 当前检测结果

运行 `vibe-rules check` 发现：

### ✅ 问题清单

1. **同名文件重复**：
   - `coding-style.md` (全局 + 项目)
   - `patterns.md` (全局 + 项目)

2. **内容重复**：
   - `.claude/rules/coding-style.md` 与 `.agent/rules/python-standards.md` (83% 重合)
   - `.claude/rules/testing.md` 与 `.agent/rules/python-standards.md` (100% 重合)
   - `.claude/rules/patterns.md` 与 `.agent/rules/python-standards.md` (100% 重合)
   - `.claude/rules/hooks.md` 与 `.agent/rules/python-standards.md` (100% 重合)

3. **未引用规则**：
   - `.agent/rules/kiro-integration.md` 未在 CLAUDE.md 中引用

4. **配置冲突**：
   - rules 要求 `mypy --strict`，但 pyproject.toml 未配置

### 💡 推荐操作

#### 删除重复文件（推荐）

```bash
# 这些文件与 .agent/rules/python-standards.md 高度重复
rm .claude/rules/coding-style.md
rm .claude/rules/testing.md
rm .claude/rules/patterns.md
rm .claude/rules/hooks.md
```

#### 修复配置冲突

在 `pyproject.toml` 中添加：

```toml
[tool.mypy]
python_version = "3.10"
strict = true  # 添加这一行
warn_return_any = true
disallow_untyped_defs = true
```

#### 清理未引用规则

评估 `.agent/rules/kiro-integration.md` 是否需要，如果需要则在 CLAUDE.md 中添加引用。

## Token 节省估算

如果执行推荐操作：

| 操作 | 删除文件 | 节省 Token |
|------|---------|-----------|
| 删除重复项目规则 | 4 个文件 | ~2,600 tokens |
| 保留 security.md | 1 个文件 | - |
| **总计** | - | **~2,600 tokens** |

## 集成建议

### 1. Pre-commit Hook

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: vibe-rules-check
      name: Vibe Rules Check
      entry: ./skills/vibe-rules/vibe-rules.sh check
      language: system
      pass_filenames: false
      files: \.claude/rules/|\.agent/rules/|CLAUDE\.md$
```

### 2. 定期检查

```bash
# 每周一运行
crontab -e
# 添加：0 9 * * 1 cd /path/to/project && ./skills/vibe-rules/vibe-rules.sh report
```

## 相关文档

- [SKILL.md](./SKILL.md) - 完整的 skill 文档
- [CLAUDE.md](../../CLAUDE.md) - 项目最高标准
- [SOUL.md](../../SOUL.md) - 项目宪法

## 维护

- **创建时间**: 2026-03-18
- **维护者**: Vibe Team
- **版本**: 1.0.0