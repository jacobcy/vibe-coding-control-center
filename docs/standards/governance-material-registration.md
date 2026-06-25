# Governance Material Registration Standard

状态：Active

## 1. 目的

本标准说明 governance material 的 4 层注册路径，以及每层的作用、验证方法和常见模式。

**治理材料（governance material）** 是 supervisor prompt 的一类，专门用于 orchestra governance scan 的轮转执行。每个 tick 从 material catalog 中按 `tick_count % len(catalog)` 选出一个材料，交给 governance agent 执行。

## 2. 何时创建治理材料

满足以下条件的 supervisor 材料应注册为 governance material：

- 需要被 orchestra heartbeat tick 自动轮转执行
- 需要基于 governance snapshot（活跃 issue 列表、server 状态、circuit breaker 等）做分析
- 属于全局治理职责（如 assignee 分配、roadmap 摄入、cron 任务监督），而非单个 issue 级别的操作

不需要注册为 governance material 的情况：

- 只在特定 issue 流程中使用的 supervisor 模板（如 `apply.md`、`manager.md`）
- 一次性或实验性脚本，尚未纳入正式治理流程

## 3. 四层注册路径

### 3.1 第一层：文件位置

治理材料文件位于 `supervisor/governance/` 目录下：

```
supervisor/governance/assignee-pool.md
supervisor/governance/roadmap-intake.md
supervisor/governance/cron-supervisor.md
supervisor/governance/code-auditor.md
supervisor/governance/audit-observation.md
supervisor/governance/audit-suggestion.md
supervisor/governance/audit-report.md
```

注意区分：

| 位置 | 类型 | 示例 |
|------|------|------|
| `supervisor/governance/<name>.md` | 治理材料 | `assignee-pool.md`, `roadmap-intake.md`, `cron-supervisor.md`, `code-auditor.md`, `audit-observation.md` |
| `supervisor/<name>.md` | 通用 supervisor 模板 | `apply.md`, `manager.md` |

通用 supervisor 模板**不是**治理材料，它们通过其他 recipe（如 `manager.default`、`supervisor.handoff`）被加载。

### 3.2 第二层：Adapter 注册

文件必须在 adapter manifest 中注册为 `type="supervisor"` 的资源：

**文件**: `src/vibe3/adapters/vibe_center.py`

```python
AdapterResource(
    type="supervisor",
    name="assignee-pool",
    path="supervisor/governance/assignee-pool.md",
),
```

`name` 是资源短名称，`path` 是从 repo root 开始的相对路径。

### 3.3 第三层：Prompt Recipe 注册

必须在 `config/prompts/prompt-recipes.yaml` 的 `governance.scan.material_catalog` 中注册：

**文件**: `config/prompts/prompt-recipes.yaml`

```yaml
recipes:
  governance.scan:
    kind: template_recipe
    template_key: orchestra.governance.plan
    material_catalog:
      - name: supervisor/governance/assignee-pool.md
        source:
          kind: file
          path: supervisor/governance/assignee-pool.md
```

关键约束：

- `material_catalog` 中每个条目的 `name` 必须与 adapter 注册中的 `path` 完全一致
- `source.kind` 通常为 `"file"`，指向实际文件路径
- 新添材料只需修改此 YAML 和 adapter manifest，**不需要**修改 `governance.py` 等运行时 Python 代码

### 3.4 第四层：运行时加载

`src/vibe3/roles/governance.py` 中的 `load_governance_material_catalog()` 函数从 prompt manifest 读取 material catalog：

```python
def load_governance_material_catalog() -> tuple[PromptMaterialSpec, ...]:
    recipe_def = _load_governance_recipe_definition()
    catalog = recipe_def.loaded_definition.material_catalog
    return catalog
```

此层不需要手动修改代码——只要第三层 YAML 正确，运行时自动生效。

## 4. 验证清单

添加新治理材料后，按以下步骤验证：

### 4.1 文件存在性

```bash
ls supervisor/governance/<name>.md
```

### 4.2 Adapter 注册

```bash
# 检查 adapter manifest 中是否有对应条目
rg '<name>' src/vibe3/adapters/vibe_center.py
```

期望：找到 `AdapterResource(type="supervisor", name="<name>", path="supervisor/governance/<name>.md")`

### 4.3 Recipe 注册

```bash
# 检查 prompt-recipes.yaml 中是否有对应条目
rg '<name>' config/prompts/prompt-recipes.yaml
```

期望：在 `governance.scan.material_catalog` 下找到该材料的 `name` 和 `source` 条目。

### 4.4 运行时验证

```bash
# 列出当前可用的治理材料
uv run python src/vibe3/cli.py scan governance --list
```

期望：新添加的材料出现在列表中。

### 4.5 一致性校验（可选）

```bash
uv run python -c "from vibe3.services.scan_service import validate_governance_material_consistency; print(validate_governance_material_consistency())"
```

期望：返回空列表 `[]`，表示 adapter ↔ recipe ↔ 文件系统三者一致。

## 5. 常见模式

### 5.1 Tick 轮转

Governance scan 通过以下代码实现轮转：

```python
catalog = load_governance_material_catalog()
current = catalog[tick_count % len(catalog)]
```

`tick_count` 来自 heartbeat 计数器。添加或删除材料会自动影响轮转周期，无需额外修改。

### 5.2 材料覆盖（Material Override）

CLI 支持 `--role` 参数临时覆盖轮转：

```bash
uv run python src/vibe3/cli.py scan governance --role roadmap-intake
```

此模式用于调试或强制指定某一材料执行，不影响正常轮转。

### 5.3 Material Spec 的 source 类型

`PromptMaterialSpec.source` 使用 `PromptVariableSource`，常见 `kind`：

- `"file"`: 从文件系统读取（标准做法）
- `"literal"`: 内联内容（用于测试或特殊场景）

治理材料通常使用 `"file"` 类型。

## 6. 与通用 Supervisor 模板的区别

| 维度 | 治理材料 | 通用 Supervisor 模板 |
|------|----------|---------------------|
| 文件位置 | `supervisor/governance/` | `supervisor/` |
| Recipe | `governance.scan.material_catalog` | `manager.default`, `supervisor.handoff` 等 |
| 触发方式 | Heartbeat tick 轮转 | Issue 流程按需调用 |
| 上下文 | Governance snapshot | Issue-specific context |
| 典型用途 | 全局扫描、分配、摄入 | Issue 级别操作、handoff |

两者都在 adapter manifest 中注册为 `type="supervisor"`，但只有治理材料出现在 `material_catalog` 中。
