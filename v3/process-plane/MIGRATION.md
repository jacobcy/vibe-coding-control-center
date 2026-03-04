# Migration Guide: V2 to V3 Process Plane

## 概述

本指南帮助你从 V2 迁移到 V3 Process Plane。

## 关键变化

### 1. 架构变化

**V2**:
- Provider 逻辑分散在多个模块
- 硬编码路由
- 无统一接口

**V3**:
- 统一的 Provider Router
- 智能路由策略引擎
- 标准化的 Adapter 接口

### 2. 接口变化

**V2 方式**:
```bash
# 直接调用 provider
openspec apply --change "my-change"
```

**V3 方式**:
```bash
# 通过路由器调用
source v3/process-plane/router.sh
TASK='{"type":"spec-driven","id":"my-change"}'
REF=$(pp_start "$TASK" '{}')
pp_complete "$REF"
```

## 迁移步骤

### 步骤 1: 验证 V3 独立性

```bash
# V3 在独立目录，不影响 V2
ls v3/process-plane/
```

✅ V3 完全独立，不会影响 V2 代码

### 步骤 2: 数据兼容性

V3 与 V2 共享数据格式，无需数据迁移。

**共享的数据**:
- 任务定义格式
- 配置文件格式
- 环境变量

### 步骤 3: 并行运行（可选）

在完全切换前，可以并行运行 V2 和 V3：

```bash
# V2 方式
vibe task add "my-task"

# V3 方式（测试）
source v3/process-plane/router.sh
pp_start '{"type":"spec-driven","id":"test"}' '{}'
```

### 步骤 4: 切换到 V3

```bash
# 更新别名或脚本指向 V3
# 例如：将 vibe 命令更新为使用 V3 接口
```

### 步骤 5: 废弃 V2

在 V3 稳定运行后，逐步废弃 V2 代码。

## 回滚计划

如果需要回滚到 V2：

1. **切换回 V2 接口** - 无需代码更改，只需切换调用方式
2. **数据兼容** - V3 数据格式与 V2 兼容
3. **清理 V3** - 可选：删除 v3/ 目录

```bash
# 回滚示例
# 1. 停止使用 V3 接口
# 2. 恢复使用 V2 命令
vibe task add "fallback-task"
```

## 功能对比

| 功能 | V2 | V3 |
|------|----|----|
| Provider 路由 | 硬编码 | 智能策略 |
| 降级机制 | 手动 | 自动 |
| Provider 接入 | 修改多处代码 | 实现 Adapter |
| 状态管理 | 分散 | 统一 |
| 测试 | 部分 | 完整覆盖 |

## 常见问题

### Q: V2 和 V3 可以同时存在吗？
A: 是的，V3 在独立目录，不影响 V2。

### Q: 数据会丢失吗？
A: 不会，V3 与 V2 共享数据格式。

### Q: 如何验证 V3 正常工作？
A: 运行测试套件：
```bash
bash tests/process-plane/test-comprehensive.sh
```

### Q: 迁移需要多长时间？
A: 取决于使用情况，通常 1-2 小时完成切换和验证。

## 灰度测试建议

1. **小范围测试** - 选择 1-2 个非关键任务使用 V3
2. **监控效果** - 观察路由决策、执行结果
3. **逐步扩大** - 增加使用 V3 的任务比例
4. **全量切换** - 确认稳定后切换所有任务

## 支持

如有问题，请查看：
- [README.md](./README.md) - 使用文档
- [INTEGRATION.md](./INTEGRATION.md) - 集成文档
- [Test Suite](../tests/process-plane/) - 测试套件

---

**迁移状态**: ✅ V3 已就绪，可随时迁移
