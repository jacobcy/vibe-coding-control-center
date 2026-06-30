# Services

核心业务逻辑层，实现 flow/PR/task/handoff 等工作流。

## 职责

- Flow 生命周期管理（创建、状态转变、查询、投影）
- PR 全生命周期（创建、评分、merge、ready）
- Task 绑定与管理
- Handoff 记录与恢复
- Pre-push 检查
- Label 状态编排
- 版本管理
- Issue 失败处理
- 编排状态聚合

## 目录结构

### `issue/` - Issue 领域
- `failure.py`: Issue 失败/阻塞处理
- `flow.py`: Issue 与 Flow 映射
- `title_cache.py`: Issue 标题缓存服务

### `pr/` - PR 领域
- `service.py`: PR 主服务
- `create.py`: PR 创建用例
- `ready.py`: PR ready 用例
- `analysis.py`: PR 变更影响分析
- `review.py`: PR review briefing 编排
- `utils.py`: PR 构建辅助

### `task/` - Task 领域
- `service.py`: Task 绑定管理
- `resume.py`: 失败任务恢复入口
- `show.py`: Task 展示服务
- `status.py`: Task 状态查询
- `classifier.py`: Task 状态分类器

### `shared/` - 跨领域公共能力
- `labels.py`: 状态标签编排
- `paths.py`: 路径常量与辅助
- `errors.py`: 统一错误记录
- `branches.py`: 分支命名与解析

### `protocols/` - 内部服务协议
- `flow_protocols.py`: Flow 相关协议

## 核心逻辑文件 (Root)

- `flow_service.py`: Flow CRUD + 状态转变
- `handoff_service.py`: Handoff 记录服务
- `handoff_storage.py`: Handoff 存储服务
- `check_service.py`: Pre-push 检查
- `orchestra_status_service.py`: 编排状态聚合查询
- `version_service.py`: 版本号管理
- `verdict_service.py`: 裁决服务

## 依赖关系

### 依赖
- `clients`：Git 客户端、GitHub 客户端、SQLite 客户端、AI 客户端
- `domain`：事件发布、状态机规则
- `models`：领域模型定义
- `config`：编排配置加载
- `exceptions`：业务异常
- `analysis`：代码分析服务

### 被依赖
- `commands`：命令层调用服务
- `execution`：执行器调用服务
- `domain handlers`：事件处理器调用服务
- `orchestra`：全局编排调用服务

## 架构说明

### Flow 生命周期
Flow 是编排的核心概念，代表一次完整的任务执行流程。

### Handoff 机制
Handoff 用于跨 agent 传递上下文，存储在 `.git/vibe3/handoff.db`。
