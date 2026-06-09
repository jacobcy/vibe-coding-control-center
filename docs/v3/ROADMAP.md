---
title: Vibe 3.0 Development Roadmap
author: Claude Sonnet 4.6
created_at: 2026-03-17
category: roadmap
status: active
version: 1.0
related_docs:
  - docs/v3/README.md
  - docs/v3/PROMPTS.md
  - docs/v3/handoff/README.md
  - docs/standards/github-labels-standard.md
---

# Vibe 3.0 Development Roadmap

> 本文档定义 Vibe 3.0 重构的完整 roadmap，用于 GitHub Project 任务跟踪

---

## 📊 项目概览

**项目目标**: 将 Vibe Center 重构为确定性、可追踪的 AI 开发编排工具

**当前状态**:
- ✅ Phase 1 (Infrastructure): 100% 完成
- ⏸️ Phase 2 (Trace): 待启动（优先级暂低于 Governance）
- ✅ Phase 3 (Handoff): 100% 完成
- ✅ Phase 4 (Orchestra): Active/Delivered (Orchestra server 已部署，治理层已上线)

**文档规模**: 40 个文档，约 11,233 行

---

## 🎯 Phase 1: Infrastructure（基础设施层）

**状态**: ✅ 已完成（100% 完成）

### 1.1 核心模块实现

#### ✅ 已完成

- [x] 目录结构创建（`src/vibe3/`）
- [x] Client 隔离（`clients/` 包含 GitClient、GitHubClient）
- [x] Models 定义（`models/`）
- [x] Commands 骨架（`commands/`）
- [x] Services 骨架（`services/`）
- [x] UI 层（`ui/`）
- [x] Config 模块（`config/`）
- [x] **实现 `observability/logger.py`**
  - Agent-Centric Logging 系统
  - 支持 verbose 参数（0=ERROR, 1=INFO, 2=DEBUG）
  - 集成到所有命令
- [x] **实现 `exceptions/` 模块**
  - 统一的 VibeError 层级
  - 所有异常继承 VibeError
  - 错误码和错误消息标准化
- [x] **为核心命令添加核心参数集**
  - `--trace` (调用链路追踪 + DEBUG 日志)
  - `--json` (输出格式)
  - `-y, --yes` (跳过确认)
- [x] **测试覆盖达标**
  - Services 层核心功能已测试
  - Clients 层关键路径已测试

### 1.2 文档完善

#### ✅ 已完成

- [x] **更新 infrastructure 文档**
  - [x] 05-logging.md - 日志系统实施细节
  - [x] 06-error-handling.md - 异常处理细节
- [x] **创建 examples/ 示例**
  - [x] 命令使用示例
  - [x] 日志配置示例
  - [x] 异常处理示例

---

## 🔍 Phase 2: Trace（调试追踪层）

**状态**: ⏸️ 待启动（Phase 1 完成后，当前优先级较低）

### 2.1 核心功能

- [ ] **实现 `--trace` 参数**
  - 使用 `sys.settrace` 实现轻量级追踪
  - 追踪开销 < 20%
  - 一次性输出到控制台
  - **预估**: 8-12 小时
  - **依赖**: Phase 1 完成

- [ ] **实现 TraceCollector 接口**
  - 为 Phase 4 预留接口
  - 支持扩展到持久化追踪
  - **预估**: 4-6 小时
  - **依赖**: `--trace` 实现

### 2.2 命令集成

- [ ] **`vibe3 review pr 42 --trace`**
  - 输出调用链路
  - 显示执行步骤
  - **预估**: 3-4 小时

- [ ] **`vibe3 inspect pr 42 --trace`**
  - 输出调用链路
  - 显示数据流
  - **预估**: 3-4 小时

### 2.3 文档

- [ ] **更新 trace/ 文档**
  - 实施细节
  - 性能基准
  - 使用指南
  - **预估**: 2-3 小时

---

## 🔄 Phase 3: Handoff（责任链层）

**状态**: ✅ 已完成（100% 完成）

### 3.1 数据存储

- [x] **实现 SQLite handoff store**
  - 数据库迁移脚本
  - `clients/store_client.py`
  - 数据模型定义

### 3.2 核心服务

- [x] **实现 HandoffService**
  - `services/handoff_service.py`
  - Plan/Execute/Review 三阶段
  - Agent 署名机制

### 3.3 命令集成

- [x] **集成到现有命令**
  - `vibe3 flow` 记录操作
  - `vibe3 task` 记录操作
  - `vibe3 pr` 记录操作

### 3.4 可视化

- [x] **`vibe3 task status` 显示责任链**
  - 显示操作历史
  - 显示 agent 署名
  - 显示产物引用

### 3.5 文档

- [x] **更新 handoff/ 文档**
  - 实施细节
  - 数据模型
  - 使用指南

---

## 🎭 Phase 4: Orchestra（自动编排层）

**状态**: ✅ Active/Delivered（Orchestra server 已部署）

**当前进展**:
- ✅ Orchestra server 已上线（`vibe3 serve`）
- ✅ Manager / Planner / Executor / Reviewer 角色已实现
- ✅ GitHub webhook 接收器已部署
- ✅ Heartbeat 轮询机制已实现
- ✅ Issue 分诊与 flow 触发已实现
- ✅ **Tier 3 Governance 实现**
  - `cron-supervisor`: 自动文档治理识别
  - `roadmap-intake`: 三级审查机制
  - `supervisor-apply`: 自动化治理执行
- 🔄 多 issue 编排与治理闭环持续优化中

**文档**: 设计已完成，核心功能已实现

---

## 📋 Execution Plan 任务（独立跟踪）

这些任务与上述 Phase 并行，聚焦于具体执行步骤：

### Phase 01: CLI Skeleton & Contract

- [x] `vibe3 flow --help` 返回正确输出
- [x] `vibe3 task --help` 返回正确输出
- [x] `vibe3 pr --help` 返回正确输出
- [ ] `mypy src/vibe3/ --strict` 无错误 (集成完成，正在清理错误)

### Phase 02: Flow & Task State (SQLite)

- [x] `vibe3 flow update` 创建/更新 flow 记录
- [x] `vibe3 task status --json` 输出 JSON 格式
- [x] FlowService 单元测试 100% 通过

### Phase 03: PR Domain (GitHub Integration)

- [x] `vibe3 pr draft` 生成 PR URL
- [x] `vibe3 pr ready` 更新 PR 状态
- [x] 日志显示完整 metadata

### Phase 04: Handoff & Logic Cutover

- [x] handoff truth model 收敛完成
- [x] `.agent/context/task.md` 降级角色已明确
- [x] review report 与 `SESSION_ID` 被明确为证据指针

### Phase 05: Verification & Cleanup

- [x] `time vibe3 flow status` < 1.0s
- [x] 清理所有 TODO 和 print()
- [x] 所有冒烟测试通过

---

## 📅 时间估算

| Phase | 预估时间 | 优先级 |
|-------|---------|--------|
| Phase 1 完成 | ✅ 已交付 | P0 |
| Phase 2 完成 | 15-20 小时 | P1 |
| Phase 3 完成 | ✅ 已交付 | P2 |
| Phase 4 核心 | ✅ 已交付 | P0 |
| **总计** | **已进入持续交付阶段** | - |

**建议迭代周期**: 每个 Phase 完成后进行 review 和验证

---

## 🏷️ GitHub Project 配置

### 标签建议

使用现有的标签系统（见 [docs/standards/github-labels-standard.md](../standards/github-labels-standard.md)）：

**类型标签**:
- `type/feature` - 新功能开发
- `type/fix` - Bug 修复
- `type/refactor` - 代码重构
- `type/docs` - 文档更新
- `type/test` - 测试相关

**范围标签**:
- `scope/python` - Python 代码改动
- `scope/infrastructure` - 基础设施改动
- `scope/documentation` - 文档改动

**组件标签**:
- `component/logger` - Logger 模块
- `component/flow` - Flow 模块
- `component/pr` - PR 模块
- `component/task` - Task 模块

**状态标签**:
- `state/blocked` - 阻塞
- `state/in-progress` - 进行中
- `state/review` - 待审核

**优先级标签**:

**Numeric Priority (推荐)**:
- `priority/9` - 紧急阻断性问题（最高优先级）
- `priority/7-8` - 核心功能、关键 bug 修复
- `priority/5-6` - 重要但非紧急的功能
- `priority/3-4` - 一般功能、改进项
- `priority/1-2` - 低优先级改进
- `priority/0` - 默认优先级（无标签时）

**Legacy Priority (兼容支持)**:
- `priority/critical` - 最高优先级（等同于 priority/9）
- `priority/high` - 高优先级（等同于 priority/7）
- `priority/medium` - 中等优先级（等同于 priority/5）
- `priority/low` - 低优先级（等同于 priority/3）

**队列排序规则**:
Orchestra ready queue 使用三级排序：
1. Milestone (版本号小的优先，如 v0.1 > v0.3)
2. Roadmap (p0 > p1 > p2)
3. Priority (数值大的优先，如 priority/9 > priority/0)

### Project 字段建议

1. **Status**: Todo, In Progress, Done, Blocked
2. **Priority**: P0 (priority/9), P1 (priority/7), P2 (priority/5), P3 (priority/3)
3. **Phase**: Phase 1, Phase 2, Phase 3, Phase 4
4. **Estimate**: 时间估算（小时）
5. **Dependencies**: 依赖任务

---

## ✅ 验收标准

### Phase 1 验收

- [x] 所有命令包含核心参数集
- [x] 所有异常继承 VibeError
- [x] 日志系统支持 verbose 参数
- [x] 所有外部调用在 clients/ 中封装
- [x] 测试覆盖核心功能

### Phase 2 验收

- [ ] `vibe3 review pr 42 --trace` 输出调用链路
- [ ] `vibe3 inspect pr 42 --trace` 输出调用链路
- [ ] 追踪开销 < 20%
- [ ] 不影响命令执行结果

### Phase 3 验收

- [ ] 每个操作记录到 SQLite handoff store
- [ ] 每个 agent 署名
- [ ] 产物引用不复制正文
- [ ] `vibe3 flow status` 显示责任链

---

## 📚 参考文档

### 项目核心文档

- **[docs/v3/README.md](docs/v3/README.md)** - 项目设计入口
- **[docs/v3/PROMPTS.md](docs/v3/PROMPTS.md)** - 项目设计总依据（权威）

### 实施文档

- **[docs/v3/handoff/README.md](docs/v3/handoff/README.md)** - Execution Plan
- **[docs/v3/infrastructure/README.md](docs/v3/infrastructure/README.md)** - 基础设施文档入口

### 标准文档

- **[docs/standards/github-labels-standard.md](docs/standards/github-labels-standard.md)** - GitHub 标签标准

---

**维护者**: Vibe Team
**最后更新**: 2026-03-17
**版本**: 1.0
