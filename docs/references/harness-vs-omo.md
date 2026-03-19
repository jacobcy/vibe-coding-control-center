# harness vs omo 技能对比

生成时间: 2026-03-18

## 核心定位

### harness - 长期运行框架
**关注点**: 跨会话的任务执行、状态持久化、失败恢复

### omo - 多代理编排器
**关注点**: 单会话内的代理协作、工作流路由

---

## 详细对比

| 维度 | harness | omo |
|------|---------|-----|
| **时间跨度** | 多个会话（跨上下文窗口） | 单个会话 |
| **核心机制** | 进度文件持久化 | 代理间上下文传递 |
| **失败恢复** | 自动 checkpoint + git rollback | 重新路由到其他代理 |
| **任务管理** | 结构化任务列表 + 依赖管理 | 按需路由代理 |
| **执行模式** | Infinite Loop Protocol | Routing Signals |
| **适用场景** | 长期项目、多步骤任务 | 代码分析、bug 修复、功能开发 |

---

## harness 深度解析

### 核心特性

1. **跨会话持久化**
   - `harness-progress.txt` - 所有操作的追加日志
   - `harness-tasks.json` - 结构化任务状态
   - 会话重启时能完全恢复上下文

2. **自动失败恢复**
   ```
   任务失败 → git reset --hard <started_at_commit> → 重试
   ```

3. **任务依赖管理**
   ```json
   {
     "id": "task-003",
     "depends_on": ["task-001", "task-002"],
     "status": "pending"
   }
   ```

4. **并发控制**
   - 独占模式（默认）：单 agent 执行
   - 并发模式：多 agent 通过 lock + lease 协作

### 使用场景

```bash
# 初始化项目
/harness init /path/to/project

# 启动无限循环
/harness run

# 查看进度
/harness status

# 添加任务
/harness add "实现用户认证"
```

### 典型工作流

```
Session 1:
  [开始 task-001] → [checkpoint 1/3] → [checkpoint 2/3]
  → [上下文窗口满，session 结束]

Session 2:
  [读取 progress 文件] → [恢复 task-001] → [checkpoint 3/3]
  → [验证通过] → [完成 task-001]
  → [开始 task-002] → ...
```

---

## omo 深度解析

### 核心特性

1. **路由优先**
   - 不是固定的 `explore → oracle → develop` 流水线
   - 根据信号动态选择代理

2. **代理选择信号**

   | 信号 | 代理 |
   |------|------|
   | 代码位置/行为不明 | `explore` |
   | 外部库/API 使用不明 | `librarian` |
   | 高风险变更 | `oracle` |
   | 需要实现代码 | `develop` |

3. **跳过启发式**
   - 用户提供了准确位置 → 跳过 `explore`
   - 低风险本地修改 → 跳过 `oracle`
   - 只需要分析 → 不调用实现代理

4. **上下文传递**
   ```bash
   # 每个代理都接收完整上下文
   codeagent-wrapper --agent develop - /path/to/project <<'EOF'
   ## Original User Request
   <原始请求>

   ## Context Pack
   - Explore output: <...>
   - Librarian output: <...>
   - Oracle output: <...>

   ## Current Task
   <具体任务>

   ## Acceptance Criteria
   <完成条件>
   EOF
   ```

### 使用场景

```bash
# 简单修复（位置已知，低风险）
/omo fix type error at src/foo.ts:123
→ 直接调用 develop

# Bug 修复（位置未知）
/omo analyze and fix this bug
→ explore → develop

# 跨模块重构（高风险）
/omo refactor auth system
→ explore → oracle → develop

# 外部库集成
/omo add feature X using library Y
→ explore + librarian (并行) → oracle → develop
```

---

## 实际案例对比

### 案例 1: 修复一个类型错误

**使用 harness**:
```
1. 创建任务 "修复类型错误"
2. 定义验证命令: npm test -- --testPathPattern=foo
3. 运行 harness run
4. 如果失败，自动 rollback 并重试
5. 适用于：需要多次尝试的复杂修复
```

**使用 omo**:
```
1. /omo fix type error at src/foo.ts:123
2. 直接调用 develop 代理
3. 在单个会话内完成
4. 适用于：简单的一次性修复
```

### 案例 2: 大型功能开发

**使用 harness**:
```
Session 1: 实现核心功能
Session 2: 添加测试
Session 3: 修复测试失败
Session 4: 代码审查反馈
...
适用于：需要多个会话的长期项目
```

**使用 omo**:
```
Session 1:
  /omo implement feature X
  → explore (理解代码库)
  → oracle (设计方案)
  → develop (实现)
适用于：单个会话内能完成的功能
```

### 案例 3: 多文件重构

**使用 harness**:
```
1. 定义多个任务，设置依赖关系
   task-001: 重构数据层
   task-002: 重构业务层 (depends_on: task-001)
   task-003: 重构 API 层 (depends_on: task-002)

2. harness run 自动处理依赖顺序
3. 每个任务失败都能独立 rollback
4. 适用于：需要分阶段的大型重构
```

**使用 omo**:
```
/omo refactor data/business/API layers
→ explore (分析影响范围)
→ oracle (评估风险，设计方案)
→ develop (一次性实现)
适用于：单个会话内能完成的跨文件修改
```

---

## 选择建议

### 使用 harness 当：

- ✅ 任务需要多个会话才能完成
- ✅ 需要结构化的进度跟踪
- ✅ 任务有复杂的依赖关系
- ✅ 需要自动失败恢复和重试
- ✅ 多个 agent 需要协作完成同一组任务

### 使用 omo 当：

- ✅ 单个会话内能完成任务
- ✅ 需要灵活的代理协作
- ✅ 任务类型明确（bug/feature/refactor）
- ✅ 不需要复杂的进度持久化
- ✅ 想要快速完成一次性任务

---

## 组合使用

两者可以结合使用：

```bash
# 1. 使用 harness 管理长期项目
/harness init /path/to/project

# 2. 添加任务
/harness add "实现用户认证系统"

# 3. 在 harness session 中使用 omo 处理具体任务
/omo implement user authentication
→ omo 编排代理完成单个任务

# 4. harness 记录进度并管理下一个任务
```

---

## 核心区别总结

| 特性 | harness | omo |
|------|---------|-----|
| **会话模型** | 多会话持久化 | 单会话 |
| **状态管理** | 文件持久化 | 内存传递 |
| **失败处理** | checkpoint + rollback | 重新路由 |
| **代理选择** | 固定任务执行 | 动态路由信号 |
| **适用规模** | 长期、多步骤项目 | 快速、单次任务 |
| **学习曲线** | 较高（需要理解协议） | 较低（自动路由） |

---

## 常见误区

### ❌ 错误理解

- "harness 和 omo 都是多代理系统，功能重复"
- "只需要学一个就够了"

### ✅ 正确理解

- **harness** = 会话管理框架（时间维度）
- **omo** = 代理编排器（空间维度）
- 两者互补，可以组合使用

---

生成时间: 2026-03-18