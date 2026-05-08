[manager] Review 已通过，进入 merge-ready 阶段

## 审核结果确认

**Verdict**: PASS
**Audit Ref**: docs/reports/issue-556-audit-report-retry.md
**Commit**: 988eb47 "refactor(events): 清理事件系统向后兼容别名"

### 质量审查

✅ **代码质量**
- 9 个文件修改，20 insertions(+), 124 deletions(-)
- 净删除 58 行代码（符合 tech-debt 清理目标）
- 无向后兼容别名残留
- 测试通过率 12/12
- 类型检查成功
- Lint 检查通过

✅ **Review 可信度**
- Reviewer 详细验证了每个文件变更
- 确认无旧名称引用残留
- 评估了 breaking change 影响（内部仅限）
- 提供了完整的 verification 结果

✅ **Baseline 变化**
- 5 个文件修改，无新增/删除文件
- 3 个模块受影响
- LOC delta: -58（符合预期）
- 依赖项无变化

## Executor 发布指令

### 1. 创建 Pull Request

```bash
gh pr create --title "refactor(events): 清理事件系统向后兼容别名" --body "$(cat <<'EOF'
## Summary

移除所有向后兼容别名，统一使用新的 `*DispatchIntent` 事件名称。

### 变更内容

- 删除事件别名定义（`ManagerDispatched` 等 4 个）
- 更新事件导出和 `EVENT_TYPES` 注册表
- 移除处理器中的双重订阅逻辑
- 更新 UI 时间轴显示映射
- 更新测试和文档

### 验证结果

- ✅ 测试: 12/12 passed
- ✅ 类型检查: Success (274 source files)
- ✅ Lint: All checks passed
- ✅ 无旧名称引用残留

### Breaking Change

内部仅限，事件总线非公开 API。外部工具不会受到影响。

Closes #556

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 2. 验证 PR 创建成功

```bash
gh pr view --json number,state,title
```

### 3. 等待 CI 检查完成

```bash
gh pr checks <pr-number>
```

## 风险与关注点

### 低风险
- ✅ 所有测试通过
- ✅ 类型检查通过
- ✅ Lint 通过
- ✅ Breaking change 仅影响内部代码
- ✅ 无外部 API 影响

### 需要注意
- 确保 PR 标题和描述清晰说明变更范围
- PR 创建后检查 CI 是否正常通过
- 如有 CI 失败，需立即修复

## 下一步

1. Executor 创建 PR
2. 等待 CI 检查
3. Manager 最终审核 PR 质量
4. 进入 `state/done`
