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
- ✅ Phase 1 (Infrastructure): 70% 完成
- ⏸️ Phase 2 (Trace): 0% 完成
- ⏸️ Phase 3 (Handoff): 0% 完成
- ⏸️ Phase 4 (Orchestra): 冻结

**文档规模**: 40 个文档，约 11,233 行

---

## 🎯 Phase 1: Infrastructure（基础设施层）

**状态**: ✅ 进行中（70% 完成）

### 1.1 核心模块实现

#### ✅ 已完成

- [x] 目录结构创建（`src/vibe3/`）
- [x] Client 隔离（`clients/` 包含 GitClient、GitHubClient）
- [x] Models 定义（`models/`）
- [x] Commands 骨架（`commands/`）
- [x] Services 骨架（`services/`）
- [x] UI 层（`ui/`）
- [x] Config 模块（`config/`）

#### ⚠️ 待完成

**优先级 P0（阻塞其他阶段）**:

- [ ] **实现 `observability/logger.py`**
  - Agent-Centric Logging 系统
  - 支持 verbose 参数（0=ERROR, 1=INFO, 2=DEBUG）
  - 集成到所有命令
  - **预估**: 4-6 小时
  - **依赖**: 无
  - **阻塞**: Phase 2 Trace 系统

- [ ] **实现 `exceptions/` 模块**
  - 统一的 VibeError 层级
  - 所有异常继承 VibeError
  - 错误码和错误消息标准化
  - **预估**: 3-4 小时
  - **依赖**: 无
  - **阻塞**: 所有后续开发

- [ ] **为核心命令添加核心参数集**
  - `--trace` (调用链路追踪 + DEBUG 日志)
  - `--json` (输出格式)
  - `-y, --yes` (跳过确认)
  - **预估**: 6-8 小时
  - **依赖**: logger.py
  - **阻塞**: Phase 2 Trace 系统

**优先级 P1（质量保证）**:

- [ ] **提升测试覆盖率至 80%**
  - Services 层单元测试
  - Clients 层 mock 测试
  - Commands 层集成测试
  - **预估**: 8-12 小时
  - **依赖**: logger.py, exceptions/
  - **阻塞**: Phase 2 启动

### 1.2 文档完善

- [ ] **更新 infrastructure 文档**
  - [ ] 05-logging.md - 日志系统实施细节
  - [ ] 06-error-handling.md - 异常处理细节
  - **预估**: 2-3 小时

- [ ] **创建 examples/ 示例**
  - [ ] 命令使用示例
  - [ ] 日志配置示例
  - [ ] 异常处理示例
  - **预估**: 3-4 小时

---

## 🔍 Phase 2: Trace（调试追踪层）

**状态**: ⏸️ 待启动（Phase 1 完成后）

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

- [ ] **`vibe review pr 42 --trace`**
  - 输出调用链路
  - 显示执行步骤
  - **预估**: 3-4 小时

- [ ] **`vibe inspect pr 42 --trace`**
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

**状态**: ⏸️ 待启动（Phase 2 完成后）

### 3.1 数据存储

- [ ] **实现 SQLite handoff store**
  - 数据库迁移脚本
  - `clients/store_client.py`
  - 数据模型定义
  - **预估**: 8-12 小时
  - **依赖**: Phase 1 完成

### 3.2 核心服务

- [ ] **实现 HandoffService**
  - `services/handoff_service.py`
  - Plan/Execute/Review 三阶段
  - Agent 署名机制
  - **预估**: 10-14 小时
  - **依赖**: SQLite store

### 3.3 命令集成

- [ ] **集成到现有命令**
  - `vibe flow` 记录操作
  - `vibe task` 记录操作
  - `vibe pr` 记录操作
  - **预估**: 6-8 小时
  - **依赖**: HandoffService

### 3.4 可视化

- [ ] **`vibe flow status` 显示责任链**
  - 显示操作历史
  - 显示 agent 署名
  - 显示产物引用
  - **预估**: 4-6 小时
  - **依赖**: 命令集成

### 3.5 文档

- [ ] **更新 handoff/ 文档**
  - 实施细节
  - 数据模型
  - 使用指南
  - **预估**: 3-4 小时

---

## 🎭 Phase 4: Orchestra（自动编排层）

**状态**: ⏸️ 冻结

**解锁条件**:
- ✅ Phase 1-3 完成并稳定运行
- ✅ 有明确的 agent 自动编排需求
- ✅ 团队有资源投入

**文档**: 已完成设计文档，但不实施

---

## 📋 Execution Plan 任务（独立跟踪）

这些任务与上述 Phase 并行，聚焦于具体执行步骤：

### Phase 01: CLI Skeleton & Contract

- [ ] `bin/vibe3 flow --help` 返回正确输出
- [ ] `bin/vibe3 task --help` 返回正确输出
- [ ] `bin/vibe3 pr --help` 返回正确输出
- [ ] `mypy src/vibe3/ --strict` 无错误

### Phase 02: Flow & Task State (SQLite)

- [ ] `vibe3 flow new test-flow --task 101` 创建 handoff 记录
- [ ] `vibe3 flow status --json` 包含 flow_slug
- [ ] FlowService 单元测试 100% 通过

### Phase 03: PR Domain (GitHub Integration)

- [ ] `vibe3 pr draft` 生成 PR URL
- [ ] `vibe3 pr ready` 更新 PR 标签
- [ ] 日志显示"Metadata injected"

### Phase 04: Handoff & Logic Cutover

- [x] handoff truth model 收敛完成
- [x] `.agent/context/task.md` 降级角色已明确
- [x] review report 与 `SESSION_ID` 被明确为证据指针

### Phase 05: Verification & Cleanup

- [ ] `time bin/vibe3 flow status` < 1.0s
- [ ] 清理所有 TODO 和 print()
- [ ] 所有冒烟测试通过

---

## 📅 时间估算

| Phase | 预估时间 | 优先级 |
|-------|---------|--------|
| Phase 1 完成 | 20-30 小时 | P0 |
| Phase 2 完成 | 15-20 小时 | P1 |
| Phase 3 完成 | 25-35 小时 | P2 |
| **总计** | **60-85 小时** | - |

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
- `status/blocked` - 阻塞
- `status/in-progress` - 进行中
- `status/ready-for-review` - 待审核

**优先级标签**:
- `priority/critical` - 最高优先级
- `priority/high` - 高优先级
- `priority/medium` - 中等优先级
- `priority/low` - 低优先级

### Project 字段建议

1. **Status**: Todo, In Progress, Done, Blocked
2. **Priority**: P0, P1, P2, P3
3. **Phase**: Phase 1, Phase 2, Phase 3, Phase 4
4. **Estimate**: 时间估算（小时）
5. **Dependencies**: 依赖任务

---

## ✅ 验收标准

### Phase 1 验收

- [ ] 所有命令包含核心参数集
- [ ] 所有异常继承 VibeError
- [ ] 日志系统支持 verbose 参数
- [ ] 所有外部调用在 clients/ 中封装
- [ ] 测试覆盖率 >= 80%

### Phase 2 验收

- [ ] `vibe review pr 42 --trace` 输出调用链路
- [ ] `vibe inspect pr 42 --trace` 输出调用链路
- [ ] 追踪开销 < 20%
- [ ] 不影响命令执行结果

### Phase 3 验收

- [ ] 每个操作记录到 SQLite handoff store
- [ ] 每个 agent 署名
- [ ] 产物引用不复制正文
- [ ] `vibe flow status` 显示责任链

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
