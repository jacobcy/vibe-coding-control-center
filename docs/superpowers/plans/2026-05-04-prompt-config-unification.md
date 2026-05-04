# Prompt Config Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 manager、supervisor_handoff、governance 的 prompt 材料来源迁入 `config/prompts/prompt-recipes.yaml`，让 `config/v3/settings.yaml` 只保留运行时行为配置。

**Architecture:** 采用同一配置入口、两种 recipe 形态的渐进迁移方案：`section_recipe` 继续服务 manager/run/plan/review，新增 `template_recipe` 服务 governance/supervisor_handoff。迁移顺序是先扩展 prompt manifest 与通用 source 解析，再迁 manager，再迁 supervisor_handoff，再迁 governance，最后删除遗留 settings 字段并更新文档。

**Tech Stack:** Python 3.10+, Pydantic, pytest, YAML config loading, Vibe3 prompt assembly

---

## 文件结构

**核心实现文件：**
- `src/vibe3/prompts/manifest.py` - 扩展 recipe schema，支持 `kind`、section source、template recipe
- `src/vibe3/prompts/models.py` - 新增 recipe/section/source 数据模型
- `src/vibe3/prompts/assembler.py` - 复用现有 `PromptVariableSource` 解析逻辑，为 template recipe 提供统一入口
- `src/vibe3/roles/manager.py` - 删除 `assignee_dispatch.supervisor_file` 手工绑定，改用 recipe source
- `src/vibe3/roles/supervisor.py` - 删除 governance override，改为直属 supervisor handoff recipe
- `src/vibe3/roles/governance.py` - 删除 `governance.supervisor_file(s)` 作为 prompt 材料真源，改为 recipe catalog + tick 选择
- `src/vibe3/config/orchestra_config.py` - 删除 prompt 材料路径字段，仅保留运行时配置
- `config/prompts/prompt-recipes.yaml` - 新增 manager source 声明、supervisor_handoff template recipe、governance template recipe/material catalog
- `config/v3/settings.yaml` - 删除 `assignee_dispatch.supervisor_file`、`supervisor_handoff.supervisor_file`、`governance.supervisor_file(s)`

**回归和文档文件：**
- `tests/vibe3/prompts/test_prompt_manifest.py`
- `tests/vibe3/prompts/test_assembler.py`
- `tests/vibe3/roles/test_manager.py`
- `tests/vibe3/roles/test_supervisor.py`
- `tests/vibe3/roles/test_governance.py`
- `tests/vibe3/config/test_migrated_config_paths.py`
- `config/README.md`
- `config/v3/registry.yaml`

---

### Task 1: 扩展 prompt recipe schema，支持统一的配置表达

**Files:**
- Modify: `src/vibe3/prompts/models.py`
- Modify: `src/vibe3/prompts/manifest.py`
- Modify: `tests/vibe3/prompts/test_prompt_manifest.py`
- Modify: `tests/vibe3/prompts/test_models.py`

- [ ] **Step 1: 写 manifest/schema 兼容性失败测试**

在 `tests/vibe3/prompts/test_prompt_manifest.py` 新增两个测试：

```python
def test_prompt_manifest_loads_section_recipe_with_section_sources(tmp_path: Path) -> None:
    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  manager.default:
    kind: section_recipe
    variants:
      first.bootstrap:
        sections:
          - key: manager.supervisor_content
            source:
              kind: file
              path: supervisor/manager.md
          - key: manager.target
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)
    recipe = manifest.recipe("manager.default")

    assert recipe.kind == "section_recipe"
    variant = recipe.variant("first.bootstrap")
    assert variant.sections[0].key == "manager.supervisor_content"
    assert variant.sections[0].source is not None
    assert variant.sections[0].source.kind == VariableSourceKind.FILE


def test_prompt_manifest_loads_template_recipe(tmp_path: Path) -> None:
    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  governance.scan:
    kind: template_recipe
    template_key: orchestra.governance.plan
    variables:
      supervisor_content:
        kind: file
        path: supervisor/governance/assignee-pool.md
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)
    recipe = manifest.recipe("governance.scan")

    assert recipe.kind == "template_recipe"
    assert recipe.template_key == "orchestra.governance.plan"
    assert recipe.variables["supervisor_content"].kind == VariableSourceKind.FILE
```

- [ ] **Step 2: 运行测试确认当前 schema 不支持**

Run:

```bash
uv run pytest tests/vibe3/prompts/test_prompt_manifest.py -q
```

Expected: 新增测试失败，错误集中在 `PromptRecipeDefinition`/`PromptRecipeVariant` 无法解析 `kind`、对象化 `sections`、`variables`。

- [ ] **Step 3: 扩展 prompt 数据模型**

在 `src/vibe3/prompts/models.py` 新增 recipe schema 相关模型，保留现有 `PromptRecipe` 不动：

```python
class PromptRecipeKind(str, Enum):
    SECTION = "section_recipe"
    TEMPLATE = "template_recipe"


class PromptSectionSpec(BaseModel):
    model_config = {"frozen": True}

    key: str
    source: PromptVariableSource | None = None


class PromptRecipeVariantSpec(BaseModel):
    model_config = {"frozen": True}

    key: str
    sections: tuple[PromptSectionSpec, ...]
```

同时为后续 manifest 使用增加一个新的 recipe definition 数据结构：

```python
class LoadedPromptRecipeDefinition(BaseModel):
    model_config = {"frozen": True}

    key: str
    kind: PromptRecipeKind = PromptRecipeKind.SECTION
    template_key: str
    variants: dict[str, PromptRecipeVariantSpec] = Field(default_factory=dict)
    variables: dict[str, PromptVariableSource] = Field(default_factory=dict)
    description: str | None = None
```

- [ ] **Step 4: 在 manifest 中实现兼容解析**

修改 `src/vibe3/prompts/manifest.py`，让 loader 同时支持：

- 旧格式：`sections: ["plan.policy", "common.rules"]`
- 新格式：`sections: [{key: "manager.supervisor_content", source: {...}}]`
- 新 `kind: template_recipe`
- 新 `variables:` 映射

关键实现约束：

```python
def _parse_section_spec(raw: Any) -> PromptSectionSpec:
    if isinstance(raw, str):
        return PromptSectionSpec(key=raw)
    if isinstance(raw, dict) and "key" in raw:
        return PromptSectionSpec(
            key=str(raw["key"]),
            source=PromptVariableSource(**raw["source"]) if raw.get("source") else None,
        )
    raise ValueError(...)
```

并把 `PromptManifest.recipe()` 返回的新 recipe definition 类型。

- [ ] **Step 5: 更新 manifest 读取测试并验证兼容性**

Run:

```bash
uv run pytest tests/vibe3/prompts/test_prompt_manifest.py tests/vibe3/prompts/test_models.py -q
```

Expected: 现有 manifest 测试继续通过，新增 schema 测试通过。

- [ ] **Step 6: 提交**

```bash
git add src/vibe3/prompts/models.py src/vibe3/prompts/manifest.py tests/vibe3/prompts/test_prompt_manifest.py tests/vibe3/prompts/test_models.py
git commit -m "feat(prompt): extend recipe schema for unified config"
```

---

### Task 2: 引入通用 source 绑定，把 manager 的 supervisor 内容迁入 recipe

**Files:**
- Modify: `config/prompts/prompt-recipes.yaml`
- Modify: `config/v3/settings.yaml`
- Modify: `src/vibe3/roles/manager.py`
- Modify: `src/vibe3/config/orchestra_config.py`
- Modify: `tests/vibe3/roles/test_manager.py`
- Modify: `tests/vibe3/config/test_migrated_config_paths.py`

- [ ] **Step 1: 先写 manager 迁移后的行为测试**

在 `tests/vibe3/roles/test_manager.py` 增加一个验证 recipe source 生效、settings 字段不再需要的测试：

```python
def test_bootstrap_recipe_reads_supervisor_source_from_recipe(tmp_path, monkeypatch):
    supervisor_file = tmp_path / "manager.md"
    supervisor_file.write_text("MANAGER SUPERVISOR BODY", encoding="utf-8")

    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        f"""
recipes:
  manager.default:
    kind: section_recipe
    variants:
      first.bootstrap:
        sections:
          - key: manager.supervisor_content
            source:
              kind: file
              path: {supervisor_file}
          - key: manager.target
""",
        encoding="utf-8",
    )

    monkeypatch.setattr("vibe3.prompts.manifest.DEFAULT_PROMPT_RECIPES_PATH", recipes_path)
    config = OrchestraConfig(assignee_dispatch=AssigneeDispatchConfig())

    request = build_manager_sync_request(...)

    assert "MANAGER SUPERVISOR BODY" in (request.prompt or "")
```

同时在 `tests/vibe3/config/test_migrated_config_paths.py` 增加：

```python
assert "supervisor_file" not in orchestra.get("assignee_dispatch", {})
```

- [ ] **Step 2: 运行 manager/config 定向测试确认失败**

Run:

```bash
uv run pytest tests/vibe3/roles/test_manager.py tests/vibe3/config/test_migrated_config_paths.py -q
```

Expected: manager 仍依赖 `config.assignee_dispatch.supervisor_file`，新增测试失败。

- [ ] **Step 3: 把 source 写入 manager recipe**

更新 `config/prompts/prompt-recipes.yaml` 的 `manager.default.first.bootstrap.sections`：

```yaml
manager.default:
  kind: section_recipe
  variants:
    first.bootstrap:
      sections:
        - key: manager.supervisor_content
          source:
            kind: file
            path: supervisor/manager.md
        - key: manager.target
        - key: manager.quick_commands
```

保持 `retry.resume` 只保留 `manager.retry_task`。

- [ ] **Step 4: 删除 manager 的 settings 绑定代码**

修改 `src/vibe3/roles/manager.py`，不再读 `config.assignee_dispatch.supervisor_file`，而是从 manifest variant 的 section source 构建 provider：

```python
recipe_def = manifest.recipe("manager.default")
variant_def = recipe_def.variant(variant_key)

providers = {
    "manager.target": _make_section_provider(...),
    "manager.quick_commands": _make_section_provider(...),
    "manager.retry_task": _make_section_provider(...),
}

for section in variant_def.sections:
    if section.source and section.key == "manager.supervisor_content":
        source = section.source
        providers[section.key] = lambda src=source: resolve_source(src, {}, ProviderRegistry())
```

实现要求：

- 不要再访问 `config.assignee_dispatch.supervisor_file`
- provider 注册逻辑要通用到“section 上带 source 就可覆盖默认静态 provider”

- [ ] **Step 5: 删除 settings/orchestra_config 中 manager prompt 材料字段**

修改：

- `config/v3/settings.yaml` 删除 `orchestra.assignee_dispatch.supervisor_file`
- `src/vibe3/config/orchestra_config.py` 删除 `AssigneeDispatchConfig.supervisor_file`

同步更新相关断言/fixtures：

- `tests/vibe3/execution/test_execution_role_policy.py`

- [ ] **Step 6: 运行回归测试**

Run:

```bash
uv run pytest tests/vibe3/roles/test_manager.py tests/vibe3/config/test_migrated_config_paths.py tests/vibe3/execution/test_execution_role_policy.py -q
uv run ruff check src/vibe3/roles/manager.py src/vibe3/config/orchestra_config.py tests/vibe3/roles/test_manager.py tests/vibe3/config/test_migrated_config_paths.py tests/vibe3/execution/test_execution_role_policy.py
```

Expected: manager bootstrap/retry 路径都通过，settings 不再声明该字段。

- [ ] **Step 7: 提交**

```bash
git add config/prompts/prompt-recipes.yaml config/v3/settings.yaml src/vibe3/roles/manager.py src/vibe3/config/orchestra_config.py tests/vibe3/roles/test_manager.py tests/vibe3/config/test_migrated_config_paths.py tests/vibe3/execution/test_execution_role_policy.py
git commit -m "refactor(prompt): move manager supervisor source into recipe"
```

---

### Task 3: 为 supervisor_handoff 增加直属 template recipe，删除 governance override

**Files:**
- Modify: `config/prompts/prompt-recipes.yaml`
- Modify: `config/v3/settings.yaml`
- Modify: `src/vibe3/roles/supervisor.py`
- Modify: `src/vibe3/config/orchestra_config.py`
- Modify: `tests/vibe3/roles/test_supervisor.py`

- [ ] **Step 1: 写 supervisor 直属 recipe 测试**

在 `tests/vibe3/roles/test_supervisor.py` 增加一个测试，验证 handoff 不再改写 governance config：

```python
def test_build_supervisor_handoff_payload_uses_supervisor_recipe(tmp_path):
    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  supervisor.handoff:
    kind: template_recipe
    template_key: orchestra.supervisor.apply
    variables:
      supervisor_name:
        kind: literal
        value: supervisor/apply.md
      supervisor_content:
        kind: literal
        value: APPLY BODY
""",
        encoding="utf-8",
    )

    prompt, _, _ = build_supervisor_handoff_payload(..., prompts_path=...)
    assert "APPLY BODY" in prompt
```

并删除/替换当前 `test_overrides_governance_config` 断言。

- [ ] **Step 2: 运行 supervisor 测试确认当前路径失败**

Run:

```bash
uv run pytest tests/vibe3/roles/test_supervisor.py -q
```

Expected: 现有实现仍依赖 governance override，新增测试失败。

- [ ] **Step 3: 在 recipe 中增加 supervisor handoff template recipe**

在 `config/prompts/prompt-recipes.yaml` 新增：

```yaml
supervisor.handoff:
  kind: template_recipe
  template_key: orchestra.supervisor.apply
  variables:
    supervisor_name:
      kind: literal
      value: supervisor/apply.md
    supervisor_content:
      kind: file
      path: supervisor/apply.md
```

- [ ] **Step 4: 重写 supervisor payload 构建逻辑**

修改 `src/vibe3/roles/supervisor.py`：

- 删除 `governance_cfg = config.governance.model_copy(...)`
- 删除 `handoff_config = config.model_copy(...)`
- 新增一个直属 recipe 渲染路径，例如：

```python
manifest = PromptManifest.load_default()
recipe_def = manifest.recipe("supervisor.handoff")
recipe = PromptRecipe(
    template_key=recipe_def.template_key,
    variables=recipe_def.variables,
    description=recipe_def.description,
)
registry = _build_runtime_registry(snapshot_context)
assembler = PromptAssembler(prompts_path=prompts_path or DEFAULT_PROMPTS_PATH, registry=registry)
rendered = assembler.render(recipe, runtime_context=snapshot_context)
```

同时更新 `build_supervisor_task_string()`，不要再从
`config.supervisor_handoff.supervisor_file` 取文件名，而是从 recipe literal/source 提供稳定显示值；如果短期不想加 manifest helper，就把 task string 改成不回显具体 supervisor 文件名：

```python
return (
    f"Process governance issue #{issue_number}{repo_hint}: {title}\n"
    "This issue has already been handed to the configured supervisor material "
    "by the trigger layer.\n"
    ...
)
```

- [ ] **Step 5: 删除 settings/orchestra_config 中 supervisor_handoff prompt 材料字段**

修改：

- `config/v3/settings.yaml` 删除 `orchestra.supervisor_handoff.supervisor_file`
- `src/vibe3/config/orchestra_config.py` 删除 `SupervisorHandoffConfig.supervisor_file`

保留 `prompt_template` 仅作为兼容桥接一轮；如果实现中 recipe 已完全接管，可同时删除它并将 template key 固化到 recipe。

- [ ] **Step 6: 运行回归测试**

Run:

```bash
uv run pytest tests/vibe3/roles/test_supervisor.py tests/vibe3/config/test_migrated_config_paths.py -q
uv run ruff check src/vibe3/roles/supervisor.py src/vibe3/config/orchestra_config.py tests/vibe3/roles/test_supervisor.py
```

Expected: supervisor handoff 渲染路径不再依赖 governance override。

- [ ] **Step 7: 提交**

```bash
git add config/prompts/prompt-recipes.yaml config/v3/settings.yaml src/vibe3/roles/supervisor.py src/vibe3/config/orchestra_config.py tests/vibe3/roles/test_supervisor.py tests/vibe3/config/test_migrated_config_paths.py
git commit -m "refactor(prompt): give supervisor handoff a direct recipe"
```

---

### Task 4: 把 governance prompt 材料目录迁入 recipe，仅保留 tick 选择在 Python

**Files:**
- Modify: `config/prompts/prompt-recipes.yaml`
- Modify: `config/v3/settings.yaml`
- Modify: `src/vibe3/roles/governance.py`
- Modify: `src/vibe3/config/orchestra_config.py`
- Modify: `tests/vibe3/roles/test_governance.py`
- Modify: `tests/vibe3/config/test_migrated_config_paths.py`

- [ ] **Step 1: 写 governance material catalog 测试**

在 `tests/vibe3/roles/test_governance.py` 增加一个测试，验证 tick 选择来自 recipe catalog 而不是 config field：

```python
def test_build_governance_recipe_uses_recipe_material_catalog(tmp_path, monkeypatch):
    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  governance.scan:
    kind: template_recipe
    template_key: orchestra.governance.plan
    material_catalog:
      - name: supervisor/governance/assignee-pool.md
        source:
          kind: file
          path: supervisor/governance/assignee-pool.md
      - name: supervisor/governance/roadmap-intake.md
        source:
          kind: file
          path: supervisor/governance/roadmap-intake.md
""",
        encoding="utf-8",
    )

    recipe = build_governance_recipe(_make_config(), tick_count=1, recipes_path=recipes_path)
    assert recipe.variables["supervisor_name"].value == "supervisor/governance/roadmap-intake.md"
```

- [ ] **Step 2: 运行 governance 测试确认当前实现失败**

Run:

```bash
uv run pytest tests/vibe3/roles/test_governance.py -q
```

Expected: 当前实现仍调用 `config.governance.get_supervisor_materials()`，新增测试失败。

- [ ] **Step 3: 在 recipe 中增加 governance template recipe 和 material catalog**

在 `config/prompts/prompt-recipes.yaml` 新增或重构为：

```yaml
governance.scan:
  kind: template_recipe
  template_key: orchestra.governance.plan
  material_catalog:
    - name: supervisor/governance/assignee-pool.md
      source:
        kind: file
        path: supervisor/governance/assignee-pool.md
    - name: supervisor/governance/roadmap-intake.md
      source:
        kind: file
        path: supervisor/governance/roadmap-intake.md
    - name: supervisor/governance/cron-supervisor.md
      source:
        kind: file
        path: supervisor/governance/cron-supervisor.md
```

- [ ] **Step 4: 改写 governance recipe 构造逻辑**

修改 `src/vibe3/roles/governance.py`：

- `build_governance_recipe()` 增加可选 `recipes_path: Path | None = None`
- 不再从 `config.governance.get_supervisor_materials()` 取列表
- 改为从 `PromptManifest.load(...).recipe("governance.scan")` 取 material catalog
- tick 选择仍保留在 Python：

```python
recipe_def = manifest.recipe("governance.scan")
materials = recipe_def.material_catalog
current = materials[tick_count % len(materials)]
variables = {
    "supervisor_name": PromptVariableSource(kind=VariableSourceKind.LITERAL, value=current.name),
    "supervisor_content": current.source,
    ...
}
```

- [ ] **Step 5: 删除 settings/orchestra_config 中 governance prompt 材料字段**

修改：

- `config/v3/settings.yaml` 删除 `orchestra.governance.supervisor_file`
- `config/v3/settings.yaml` 删除 `orchestra.governance.supervisor_files`
- `src/vibe3/config/orchestra_config.py` 删除 `GovernanceConfig.supervisor_file`、`supervisor_files`、`get_supervisor_materials()`

保留：

- `prompt_template` 一轮兼容或直接删除，取决于 Task 3 的 recipe 化程度
- `interval_ticks`
- `enabled`
- `dry_run`
- agent/backend/model

- [ ] **Step 6: 运行回归测试**

Run:

```bash
uv run pytest tests/vibe3/roles/test_governance.py tests/vibe3/config/test_migrated_config_paths.py -q
uv run mypy src/vibe3/roles/governance.py src/vibe3/config/orchestra_config.py
```

Expected: governance tick 轮换仍正确，settings 已不包含材料路径。

- [ ] **Step 7: 提交**

```bash
git add config/prompts/prompt-recipes.yaml config/v3/settings.yaml src/vibe3/roles/governance.py src/vibe3/config/orchestra_config.py tests/vibe3/roles/test_governance.py tests/vibe3/config/test_migrated_config_paths.py
git commit -m "refactor(prompt): move governance materials into recipe catalog"
```

---

### Task 5: 清理遗留兼容层，更新文档和全量定向回归

**Files:**
- Modify: `src/vibe3/execution/execution_role_policy.py`
- Modify: `config/README.md`
- Modify: `config/v3/registry.yaml`
- Modify: `docs/superpowers/specs/2026-05-04-prompt-config-unification-design.md`（如实现细节与设计文字需同步）

- [ ] **Step 1: 删除 execution policy 中对 prompt 材料字段的感知**

修改 `src/vibe3/execution/execution_role_policy.py`：

```python
@dataclass(frozen=True)
class PromptContract:
    template: str


def resolve_prompt_contract(self, role: str) -> PromptContract:
    ...
    return PromptContract(template=template)
```

目标：execution policy 只知道 template selector，不知道 `supervisor_file` 之类 prompt 材料字段。

- [ ] **Step 2: 更新配置说明文档**

更新 `config/README.md` 和 `config/v3/registry.yaml`，明确：

- `settings.yaml` 不再拥有 supervisor prompt material path
- `prompt-recipes.yaml` 现在同时拥有 section order 与 material sources
- `manager` 使用 `section_recipe`
- `governance/supervisor_handoff` 使用 `template_recipe`

- [ ] **Step 3: 运行完整定向回归**

Run:

```bash
uv run pytest \
  tests/vibe3/prompts/test_prompt_manifest.py \
  tests/vibe3/prompts/test_models.py \
  tests/vibe3/prompts/test_assembler.py \
  tests/vibe3/roles/test_manager.py \
  tests/vibe3/roles/test_supervisor.py \
  tests/vibe3/roles/test_governance.py \
  tests/vibe3/config/test_migrated_config_paths.py \
  tests/vibe3/execution/test_execution_role_policy.py -q
```

Expected: 全部通过。

- [ ] **Step 4: 运行代码质量检查**

Run:

```bash
uv run ruff check src/vibe3/prompts src/vibe3/roles src/vibe3/config tests/vibe3/prompts tests/vibe3/roles tests/vibe3/config
uv run mypy src/vibe3/prompts src/vibe3/roles src/vibe3/config
```

Expected: 无 lint/type 问题。

- [ ] **Step 5: 最终提交**

```bash
git add src/vibe3/execution/execution_role_policy.py config/README.md config/v3/registry.yaml docs/superpowers/specs/2026-05-04-prompt-config-unification-design.md
git commit -m "docs: finalize prompt config unification cleanup"
```

---

## Self-Review

- Spec coverage:
  - 已覆盖 schema 扩展、manager 迁移、supervisor_handoff 直属 recipe、governance material catalog、settings 清理、文档更新与回归验证。
- Placeholder scan:
  - 计划中没有 `TODO/TBD`，所有任务都给出了目标文件、测试入口和验证命令。
- Type consistency:
  - 统一使用 `section_recipe` / `template_recipe` 两个术语。
  - manager 仍通过 `PromptManifest` 选 variant。
  - governance/supervisor_handoff 统一使用 template recipe + `PromptRecipe` 实例渲染。
