# Prompts

Prompt 模板组装层，加载模板、解析变量、记录 provenance，并逐步把角色
prompt 的装配顺序从 Python 代码迁移到配置文件。

## 职责

- 加载文本模板（config/prompts.yaml）
- 加载装配表（config/prompt-recipes.yaml）
- 注册和解析变量 provider（code/git/config 来源）
- 组装最终 prompt（变量替换 + 段落拼接）
- 记录变量 provenance（用于审计追踪）
- 支持通过命令 dry-run 查看运行时 prompt

## 关键组件

| 文件 | 职责 |
|------|------|
| assembler.py | PromptAssembler 主拼装器 |
| manifest.py | 装配表加载、variant 解析、section 渲染 |
| template_loader.py | 模板文件加载 |
| builtin_providers.py | 内置变量 provider |
| provider_registry.py | Provider 注册中心 |
| context_builder.py | 运行时上下文构建 |
| models.py | PromptRecipe, PromptRenderResult |
| validation.py | 模板校验 |

## 配置关系

`config/prompts.yaml` 保留实际 prompt 文本、模板和说明。
`config/prompt-recipes.yaml` 回答“某个 prompt variant 使用哪些 section、什么顺序”。
当前 `run.*` 已由 recipe 驱动；`plan.*` / `review.*` 先记录目标装配形态，
待对应 builder 迁移后再成为运行时真源。

## 依赖关系

- 依赖: clients (GitClient, 获取 git 上下文), config, analysis
- 被依赖: agents (prompt 构建), manager (manager prompts)
