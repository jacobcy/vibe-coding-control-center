# Prompts

Prompt 模板组装层，加载模板、解析变量、记录 provenance，并从配置文件
读取角色 prompt 的装配顺序。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 1 | 模块初始化 |
| provider_registry.py | 34 | Provider 注册中心，变量解析分发 |
| exceptions.py | 56 | 模块专用异常定义 |
| models.py | 73 | PromptRecipe, PromptRenderResult 等数据模型 |
| context_builder.py | 93 | 运行时上下文构建，配置注入 |
| assembler.py | 113 | PromptAssembler 主拼装器，模板变量替换 |
| builtin_providers.py | 130 | 内置变量 provider（git/code/config 来源） |
| template_loader.py | 154 | 模板文件加载，YAML 解析 |
| manifest.py | 170 | 装配表加载、variant 解析、section 渲染 |
| validation.py | 232 | 模板校验，变量检查 |

截至 2026-05，总计约 1056 行。

## 职责

- 加载文本模板（config/prompts/prompts.yaml）
- 加载装配表（config/prompts/prompt-recipes.yaml）
- 注册和解析变量 provider（code/git/config 来源）
- 组装最终 prompt（变量替换 + 段落拼接）
- 记录变量 provenance（用于审计追踪）
- 支持通过命令 dry-run 查看运行时 prompt

## 关键组件

### assembler.py
**PromptAssembler** 是核心拼装器，负责：
1. 加载模板文件
2. 解析变量引用（`{{variable}}` 语法）
3. 调用 ProviderRegistry 解析变量值
4. 执行变量替换并记录 provenance
5. 返回 PromptRenderResult（含最终文本和变量来源追踪）

### provider_registry.py
**ProviderRegistry** 是变量解析中心：
1. 维护 variable name → provider function 映射
2. 支持动态注册 provider
3. 变量解析时按优先级查找 provider
4. 提供变量缺失时的错误信息

### manifest.py
负责装配表的加载和解析：
1. 从 `config/prompt-recipes.yaml` 加载配方
2. 解析 variant（如 `plan.default` vs `plan.detailed`）
3. 按 section 顺序渲染段落
4. 支持条件性包含段落

### builtin_providers.py
提供内置变量解析器：
- `git_*`: Git 相关变量（branch, commit, status）
- `code_*`: 代码分析变量
- `config_*`: 配置文件变量
- `env_*`: 环境变量

## 配置关系

`config/prompts/prompts.yaml` 保留实际 prompt 文本、模板和说明。
`config/prompts/prompt-recipes.yaml` 回答”某个 prompt variant 使用哪些 section、什么顺序”。
当前 `run.*` / `plan.*` / `review.*` 均由 recipe 驱动。

## 依赖关系

```
prompts/
├── assembler.py → builtin_providers, exceptions, models, provider_registry, template_loader
├── builtin_providers.py → exceptions, models, provider_registry
├── context_builder.py → assembler, models, provider_registry
├── validation.py → assembler, models, provider_registry, template_loader
└── 其他模块：无内部依赖（exceptions, models, provider_registry, template_loader, manifest）
```

**外部依赖**:
- loguru: 日志记录
- pydantic: 数据模型
- yaml: 配置文件解析
- vibe3.exceptions: VibeError 基类
- vibe3.services.flow_service: Git common dir 解析（builtin_providers，条件导入）

**被依赖**:
- agents/: prompt 构建
- manager/: manager prompts
- commands/: dry-run 命令
