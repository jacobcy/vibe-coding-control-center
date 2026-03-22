# Structure Snapshot 重构 Effort 评估

> **评估日期**: 2026-03-21
> **评估范围**: 基于现有代码，实现 Structure Snapshot 系统
> **参考**: [design-proposal.md](./design-proposal.md)

---

## 1. 改动范围统计

### 1.1 受影响文件

| 文件 | 行数 | 改动类型 | 影响度 |
|------|------|---------|--------|
| `src/vibe3/services/structure_service.py` | 155 | 重命名 + 重构 | 🔴 高 |
| `src/vibe3/commands/inspect.py` | 240 | 扩展命令 | 🟡 中 |
| `src/vibe3/commands/structure.py` | 63 | 合并或删除 | 🟡 中 |
| `tests/vibe3/services/test_structure_service.py` | 105 | 重命名 + 更新 | 🟡 中 |
| `tests/vibe3/commands/test_inspect_structure.py` | 54 | 更新导入 | 🟢 低 |
| **总计** | **617** | | |

### 1.2 新增文件

| 文件 | 预估行数 | 说明 |
|------|---------|------|
| `src/vibe3/models/snapshot.py` | ~150 | Snapshot 模型定义 |
| `src/vibe3/services/structure_service.py` (新) | ~200 | 项目级快照服务 |
| `src/vibe3/services/function_hash.py` | ~80 | Function Hash 计算 |
| `tests/vibe3/services/test_snapshot_service.py` | ~150 | 快照服务测试 |
| `tests/vibe3/models/test_snapshot.py` | ~80 | 模型测试 |
| **总计** | **~660** | |

---

## 2. 改动分类与 Effort 评估

### 2.1 Phase 1: 重构现有代码（预估 2-3 小时）

**目标**：职责拆分，`structure_service.py` → `file_analyzer.py`

| 任务 | Effort | 风险 | 说明 |
|------|--------|------|------|
| 重命名文件 | 5min | 🟢 低 | `mv structure_service.py file_analyzer.py` |
| 重命名类 | 10min | 🟢 低 | 全局替换 `FileStructure` → `FileAnalysisResult` |
| 更新导入 | 30min | 🟡 中 | 5 个文件，逐个更新导入路径 |
| 更新测试 | 30min | 🟡 中 | 重命名测试文件，更新断言 |
| 验证测试通过 | 15min | 🟢 低 | `uv run pytest` |

**风险点**：
- 导入路径遗漏（低风险，IDE 会提示）
- 测试断言失败（低风险，只是重命名）

---

### 2.2 Phase 2: 实现基础快照（预估 4-6 小时）

**目标**：MVP 第一阶段，基本快照能力

| 任务 | Effort | 风险 | 说明 |
|------|--------|------|------|
| 定义 Snapshot 模型 | 1h | 🟢 低 | Pydantic 模型定义 |
| 实现模块聚合逻辑 | 2h | 🟡 中 | 按目录聚合文件级数据 |
| 复用 dag_service 提取依赖 | 30min | 🟢 低 | 现有代码复用 |
| 实现 `build_snapshot()` | 1.5h | 🟡 中 | 整合所有能力 |
| 实现 `save/load_snapshot()` | 30min | 🟢 低 | JSON 序列化/反序列化 |
| 更新 CLI 命令 | 1h | 🟡 中 | 扩展 `inspect structure` |
| 测试编写 | 1.5h | 🟡 中 | 单元测试 + 集成测试 |

**风险点**：
- 模块聚合逻辑复杂度（中等风险，需要正确处理目录层级）
- 快照文件格式稳定性（中等风险，需要保证 key 顺序）

---

### 2.3 Phase 3: 实现变更对比（预估 3-4 小时）

**目标**：MVP 第二阶段，`structure diff`

| 任务 | Effort | 风险 | 说明 |
|------|--------|------|------|
| 定义 SnapshotDiff 模型 | 30min | 🟢 低 | Pydantic 模型定义 |
| 实现 `diff_snapshots()` | 2h | 🟡 中 | 对比逻辑实现 |
| 实现文本化输出 | 1h | 🟢 低 | 格式化输出（表格 + ASCII） |
| 更新 CLI 命令 | 30min | 🟢 低 | 添加 `--diff` 选项 |
| 测试编写 | 1h | 🟡 中 | 对比逻辑测试 |

**风险点**：
- Diff 逻辑正确性（中等风险，需要覆盖各种变更场景）
- 输出格式可读性（低风险，可以迭代优化）

---

### 2.4 Phase 4: 实现重复检测（预估 4-5 小时）

**目标**：完整版，Function Hash + Duplication

| 任务 | Effort | 风险 | 说明 |
|------|--------|------|------|
| 实现 Function Hash（简化版） | 1.5h | 🟡 中 | 直接 hash AST |
| 构建重复代码映射 | 1h | 🟢 低 | Hash → 出现次数 |
| 更新 Snapshot 模型 | 30min | 🟢 低 | 添加 duplication 字段 |
| 更新 `build_snapshot()` | 1h | 🟡 中 | 整合 Function Hash |
| 更新 Diff 输出 | 30min | 🟢 低 | 输出重复代码变化 |
| 测试编写 | 1h | 🟡 中 | Hash 正确性测试 |

**风险点**：
- Function Hash 算法选择（中等风险，简化版可能不够精确）
- 性能问题（低风险，项目规模不大）

---

## 3. 总 Effort 估算

### 3.1 按阶段估算

| 阶段 | Effort | 累计 | 交付物 |
|------|--------|------|--------|
| Phase 1: 重构现有代码 | 2-3h | 2-3h | `file_analyzer.py` |
| Phase 2: 基础快照 | 4-6h | 6-9h | `structure build` |
| Phase 3: 变更对比 | 3-4h | 9-13h | `structure diff` |
| Phase 4: 重复检测 | 4-5h | 13-18h | Duplication Map |

### 3.2 按优先级估算

**MVP 最小可交付**（Phase 1 + 2）：**6-9 小时**
- 完成重构
- 实现 `structure build`
- 生成 `snapshot.json`

**推荐版本**（Phase 1 + 2 + 3）：**9-13 小时**
- MVP + `structure diff`
- 完整的快照对比能力

**完整版**（Phase 1-4）：**13-18 小时**
- 全部功能
- Duplication 检测

---

## 4. 风险与依赖

### 4.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 模块聚合逻辑错误 | 中 | 中 | 增量测试，先从简单场景开始 |
| Function Hash 算法不精确 | 中 | 低 | MVP 用简化版，后续优化 |
| 快照文件格式不稳定 | 低 | 中 | 使用 Pydantic，保证字段顺序 |
| 性能问题 | 低 | 低 | 项目规模小，暂不考虑 |

### 4.2 依赖项

**现有依赖**（可直接复用）：
- ✅ `dag_service.py` - 模块依赖图
- ✅ `metrics_service.py` - 项目度量
- ✅ Pydantic - 模型定义

**新增依赖**：
- ❌ 无（Function Hash 用标准库 hashlib）

---

## 5. 实施建议

### 5.1 推荐实施路径

**方案A：渐进式交付**（推荐）
1. **第一周**：Phase 1 + 2（基础快照）
   - 重构现有代码
   - 实现 `structure build`
   - 验证基本能力

2. **第二周**：Phase 3（变更对比）
   - 实现 `structure diff`
   - 完善 CLI 交互

3. **第三周**（可选）：Phase 4（重复检测）
   - 实现 Function Hash
   - 检测重复代码

**方案B：一次性交付**
- 连续 2-3 天完成全部 4 个阶段
- 风险：一次性改动较大，测试覆盖可能不足

### 5.2 质量保证

**测试策略**：
- Phase 1：确保现有测试通过（回归测试）
- Phase 2-4：新增单元测试 + 集成测试
- 测试覆盖率目标：80%+

**验证方式**：
1. 运行现有测试：`uv run pytest tests/vibe3/services/test_structure_service.py`
2. 生成真实快照：`vibe3 inspect structure --build`
3. 对比真实变更：`vibe3 inspect structure --diff main feature`

---

## 6. 结论

### 6.1 Effort 总结

| 版本 | Effort | 适用场景 |
|------|--------|---------|
| MVP（基础快照） | 6-9 小时 | 快速验证能力，满足基本需求 |
| 推荐（+ 对比） | 9-13 小时 | 生产可用，完整的快照能力 |
| 完整（+ 重复检测） | 13-18 小时 | 完整功能，自动化重复检测 |

### 6.2 建议

**短期**（1-2 周）：
- 实施 Phase 1 + 2（基础快照）
- Effort：6-9 小时
- 交付物：`structure build` + `snapshot.json`

**中期**（1 个月）：
- 实施 Phase 3（变更对比）
- Effort：+3-4 小时
- 交付物：`structure diff`

**长期**（可选）：
- 实施 Phase 4（重复检测）
- Effort：+4-5 小时
- 交付物：Duplication Map

### 6.3 投入产出比

| 版本 | 投入 | 产出 | ROI |
|------|------|------|-----|
| MVP | 6-9h | 基础快照能力 | 🟢 高 |
| 推荐 | 9-13h | 完整快照 + 对比 | 🟢 高 |
| 完整 | 13-18h | 全部功能 | 🟡 中 |

**建议优先实施 MVP 版本**，验证价值后再决定是否扩展。

---

## 7. 附录：改动详细清单

### 7.1 受影响文件改动详情

#### `src/vibe3/services/structure_service.py` → `file_analyzer.py`
- **改动类型**：重命名 + 重构
- **改动内容**：
  - 文件名：`structure_service.py` → `file_analyzer.py`
  - 类名：`StructureError` → `FileAnalysisError`
  - 类名：`FileStructure` → `FileAnalysisResult`
  - 函数签名：无变化（只是重命名）
- **影响范围**：所有导入该模块的地方

#### `src/vibe3/commands/inspect.py`
- **改动类型**：扩展
- **改动内容**：
  - 更新导入：`from vibe3.services.file_analyzer import analyze_file`
  - 新增选项：`--build`、`--show`、`--diff`
  - 新增逻辑：调用 `StructureService`
- **影响范围**：`structure` 命令

#### `src/vibe3/commands/structure.py`
- **改动类型**：合并或删除
- **改动内容**：
  - 选项A：删除（合并到 `inspect structure`）
  - 选项B：保留（独立命令）
- **影响范围**：用户使用习惯

#### 测试文件
- **改动类型**：重命名 + 更新
- **改动内容**：
  - 文件名：`test_structure_service.py` → `test_file_analyzer.py`
  - 更新断言：类名变化

### 7.2 新增文件清单

#### `src/vibe3/models/snapshot.py` (~150 行)
```python
class ModuleMetrics(BaseModel): ...
class ModuleInfo(BaseModel): ...
class Snapshot(BaseModel): ...
class SnapshotDiff(BaseModel): ...
class ModuleChange(BaseModel): ...
class DuplicationInfo(BaseModel): ...
```

#### `src/vibe3/services/structure_service.py` (新，~200 行)
```python
class StructureService:
    def build_snapshot(self) -> Snapshot: ...
    def load_snapshot(self) -> Snapshot: ...
    def save_snapshot(self) -> None: ...
    def diff_snapshots(self) -> SnapshotDiff: ...
    def _aggregate_modules(self) -> list[ModuleInfo]: ...
```

#### `src/vibe3/services/function_hash.py` (~80 行)
```python
def compute_function_hash(node: ast.FunctionDef) -> str: ...
```

#### 测试文件 (~230 行)
- `tests/vibe3/services/test_snapshot_service.py` (~150 行)
- `tests/vibe3/models/test_snapshot.py` (~80 行)