# Phase 2 Execution Plan

**定位**: 这是执行器的 Phase 2 施工参考计划，不是标准真源，也不能覆盖已经冻结的设计与计划文档。

**目的**: 在 Phase 1 骨架基础上实现真实的业务逻辑，使 vibe3 成为可用的 3.0 实现

**边界说明**:
- 真正语义真源仍是 `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md`
- 真正实施真源仍是 `docs/plans/2026-03-13-vibe3-parallel-rebuild-plan.md`
- 第三轮顺序执行入口仍是 `docs/v3/plans/README.md`
- 若本文件与上述真源冲突，以上述真源为准
- 本文件只服务于 executor 拆解施工顺序，不应被当作标准、规范或 merge 审查依据

---

## 执行原则

### 核心原则

1. **渐进式实现**: 按阶段顺序实现，每阶段完成后验证
2. **最小实现**: 先实现核心路径，再补充边缘功能
3. **持续测试**: 每个功能实现后立即编写测试
4. **文档同步**: 宯现完成后更新文档状态
5. **范围守恒**: 若当前 task 过大，executor 应先提出拆分异议，而不是自行扩写范围
6. **责任链优先**: 本地只实现 `plan / report / audit` 责任链，不实现 GitHub Project 镜像缓存
7. **一致性检查**: `vibe check` 必须验证本地责任链与远端真源对齐

### 禁止事项

- ❌ 不重构现有 2.x 代码
- ❌ 不修改 `bin/vibe` 默认入口
- ❌ 不实现设计文档外的功能
- ❌ 不跳过测试直接进入下一阶段
- ❌ 不在 task 明显过大时硬做到底
- ❌ 不把 handoff 实现成第二套 issue/task/pr 本地数据库
- ❌ 不把 `.agent/context/task.md` 当成 3.0 主交接物

### Task Size Rule

planner 负责在创建 `flow` 和 `task issue` 时把执行范围拆到合理粒度。

如果 executor 在执行阶段判断当前 task 过大，无法一次安全完成，则应：

1. 停止继续扩面实现
2. 向人类或 planner 明确提出 scope challenge
3. 说明建议按什么维度拆分
4. 建议拆成 sub issue / 子 task
5. 待拆分完成后再继续执行

这条规则的目标是：

- 避免 executor 以“先做完再说”的方式把单个 task 做成大杂烩
- 让 task 粒度继续由 planner / 人类控制
- 保证 `report` 和 `audit` 仍然能对准清晰范围

---

## Execution Phases

### Phase 2.1: Flow Domain Core

**目标**: 实现 flow 域的核心业务逻辑

**范围**:
- `flow show` - 显示当前 flow
- `flow status` - 显示所有活跃 flow
- `flow new` - 创建新 flow (branch)
- `flow switch` - 切换 flow

**实现步骤**:

1. **实现最小 handoff store**
   - 文件: `lib3/flow/state.sh`
   - 功能: 基于 SQLite 的本地 flow 责任链索引
   - 标准: 以 `docs/standards/v3/handoff-store-standard.md` 为准
   - 警告: 仅保存 `branch / task_issue / pr / plan_ref / report_ref / audit_ref / next / blocked_by`
   - 禁止: 写入 task registry、roadmap mirror、PR state mirror、任意自定义 JSON 主存储

2. **实现 flow show**
   - 读取当前 branch
   - 从远端和 handoff store 重建 flow 元数据
   - 格式化输出 (文本/JSON)

3. **实现 flow status**
   - 列出所有 branch
   - 过滤活跃 branch
   - 显示状态表格

4. **实现 flow new**
   - 创建新 branch
   - 初始化最小责任链记录
   - 更新 handoff store

5. **实现 flow switch**
   - 切换 git branch
   - 更新当前 flow handoff 索引

6. **实现 vibe check (flow 基础检查)**
   - 检查当前 branch 是否有对应 flow 责任链
   - 检查 `task_issue / pr / plan_ref` 是否可解析
   - 输出 warning / hard-block 分类

**验证**:
```bash
# 测试命令
bin/vibe3 flow show
bin/vibe3 flow status
bin/vibe3 flow new test-feature
bin/vibe3 flow switch main
bin/vibe3 check
```

**测试文件**: `tests3/flow/flow-core.test.sh`

**预计时间**: 2-3 小时

---

### Phase 2.2: Task Domain Core

**目标**: 实现 task 域的核心业务逻辑

**范围**:
- `task add --repo-issue` - 从 issue 创建 task
- `task show` - 显示 task 详情
- `task list` - 列出所有 task
- `task link` - 链接 issue 到 task

**实现步骤**:

1. **实现 task linkage layer (Python)**
   - 职责: 宬现 task issue / repo issue 关联与责任链引用的最小索引
   - 警告: 不复制 GitHub issue 全量数据，真源仍是 GitHub issue / Project
   - 落地方式: 对 SQLite 的 `flow_issue_links` 做写入和查询，由 Python `store.py` 负责

2. **实现 task add**
   - 读取 GitHub issue
   - 提升为 task issue 或建立 issue link
   - 只写入最小关联索引

3. **实现 task show**
   - 读取远端 issue / project
   - 合并本地责任链 ref
   - 格式化输出

4. **实现 task list**
   - 读取远端 issue / project
   - 过滤和排序
   - 表格输出

5. **实现 task link**
   - 更新本地 issue link 索引
   - 不复制远端 issue 正文

**验证**:
```bash
# 测试命令
bin/vibe3 task add --repo-issue 123 --group feature
bin/vibe3 task show task-123
bin/vibe3 task list
bin/vibe3 task link task-456 --repo-issue 789
```

**测试文件**: `tests3/task/task-core.test.sh`

**预计时间**: 2-3 小时

---

### Phase 2.3: Flow-Task Binding

**目标**: 实现 flow 和 task 的绑定关系

**范围**:
- `flow bind --issue` - 绑定 repo issue
- `flow bind task` - 绑定 task issue

**实现步骤**:

1. **实现 flow bind --issue**
   - 读取当前 flow
   - 添加 issue 到 flow responsibility chain
   - 更新 handoff store

2. **实现 flow bind task**
   - 读取当前 flow
   - 设置 flow.task_issue
   - 更新 handoff store

3. **更新 flow show**
   - 显示绑定的 issue 和 task

**验证**:
```bash
# 测试命令
bin/vibe3 flow bind --issue 123
bin/vibe3 flow bind task 456
bin/vibe3 flow show
```

**测试文件**: `tests3/flow/flow-task-binding.test.sh`

**预计时间**: 1-2 小时

---

### Phase 2.4: PR Domain Core

**目标**: 实现 PR 域的核心业务逻辑

**范围**:
- `pr draft` - 创建 draft PR
- `pr show` - 显示 PR 详情
- `pr ready` - 标记 PR ready
- `pr merge` - 合并 PR

**实现步骤**:

1. **实现 pr draft**
   - 读取当前 flow
   - 创建 GitHub PR (draft)
   - 绑定 task/spec_ref 元数据
   - 更新 handoff store

2. **实现 pr show**
   - 读取 GitHub PR
   - 格式化输出

3. **实现 pr ready**
   - 检查 preflight 条件
   - 根据 group 决定 bump 策略
   - 更新 PR 状态

4. **实现 pr merge**
   - 合并 PR
   - 更新 task 状态
   - 更新 handoff store

**验证**:
```bash
# 测试命令
bin/vibe3 pr draft --task 123 --spec-ref docs/plans/test.md
bin/vibe3 pr show
bin/vibe3 pr ready
bin/vibe3 pr merge
```

**测试文件**: `tests3/pr/pr-core.test.sh`

**预计时间**: 3-4 小时

---

### Phase 2.5: Advanced Features

**目标**: 宬现高级功能

**范围**:
- `flow freeze --by` - 冻结 flow
- `pr review` - PR 审查
- `task update` - 更新 task
- `vibe handoff plan/report/audit`
- Handoff 责任链刷新

**实现步骤**:

1. **实现 flow freeze**
   - 标记 flow 为 frozen
   - 记录 blocking reason
   - 更新 flow cache

2. **实现 pr review**
   - 运行本地 Codex 审查
   - 生成审查报告
   - (可选) 回贴到 PR

3. **实现 task update**
   - 更新 task 字段
   - 写入 handoff store

4. **实现 `vibe handoff` 与责任链刷新**
   - 写入 `plan / report / audit` 的署名与 ref
   - 更新 handoff 固定区块或最小索引
   - 不复制远端业务事实

5. **扩展 `vibe check`**
   - 检查 handoff store 与 GitHub / git 当前现场是否一致
   - 检查 `plan/report/audit` ref 是否存在
   - 提供可修复项与人工处理项分类

**验证**:
```bash
# 测试命令
bin/vibe3 flow freeze --by "#123"
bin/vibe3 pr review --local
bin/vibe3 task update task-123 --status in_progress
bin/vibe3 handoff report --agent codex --model gpt-5.4
```

**测试文件**: `tests3/advanced-features.test.sh`

**预计时间**: 2-3 小时

---

## Testing Strategy

### 单元测试

**每个功能实现后立即编写测试**:

```bash
# 测试文件结构
tests3/
├── flow/
│   ├── flow-core.test.sh
│   └── flow-task-binding.test.sh
├── task/
│   └── task-core.test.sh
├── pr/
│   └── pr-core.test.sh
└── advanced-features.test.sh
```

### 集成测试

**在所有 Phase 2.x 完成后运行**:
- 端到端测试: flow -> task -> pr 链路
- 状态一致性测试
- 错误处理测试

### 回归测试

**确保不破坏 2.x**:
- 运行 `tests/` 中的现有测试
- 确认 `bin/vibe` 仍然指向 2.x

---

## Documentation Updates

### 需要更新的文档

1. **实现状态文档**
   - 在 `docs/v3/01-command-and-skeleton.md` 等文档中标记已实现的功能
   - 从 "Not implemented" 改为 "Implemented"

2. **验证报告更新**
   - 更新 `docs/v3/01-verification-report.md`
   - 更新 `docs/v3/02-04-verification-report.md`
   - 添加实现证据

3. **用户文档**
   - 创建 `docs/v3/USER_GUIDE.md`
   - 说明如何使用已实现的功能

---

## Success Criteria

Phase 2 被认为成功完成，当且仅当:

- [ ] **所有核心功能实现**: flow/task/pr 核心命令可用
- [ ] **所有测试通过**: 单元测试 + 集成测试
- [ ] **文档完整**: 实现状态、用户指南更新
- [ ] **无破坏性变更**: 2.x 仍然正常工作
- [ ] **性能可接受**: 命令响应时间 < 1s
- [ ] **错误处理完善**: 所有错误情况都有清晰提示

---

## Rollback Plan

如果 Phase 2 实现出现问题:

1. **立即停止**: 不要继续实现新功能
2. **回滚代码**:
   ```bash
   git revert <problematic-commit>
   ```
3. **分析问题**: 记录问题原因
4. **重新规划**: 调整 Phase 2 计划
5. **重新执行**: 从 Phase 2.1 开始

---

## Timeline

**总预计时间**: 10-15 小时

- Phase 2.1: 2-3 小时
- Phase 2.2: 2-3 小时
- Phase 2.3: 1-2 小时
- Phase 2.4: 3-4 小时
- Phase 2.5: 2-3 小时

**建议**: 每完成一个 Phase 2.x 就分组提交一次，便于追踪进度和安全回滚。

---

## Reference

- [docs/v3/README.md](README.md) - Vibe3 主文档
- [docs/v3/phase_1_review_and_apply.md](phase_1_review_and_apply.md) - Phase 1 审核指南
- [docs/standards/v2/command-standard.md](../../standards/v2/command-standard.md) - 命令标准
- [docs/standards/glossary.md](../../standards/glossary.md) - 术语定义
