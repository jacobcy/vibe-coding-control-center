---
author: Claude Sonnet 4.6
created: 2026-03-03
purpose: V3 Execution Plane 迁移执行计划
related_docs:
  - ./SPEC.md
  - ./PRD.md
  - ../../.agent/rules/execution-plane.md
---

# V3 Execution Plane 迁移执行计划

## 迁移概述

**目标**: 将 V2 aliases 系统升级为 V3 Execution Plane，实现标准化的 worktree/tmux 管理和会话恢复能力。

**原则**: 复用 V2 核心逻辑，不重写执行理念，仅增强和标准化。

## 迁移阶段

### 阶段 1: 基础设施（Week 1）

#### 1.1 目录结构创建
```bash
# 创建执行结果存储
mkdir -p .agent/execution-results
touch .agent/execution-results/.gitkeep

# 创建恢复历史日志
touch .agent/recovery-history.log

# 添加到 .gitignore
echo ".agent/execution-results/*.json" >> .gitignore
echo "!.agent/execution-results/.gitkeep" >> .gitignore
```

#### 1.2 模块文件创建
```bash
# 创建 execution-contract.sh
touch config/aliases/execution-contract.sh
chmod +x config/aliases/execution-contract.sh

# 创建 session-recovery.sh
touch config/aliases/session-recovery.sh
chmod +x config/aliases/session-recovery.sh
```

#### 1.3 验证基础设施
- [ ] `.agent/execution-results/` 目录存在
- [ ] `.agent/recovery-history.log` 文件存在
- [ ] `.gitignore` 已更新
- [ ] 模块文件已创建并可执行

### 阶段 2: Worktree 能力增强（Week 1-2）

#### 2.1 命名验证
```bash
# 在 config/aliases/worktree.sh 添加
_validate_worktree_name()  # 验证命名约定
_generate_conflict_suffix()  # 生成冲突后缀
```

**测试**: `tests/test_worktree_execution_plane.bats`

#### 2.2 自动命名增强
```bash
# 增强 wtnew 命令
- 添加命名验证
- 添加冲突检测
- 添加自动后缀
- 集成执行结果写入
```

**迁移点**: V2 `wtnew` → V3 `wtnew` (向后兼容)

#### 2.3 列表过滤
```bash
# 增强 wtlist 命令
wtlist [owner] [task]  # 按 owner 和 task 过滤
```

**迁移点**: V2 `wtls` → V3 `wtlist` (别名保持兼容)

#### 2.4 清理确认
```bash
# 增强 wtrm 命令
wtrm <worktree> [--force]  # 添加确认提示
```

**迁移点**: V2 `wtrm` → V3 `wtrm` (添加 --force)

#### 2.5 验证命令
```bash
# 新增 wtvalidate 命令
wtvalidate <worktree>  # 验证 worktree 完整性
```

**新能力**: V2 无此命令

#### 2.6 验证清单
- [ ] 命名验证函数工作正常
- [ ] 冲突检测和自动后缀生成
- [ ] wtlist 过滤功能
- [ ] wtrm 确认提示
- [ ] wtvalidate 验证完整性
- [ ] 测试通过

### 阶段 3: Tmux 能力增强（Week 2）

#### 3.1 命名验证
```bash
# 在 config/aliases/tmux.sh 添加
_validate_tmux_session_name()  # 验证命名约定
_parse_session_name()  # 解析 agent 和 task
```

**测试**: `tests/test_tmux_execution_plane.bats`

#### 3.2 自动命名创建
```bash
# 新增 tmnew 命令
tmnew <task-slug> [agent]  # 创建 session 并写入执行结果
```

**新能力**: V2 使用 vtup，V3 提供 tmnew

#### 3.3 自动检测附加
```bash
# 增强 tmattach 命令
tmattach [session]  # 自动检测当前 worktree 的 session
```

**迁移点**: V2 `vt` → V3 `tmattach` (别名保持)

#### 3.4 会话切换
```bash
# 增强 tmswitch 命令
tmswitch <session>  # 带验证的切换
```

**迁移点**: V2 `vtswitch` → V3 `tmswitch`

#### 3.5 会话终止确认
```bash
# 增强 tmkill 命令
tmkill <session> [--force]  # 添加确认提示
```

**迁移点**: V2 `vtkill` → V3 `tmkill`

#### 3.6 会话重命名
```bash
# 新增 tmrename 命令
tmrename <old> <new>  # 重命名并更新执行结果
```

**新能力**: V2 无此命令

#### 3.7 任务上下文列表
```bash
# 增强 tmlist 命令
tmlist  # 显示 agent, task, worktree 信息
```

**迁移点**: V2 `vtls` → V3 `tmlist`

#### 3.8 验证清单
- [ ] 命名验证函数工作正常
- [ ] tmnew 创建并写入执行结果
- [ ] tmattach 自动检测
- [ ] tmswitch 验证切换
- [ ] tmkill 确认提示
- [ ] tmrename 更新执行结果
- [ ] tmlist 显示任务上下文
- [ ] 测试通过

### 阶段 4: 会话恢复能力（Week 2-3）

#### 4.1 恢复命令实现
```bash
# 创建 wtrecover 命令
wtrecover --task-id <id>
wtrecover --worktree <path>
wtrecover --session <name>
```

**新能力**: V2 无此命令

#### 4.2 会话重建逻辑
```bash
# session-recovery.sh 实现
- 查询执行结果
- 检查 worktree 存在性
- 检查 session 存在性
- 自动重建丢失的 session
```

#### 4.3 恢复状态报告
```bash
# 输出格式
SUCCESS: session found and attached
PARTIAL: session recreated
FAILED: worktree missing
```

#### 4.4 恢复历史日志
```bash
# 记录到 .agent/recovery-history.log
timestamp | task_id | worktree | session | status | details
```

#### 4.5 验证清单
- [ ] wtrecover 按三种方式恢复
- [ ] session 丢失时自动重建
- [ ] worktree 丢失时报错
- [ ] 恢复历史正确记录
- [ ] 恢复时间 < 30 秒
- [ ] 测试通过

### 阶段 5: 执行契约实现（Week 3）

#### 5.1 JSON Schema 验证
```bash
# execution-contract.sh 实现
_validate_execution_result()  # 验证 JSON 格式和字段
```

#### 5.2 执行器模式检测
```bash
_get_executor()  # 检测 EXECUTOR 环境变量
```

#### 5.3 写入函数
```bash
write_execution_result()  # 写入 JSON 文件
```

#### 5.4 查询函数
```bash
query_by_task_id()
query_by_worktree()
query_by_session()
```

#### 5.5 更新函数
```bash
update_execution_result()  # 更新字段
```

#### 5.6 清理函数
```bash
cleanup_execution_results()  # 备份并清理
```

#### 5.7 验证清单
- [ ] JSON schema 验证正确
- [ ] 执行器模式检测
- [ ] 写入和查询功能
- [ ] 更新和清理功能
- [ ] 跨 worktree 访问
- [ ] 测试通过

### 阶段 6: OpenClaw Skill 集成（Week 3-4）

#### 6.1 Skill 目录结构
```bash
mkdir -p skills/execution-plane/examples
touch skills/execution-plane/SKILL.md
touch skills/execution-plane/README.md
touch skills/execution-plane/wrappers.sh
```

#### 6.2 Skill 定义
```markdown
# skills/execution-plane/SKILL.md
- System Role
- Overview
- When to Use
- Execution Steps
- Output Format
- What This Skill Does NOT Do
```

#### 6.3 Skill Wrappers
```bash
# wrappers.sh 实现
skill_wtnew()  # EXECUTOR=openclaw wtnew
skill_tmnew()  # EXECUTOR=openclaw tmnew
skill_wtrecover()  # EXECUTOR=openclaw wtrecover
skill_prepare_environment()  # 完整环境准备
skill_cleanup_environment()  # 完整环境清理
```

#### 6.4 文档和示例
```bash
# README.md
- Quick Start
- Common Workflows
- Command Reference
- Troubleshooting

# examples/
human-workflow.sh
openclaw-workflow.sh
```

#### 6.5 验证清单
- [ ] Skill 目录完整
- [ ] SKILL.md 定义完整
- [ ] Wrappers 正确设置 EXECUTOR=openclaw
- [ ] README 清晰完整
- [ ] 示例可运行
- [ ] 测试通过

### 阶段 7: 测试与验证（Week 4）

#### 7.1 单元测试
- `tests/test_worktree_execution_plane.bats`
- `tests/test_tmux_execution_plane.bats`
- `tests/test_execution_contract.bats`
- `tests/test_session_recovery.bats`

#### 7.2 集成测试
- `tests/test_execution_plane_e2e_human.bats`
- `tests/test_execution_plane_e2e_openclaw.bats`
- `tests/test_execution_plane_integration.bats`

#### 7.3 性能测试
- `tests/test_execution_plane_performance.bats`
  - Recovery < 30s
  - Creation < 5s
  - Query < 1s

#### 7.4 压力测试
- `tests/test_execution_plane_stress.bats`
  - 5+ parallel sessions
  - Conflict rate ≈ 0
  - Rapid create/delete

#### 7.5 验证清单
- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 性能测试满足要求
- [ ] 压力测试通过
- [ ] 无回归问题

### 阶段 8: 文档更新（Week 4）

#### 8.1 CLAUDE.md
- [x] 添加 Execution Plane 命令
- [x] 更新目录职责
- [ ] 添加使用示例

#### 8.2 .agent/rules/execution-plane.md
- [x] 命名约定
- [x] 执行模式
- [x] 工作流程规范
- [x] 错误处理
- [x] 性能要求
- [x] 故障排除

#### 8.3 v3/execution-plane/PLAN.md
- [x] 本文件

#### 8.4 迁移指南
- [ ] 创建 `docs/migration/v2-to-v3-execution-plane.md`

#### 8.5 config/aliases/README.md
- [ ] 更新命令参考

#### 8.6 故障排除指南
- [ ] 创建 `docs/troubleshooting/execution-plane.md`

#### 8.7 项目结构文档
- [ ] 更新 `STRUCTURE.md`

### 阶段 9: 代码质量检查（Week 4）

#### 9.1 LOC 检查
```bash
# 检查 lib/ + bin/ <= 1800 行
find lib bin -name "*.sh" -exec wc -l {} + | tail -1
```

#### 9.2 单文件检查
```bash
# 检查每个文件 <= 200 行
find lib bin -name "*.sh" -exec sh -c 'lines=$(wc -l < "$1"); if [ $lines -gt 200 ]; then echo "$1: $lines lines"; fi' _ {} \;
```

#### 9.3 死代码检查
```bash
# 检查未使用的函数
# (手动检查或使用工具)
```

#### 9.4 职责检查
- [ ] 每个文件单一职责
- [ ] 函数清晰单一
- [ ] 无过度抽象

#### 9.5 环境一致性
```bash
bin/vibe check
```

#### 9.6 过度工程化检查
- [ ] 无复杂动态路由
- [ ] 无自研测试框架
- [ ] 无过度抽象层

#### 9.7 合规检查
- [ ] 符合 CLAUDE.md HARD RULES
- [ ] 符合 SOUL.md 原则
- [ ] 符合命名约定

## 迁移风险

### 风险 1: 向后兼容性
**缓解**: 保留 V2 别名（wtls, vt, vtswitch 等）
**验证**: 运行现有脚本，确认别名工作

### 风险 2: 性能退化
**缓解**: 性能测试覆盖所有关键操作
**验证**: 基准测试对比 V2 vs V3

### 风险 3: 命名冲突增加
**缓解**: 自动后缀机制
**验证**: 压力测试 5+ 并发会话

### 风险 4: 执行结果损坏
**缓解**: JSON schema 验证 + 备份机制
**验证**: 损坏场景测试

## 回滚计划

### 回滚触发条件
- 关键功能失败率 > 5%
- 性能退化 > 50%
- 命名冲突率 > 10%

### 回滚步骤
1. 恢复 V2 aliases 文件
2. 移除 execution-contract.sh 和 session-recovery.sh
3. 清理 .agent/execution-results/
4. 更新 CLAUDE.md 移除 V3 命令

### 回滚验证
- V2 命令正常工作
- 无残留文件
- 文档已恢复

## 验收标准

### 功能验收
- [ ] 所有 V3 命令正常工作
- [ ] 所有测试通过
- [ ] 向后兼容性保持
- [ ] 文档完整

### 性能验收
- [ ] Recovery < 30s
- [ ] Creation < 5s
- [ ] Query < 1s
- [ ] Conflict rate ≈ 0

### 质量验收
- [ ] LOC 限制满足
- [ ] 无死代码
- [ ] 职责清晰
- [ ] 合规检查通过

## 迁移完成标志

当以下所有条件满足时，迁移完成：

1. ✅ 所有 9 个阶段完成
2. ✅ 所有验收标准通过
3. ✅ 无阻塞性问题
4. ✅ 文档完整且最新
5. ✅ 团队培训完成
6. ✅ 试运行成功（1 周）

**预计完成时间**: Week 4 结束（2026-03-31）
