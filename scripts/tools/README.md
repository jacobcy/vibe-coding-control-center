# GitHub 标签工具

本目录包含用于管理 GitHub Issue 和 PR 标签的工具脚本。

## 可用脚本

### `create-labels.sh`

创建 GitHub 标签体系。

**使用方法**：

```bash
# 确保已安装并登录 GitHub CLI
gh auth status

# 运行脚本创建标签
./scripts/tools/create-labels.sh
```

**前置条件**：
- 已安装 [GitHub CLI](https://cli.github.com/)
- 已运行 `gh auth login` 登录

**标签体系**：

详见 `docs/standards/github-labels-standard.md`

---

## 自动标签

### GitHub Actions 自动标签

项目配置了 GitHub Actions 自动标签功能（`.github/workflows/label.yml`）：

- **触发时机**：PR 创建或更新时
- **配置文件**：`.github/labeler.yml`
- **自动规则**：
  - 根据分支名添加类型标签
  - 根据文件路径添加范围和组件标签

### 手动添加标签

如果需要手动添加标签：

```bash
# 查看当前 PR
gh pr view <pr-number>

# 添加标签
gh pr edit <pr-number> --add-label "type/feature,scope/python,status/ready-for-review"

# 移除标签
gh pr edit <pr-number> --remove-label "status/wip"
```

---

## 标签最佳实践

### ✅ 推荐

1. **每个 Issue/PR 至少有一个类型标签**
2. **优先级标签帮助排定工作顺序**
3. **范围标签帮助快速定位改动影响**
4. **状态标签帮助跟踪工作进度**

### ❌ 避免

1. **不要创建过多标签** - 保持精简
2. **不要滥用高优先级标签** - 仅用于真正紧急的事项
3. **不要忽略标签** - 标签是项目管理的重要工具

---

**相关文档**：
- [docs/standards/github-labels-standard.md](../../docs/standards/github-labels-standard.md) - 标签规范
- [skills/vibe-commit/SKILL.md](../../skills/vibe-commit/SKILL.md) - 提交流程