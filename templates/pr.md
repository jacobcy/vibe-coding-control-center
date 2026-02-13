# {FEATURE_NAME}

## 概述

_一句话描述这个 PR 的目的。_

**相关 Issue**: #{ISSUE_NUMBER} (如果有)
**PRD 文档**: `{PRD_PATH}`
**技术规格**: `{SPEC_PATH}`

## 变更内容

### 新增

- 新增文件 `path/to/file.sh` - 功能说明
- 新增命令 `vibe command` - 用途说明

### 修改

- 修改 `lib/module.sh` - 优化逻辑
- 更新 `docs/guide.md` - 补充文档

### 删除

- 删除废弃命令 `old-command`
- 移除过时文件 `deprecated.sh`

## 变更摘要 | 测试说明 | 风险点

_示例：新增 vnew 文档说明 | 已运行 docs 校验 | 无破坏性变更_

## 测试验证

### 自动化测试

- ✅ 所有单元测试通过 ({PASS_COUNT}/{TOTAL_COUNT})
- ✅ 集成测试通过
- ✅ 回归测试通过

### 手动测试场景

- [x] 场景1：正常流程验证
- [x] 场景2：边界条件测试
- [x] 场景3：错误处理测试

### 测试命令

```bash
# 运行测试
./tests/test_{FEATURE}.sh

# 预期结果
✅ All tests passed
```

## 破坏性变更

> [!WARNING]
> 如果有破坏性变更，在此说明

- **变更描述**: 简要说明
- **迁移指南**: 如何升级

_(如果没有破坏性变更，删除此节)_

## 检查清单

- [x] 代码遵循项目规范
- [x] 所有测试通过
- [x] 文档已更新
- [x] CHANGELOG.md 已更新
- [x] 无调试代码残留
- [x] 代码已自我审核

## 截图/演示

_(如果是 UI 变更或命令行输出变更，添加截图)_

```bash
$ vibe flow start example
🚀 Starting new feature: example
✅ Created worktree: wt-claude-example
```

## 相关链接

- PRD: `docs/prds/{FEATURE}.md`
- Spec: `docs/specs/{FEATURE}-spec.md`
- Tests: `tests/test_{FEATURE}.sh`

---

**Agent**: {AGENT}
**Created**: {TIMESTAMP}
