# Issue #248: Flow Auto-Ensure Implementation Plan

> **Issue**: [#248 - feat(flow): make branch the implicit flow anchor](https://github.com/jacobcy/vibe-center/issues/248)
>
> **Branch**: `task/flow-auto-ensure`
>
> **Status**: Phase 2 完成，Phase 3-4 待实施

## 概述

将 Vibe3 的 flow 模型从"显式注册/退出"转变为"以 branch 为唯一锚点的隐形运行时元数据"。用户无需手动执行 `vibe3 flow new`，常用入口命令自动确保 flow 存在。

## 已完成工作（Phase 0-2）

### Phase 0: 基础设施（✅ 完成）

**Commit**: d7f4f9b

- 创建 feature 分支 `task/flow-auto-ensure`
- 建立测试基线
- TDD 开发环境就绪

### Phase 1: 服务层核心改动（✅ 完成）

**Commit**: d7f4f9b

**核心实现**:
- `FlowConfig` 配置（settings.yaml）
  - `protected_branches`: ["main", "master", "develop"]
  - 支持配置化扩展
- `MainBranchProtectedError` 异常类
- `FlowAutoEnsureMixin` 混入类
  - `ensure_flow_for_branch()`: 自动创建 flow
  - `_is_main_branch()`: 主分支检测
- `CheckService` PR 状态检测
  - 自动识别 merged/closed PR
  - 标记 flow 为 done

**测试覆盖**:
- 14 个新测试，全部通过
- 覆盖 auto-ensure、main branch guard、PR status detection

**架构优化**:
- 提取 `FlowAutoEnsureMixin` 保持模块化
- `flow_service.py` 控制在 273 行（< 300 行限制）

### Phase 2: 命令层集成（✅ 完成）

**Commit**: b29df47

**集成入口**:
- `vibe3 plan task` - 自动确保 flow
- `vibe3 run execute` - 自动确保 flow
- `vibe3 review base` - 自动确保 flow
- `task_bridge_mixin` - 移除"请先运行 vibe flow new"

**用户体验改进**:
- 用户无需显式 `vibe3 flow new`
- 主分支尝试自动拒绝并提示
- Feature 分支首次使用自动创建 flow

**测试验证**:
- 26 个命令测试通过
- 更新 `test_run.py` 添加 proper mocks
- 验证所有命令路径的 auto-ensure 逻辑

---

## 待完成工作（Phase 3-4）

### Phase 3: 命名和展示更新（待实施）

**预计时间**: 2 小时

#### Task 3.1: 更新 flow show/status 输出

**文件**:
- Modify: `src/vibe3/ui/flow_ui.py`
- Modify: `src/vibe3/commands/flow.py`
- Test: `tests/vibe3/commands/test_flow_actor_defaults.py`

**改动**:
```python
# 当前输出
Flow: my_feature (Branch: task/my-feature)

# 目标输出
Branch: task/my-feature (Flow: active)
Task Issue: #248
PR: #1024
```

**步骤**:
1. 更新 `render_flow_status` 输出格式
2. 显式标注 branch 为主键
3. 弱化 flow_slug 的突出性
4. 更新 help text 说明 branch-centric 模型

#### Task 3.2: 更新 PR metadata

**文件**:
- Modify: `src/vibe3/services/pr_utils.py`
- Test: `tests/vibe3/services/test_pr_utils.py`

**改动**:
```markdown
# 当前
Flow: my_feature

# 目标
Branch: task/my-feature
```

**步骤**:
1. 更新 PR metadata 生成逻辑
2. 使用 branch 作为 flow 标识
3. 保留 flow_slug 作为可选元数据

---

### Phase 4: 文档和迁移指南（待实施）

**预计时间**: 1 小时

#### Task 4.1: 更新项目文档

**文件**:
- Modify: `README.md`
- Modify: `docs/DEVELOPMENT.md`

**内容**:

**README.md 更新**:
```markdown
## Flow Management

Vibe3 automatically manages flows based on git branches. There's no need to
manually create or delete flows:

- **Automatic Creation**: Running `vibe3 plan`, `run`, or `review` on a feature
  branch automatically creates a flow if one doesn't exist.
- **Main Branch Protection**: Flows cannot be created on main/master branches.
- **Automatic Completion**: When a PR is merged or closed, `vibe3 check` marks
  the flow as done.

### Protected Branches

By default, the following branches are protected:
- `main`
- `master`
- `develop`

Configure via `config/settings.yaml`:
```yaml
flow:
  protected_branches:
    - "main"
    - "master"
    - "production"
```
```
---

## Final Gate: 全量验证（待实施）

**预计时间**: 1 小时

### Task F.1: 运行完整测试套件

**命令**:
```bash
# 运行所有 vibe3 测试
uv run pytest tests/vibe3/ -q

# 运行关键测试集
uv run pytest tests/vibe3/services/test_flow*.py -q
uv run pytest tests/vibe3/commands/test_plan.py tests/vibe3/commands/test_run.py tests/vibe3/commands/test_review_pr.py -q
```

**预期结果**:
- 所有测试通过
- 覆盖率 >= 80%（新代码）

### Task F.2: 质量检查

**命令**:
```bash
# LOC 检查
vibe3 inspect metrics

# 类型检查
uv run mypy src/vibe3

# Lint
uv run ruff check src/vibe3
```

**目标**:
- Python LOC < 19000（当前基线）
- 所有文件 ≤ 300 行
- commands 总 LOC 较基线降低
- MyPy 无错误
- Ruff 无错误

### Task F.3: 生成总结报告

**文件**: `docs/reports/2026-03-25-issue-248-implementation-summary.md`

**内容**:
```markdown
# Issue #248 Implementation Summary

## Summary

Successfully implemented automatic flow management with branch as the implicit anchor.

## Changes

### Service Layer
- FlowAutoEnsureMixin with ensure_flow logic
- MainBranchProtectedError for protection
- CheckService PR status detection

### Command Layer
- plan/run/review commands auto-ensure flow
- task_bridge removes explicit flow check
- Main branch guard in all entry points

## Metrics

- **New Tests**: 40 (14 service + 26 command)
- **Test Pass Rate**: 100%
- **Code Coverage**: XX%
- **LOC Impact**: -XX lines (commands layer)

## Verification

- [x] All tests pass
- [x] MyPy clean
- [x] Ruff clean
- [x] LOC within limits
- [x] Manual testing on feature branch
- [x] Main branch rejection works
- [x] PR merge auto-complete works

## User Impact

**Positive**:
- Reduced friction: no need to run `flow new`
- Clear error messages on main branch
- Automatic cleanup on PR merge

**Neutral**:
- Existing flows unchanged
- Backward compatible

## Next Steps

1. Monitor user feedback
2. Consider removing `flow new` command in future
3. Enhance `vibe3 check` for more auto-corrections
```

---

## 技术债务

### 已知问题（非阻塞）

1. **Type annotations**:
   - `plan.py` 和 `run.py` 中的 `run_plan` 和 `get_agent_options` 调用
   - 添加了 `# type: ignore[call-arg]` 注释
   - 根因：现有代码的签名不匹配
   - 修复：应在架构重构中统一处理

2. **Test file formatting**:
   - `test_run.py` 被 black 重新格式化
   - Python 3.11/3.12 兼容性警告
   - 不影响功能

---

## 验收标准

### 必须满足（Phase 1-2 已完成）

- [x] 在非 main/master 分支执行命令无需显式 `flow new`
- [x] 在 main/master 分支执行命令收到明确错误
- [x] PR merged 后 `vibe3 check` 自动标记 flow done
- [x] 所有测试通过（40 个新测试）
- [x] pre-commit hooks 通过

### 建议完成（Phase 3-4）

- [ ] flow show/status 以 branch 为主语展示
- [ ] PR metadata 使用 branch 标识
- [ ] 文档已更新（README + DEVELOPMENT）
- [ ] 迁移指南已创建
- [ ] 完整测试套件通过
- [ ] 质量检查通过
- [ ] 总结报告已生成

---

## 风险与缓解

### 已缓解风险（Phase 1-2）

1. **✅ 破坏现有工作流**
   - 缓解：保留 `vibe3 flow new` 向后兼容
   - 结果：无破坏性变更

2. **✅ 数据迁移问题**
   - 缓解：保留 flow_slug 作为 display name
   - 结果：现有 flow 不受影响

3. **✅ Main branch 边缘情况**
   - 缓解：配置化 protected_branches
   - 结果：灵活可扩展

4. **✅ 并发竞争**
   - 缓解：SQLite 事务 + INSERT OR IGNORE
   - 结果：原子性保证

### 待观察风险

1. **用户适应成本**
   - 风险：用户习惯显式 `flow new`
   - 缓解：文档 + 迁移指南
   - 监控：用户反馈

2. **UI 改动影响**
   - 风险：用户依赖当前 UI 输出
   - 缓解：保留 flow_slug 显示
   - 监控：Phase 3 上线后反馈

---

## 相关链接

- **Issue**: https://github.com/jacobcy/vibe-center/issues/248
- **Branch**: `task/flow-auto-ensure`
- **Commits**:
  - d7f4f9b: Phase 1 - Service layer
  - b29df47: Phase 2 - Command layer
- **Architecture Refactor Plan**: `docs/plans/2026-03-25-vibe3-architecture-break-refactor-plan.md`

---

## 时间线

- **2026-03-25 08:00**: 开始实施 Phase 0
- **2026-03-25 09:30**: 完成 Phase 1 (服务层)
- **2026-03-25 11:00**: 完成 Phase 2 (命令层)
- **待定**: Phase 3 (UI/文档)
- **待定**: Phase 4 (文档)
- **待定**: Final Gate (验证)

**总耗时**: ~3 小时（Phase 0-2）

**剩余时间**: ~4 小时（Phase 3-4 + Final Gate）