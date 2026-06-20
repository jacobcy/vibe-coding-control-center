# Vibe Center Development Rules

本文件包含 vibe-center 项目内部开发专用的规则和约束。
这些内容仅在 vibe-center 仓库内工作时注入，跨项目执行时不加载。

术语以 [docs/standards/glossary.md](../../docs/standards/glossary.md) 为准。

## 跨层一致性检查

本项目的核心模块分为三层，命名/API/文档变更时必须全层覆盖检查：

### 三层结构

1. **Service 层**：`src/vibe3/services/` — 业务逻辑实现
2. **UI 层**：`src/vibe3/ui/` — 命令行交互界面
3. **Command 层**：`src/vibe3/commands/` — 命令入口定义

### 触发条件

以下任务类型必须执行跨层检查：
- 命名一致性修复（函数、变量、常量重命名）
- 文档同步（docstring、help text、error message）
- API 签名变更（函数参数、返回值、异常）
- 概念重命名（domain term、command name）

### 检查工具链

- **符号级引用**：`vibe3 inspect symbols <file>:<symbol>` 查找代码引用
- **字符串引用**：`rg '<old_name>'` 查找文档、配置、测试中的引用
- **组合使用**：先用 inspect 定位代码引用，再用 rg 补充字符串引用

### 适用阶段

- **Planner**：在 scoping 阶段搜索所有层，确认完整文件列表
- **Executor**：实现后验证所有层已更新，无遗漏旧引用
- **Reviewer**：审查时检查 plan scope 是否覆盖所有相关层

### 注意事项

- `rg` 是辅助工具，可能漏掉间接引用（如动态拼接的名称）
- 优先使用 `inspect symbols` 做符号级确认
- 如有怀疑，用 handoff 记录潜在遗漏

## CI 环境模拟验证

对于可能在 CI 和本地环境表现不一致的测试（特别是 subprocess 测试）：

```bash
# 方式一：设置 CI 环境变量运行测试
GITHUB_ACTIONS=true uv run pytest tests/vibe3/path/to/test.py

# 方式二：使用 pre-push CI 模拟模式
VIBE_CI_SIMULATE=1 bash scripts/hooks/pre-push.sh

# 方式三：运行 CI parity 测试
uv run pytest tests/vibe3/integration/test_ci_parity.py -v
```

## 文件大小限制（LOC Limits）处理原则

当实现过程中遇到文件行数超过 `config/v3/loc_limits.yaml` 定义的限制时：

### 处理流程

1. **评估拆分可能性**
   - 检查文件职责是否可以合理拆分
   - 评估拆分是否会破坏内聚性
   - 考虑拆分后的维护成本

2. **如果可以合理拆分**
   - 在 plan 中明确拆分策略
   - 说明拆分后的职责边界
   - 验证拆分不会破坏现有功能

3. **如果无法合理拆分**
   - **立即**在 `config/v3/loc_limits.yaml` 的 `exceptions` 中添加例外
   - **不要让 LOC 限制阻碍开发进度**
   - 必须提供合理的理由（reason 字段）
   - 说明为什么该文件必须保持较大规模

### 例外申请模板

```yaml
- path: "src/vibe3/path/to/file.py"
  limit: 650
  reason: |
    文件职责说明，包含：
    - 核心功能 A（紧密耦合，不宜拆分）
    - 核心功能 B（依赖 A 的内部状态）
    - 核心功能 C（共享基础设施）

    拆分会破坏：
    - 数据一致性保证
    - 事务原子性
    - 代码可读性
```

### 判断标准

**值得拆分**：
- 文件包含多个独立职责
- 功能之间耦合度低
- 拆分后可独立测试和维护

**不应拆分**：
- 核心业务聚合（如 dispatcher、coordinator）
- 强耦合逻辑链（如 validation chain、state machine）
- 共享状态的紧密耦合（如 session registry）
- 测试集（fixture 共享，拆分收益低）

### 相关文档

- 配置文件：`config/v3/loc_limits.yaml`
- 项目规则：`CLAUDE.md` HARD RULES 第 12 条
- 详细标准：`.claude/rules/coding-standards.md` Size And Complexity
