# Claude Code & OpenCode 使用进阶建议

完成安装和配置后，你可以使用 **Vibe Coding 控制中心** 作为统一入口。

## 0. 🚀 Start Here: The Vibe Coding Launcher (`vibecoding.sh`)
这是你的 "Vibe Coding" 控制中心。它可以一键启动新项目、安装/更新工具、以及运行环境诊断。

- **Run**: `./scripts/vibecoding.sh`
- **功能**:
    - **Ignition**: 极速启动新项目（自动配置 Rules 和 Context）。
    - **Equip**: 一键安装/更新 Claude Code 和 OpenCode。
    - **Diagnostics**: 检查 API Key 和环境状态。

## 0.5 🔐 安全配置 (Required)
首次使用前：

1. 进入仓库的 `config` 目录。
2. 复制模板：`cp keys.template.env keys.env`
3. 编辑 `keys.env` 填入你的 Token 和 Key。
4. 运行 `source config/aliases.sh` 或重新运行安装脚本来生效。

> [!IMPORTANT]
> **不要将 `keys.env` 提交到版本控制系统！** 它已默认包含在 .gitignore 中。

## 1. 核心别名与快捷命令
别名现在通过 `config/aliases.sh` 统一管理。
脚本会自动配置以下别名（需 `source ~/.zshrc`）：

- `c`: 启动 `claude` 交互界面。
- `ca "问题"`: 快速向 Claude 提问（无需进入交互模式）。
- `cr`: 让 Claude 审查当前改动。
- `o`: 启动 `opencode`。
- `oa "问题"`: 向 OpenCode 快速提问。
- `vibe`: Start Vibe Coding Control Center (`vibe` dispatcher -> `scripts/vibecoding.sh`)
- `x`: （可选）启动 `codex`（如已安装 OpenAI Codex CLI）。
- `xy`: （可选）`codex --yes` 自动执行（如已配置）。

## 2. 增强的安全特性
新版脚本包含多种安全增强功能：
- **输入验证**: 所有用户输入都经过验证以防止注入攻击
- **路径验证**: 防止目录遍历攻击
- **安全文件操作**: 包含安全的文件复制和写入函数
- **环境验证**: 检查命令可用性和目录权限
- **安全用户交互**: 安全的提示和确认功能

## 3. 善用 `CLAUDE.md` (项目级上下文)
在每个项目的根目录下创建一个 `CLAUDE.md` 文件。即使里面只有几行字，也能极大提升 AI 的准确度：
- **构建命令**：告诉它如何跑 `npm run dev` 或 `make`。
- **测试命令**：告诉它如何跑 `npm test`。
- **代码风格**：定义项目的缩进、命名规范等。
> [!TIP]
> 运行 `c` 进交互模式后，你可以直接说 "Generate a CLAUDE.md for this project"，它会自动扫描并创建。

## 4. 实时联网与搜索 (MCP)
脚本已为你集成了 **Brave Search** 和 **Google Generative AI**（通过 MCP）。
- 当你需要查阅最新的 API 文档（如 Next.js 15 或新的模型参数）时，直接在对话中说："Search Brave for the latest Next.js 15 routing documentation"。
- AI 会自动调用 MCP 工具进行联网搜索，结果比训练数据更准确。

## 5. 调试与报错处理
- **一键修复**：遇到报错时，直接复制报错信息给 Claude，或者运行 `claude "fix the error in last command"`。
- **Tmux 提醒**：如果你看到 "[Hook] BLOCKED" 提示，说明你在非 tmux 环境下尝试运行 dev server。这是为了防止 AI 丢失进程控制权。请按提示使用 `tmux`。

## 6. Google Generative AI (Gemini) MCP
如果在 `keys.env` 中配置了 `GOOGLE_GENERATIVE_AI_API_KEY`，安装脚本会生成对应 MCP 服务配置。
- **用法示例**：`Ask Gemini to analyze this complex logic`
- **适用场景**：超长上下文、多模态任务或复杂推理时的辅助分析

## 7. oh-my-opencode "ulw" 魔法 (Ultrawork)
当你使用 OpenCode 时，可以在 Prompt 中加入 `ulw` 关键词：
- **全自动模式**：`ulw` (Ultrawork) 会触发高强度自动化模式。AI 将自主进行：代码调研 -> 并行搜索 -> 方案实现 -> 自动测试。
- **使用示例**：`o "ulw 为项目添加用户登录功能"`
- **适用场景**：当你希望 AI “闭嘴干活”，直接把任务从 0 完成到 100% 时使用。

## 8. 项目一键初始化 (`init-project.sh`)
当你开始一个新项目时，在项目根目录下运行这个脚本：
- **功能**：自动创建 `.cursor/rules` 并复制通用规则，生成 `CLAUDE.md` 模板。
- **意义**：这会让 Cursor 和 Claude 立即理解你的项目结构和规范，减少"幻觉"。

## 9. AI 友好型脚手架 (Scaffolding)
为了让 AI 工具发挥最大威力，推荐使用以下脚手架起手：
- **[Next.js + Shadcn UI](https://ui.shadcn.com/)**：AI 对 Shadcn 的理解非常透彻，生成的 UI 代码质量极高。
- **[T3 Stack](https://create.t3.gg/)**：利用 tRPC 和 Prisma 提供端到端的类型安全。
- **[Achromatic](https://achromatic.dev/)**：专门为 AI 时代设计的 SaaS 启动模板。
- **[FastAPI](https://fastapi.tiangolo.com/)**：Python 后端的首选，强类型提示让 AI 写接口变得极其简单。

## 10. 多模型切换
如果你发现 Qwen 在处理极其复杂的逻辑（如大规模重构）时不够理想：
- 可以使用环境变量临时切换：`ANTHROPIC_MODEL=claude-3-7-sonnet-latest claude`。
- OpenCode 侧可通过配置对应厂商 API Key 切换不同模型（如 DeepSeek / Moonshot）。

## 11. 安全最佳实践
- 始终使用提供的验证函数来处理用户输入
- 检查所有外部资源的访问权限
- 定期更新 API 密钥并验证其有效性
- 使用 `secure_write_file` 函数安全地写入配置文件
- 在处理路径时始终使用 `validate_path` 函数防止路径遍历攻击
