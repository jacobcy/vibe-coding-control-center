# Prompts

Prompt 模板组装层，加载模板、解析变量、记录 provenance。

## 职责

- 加载 Jinja2/文本模板（config/prompts.yaml）
- 注册和解析变量 provider（code/git/config 来源）
- 组装最终 prompt（变量替换 + 段落拼接）
- 记录变量 provenance（用于审计追踪）
- 模板验证

## 关键组件

| 文件 | 职责 |
|------|------|
| assembler.py | PromptAssembler 主拼装器 |
| recipe_service.py | Recipe 加载与管理 |
| template_loader.py | 模板文件加载 |
| builtin_providers.py | 内置变量 provider |
| provider_registry.py | Provider 注册中心 |
| context_builder.py | 运行时上下文构建 |
| models.py | PromptRecipe, PromptRenderResult |
| validation.py | 模板校验 |

## 依赖关系

- 依赖: clients (GitClient, 获取 git 上下文), config, analysis
- 被依赖: agents (prompt 构建), manager (manager prompts)
