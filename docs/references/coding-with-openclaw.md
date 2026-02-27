## **完整的8步工作流程**

让我通过上周的一个真实案例来讲解。

### **第 1 步：客户请求→使用 Zoe 进行范围界定**

我接到了一个机构客户的电话。他们希望重用团队已经设置好的配置。

通话后，我和 Zoe 讨论了这项请求。由于我所有的会议笔记都会自动同步到我的 Obsidian 库中，我这边无需做任何解释。**我们一起梳理了功能范围——最终确定了一个模板系统，让他们能够保存和编辑现有的配置**。

然后 Zoe 做了三件事：

- 1.充值积分以立即解除客户限制——她有管理员 API 访问权限
- 2.从生产数据库中获取客户配置 — 她有只读的生产数据库访问权限（我的 Codex 代理永远不会拥有这种权限），用于检索他们现有的设置，这些设置会包含在提示中
- 3.生成一个 Codex 代理——带有包含所有上下文的详细提示

### **步骤2：生成agent**

每个代理都有自己的工作树（隔离分支）和 [tmux](https://zhida.zhihu.com/search?content_id=270665735&content_type=Article&match_order=1&q=tmux&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3NzIzOTQ0MDUsInEiOiJ0bXV4IiwiemhpZGFfc291cmNlIjoiZW50aXR5IiwiY29udGVudF9pZCI6MjcwNjY1NzM1LCJjb250ZW50X3R5cGUiOiJBcnRpY2xlIiwibWF0Y2hfb3JkZXIiOjEsInpkX3Rva2VuIjpudWxsfQ.2uXGJIz_aF34qOqW4iQY3nykMC8y86i-NHFEum11i1w&zhida_source=entity) 会话：

`# Create worktree + spawn agent
git worktree add ../feat-custom-templates -b feat/custom-templates origin/main
cd ../feat-custom-templates && pnpm install

tmux new-session -d -s "codex-templates" \
  -c "/Users/elvis/Documents/GitHub/medialyst-worktrees/feat-custom-templates" \
  "$HOME/.codex-agent/run-agent.sh templates gpt-5.3-codex high"`

该代理在 tmux 会话中运行，并通过脚本实现完整的终端日志记录。 我们启动代理的方式如下：

`# Codex
codex --model gpt-5.3-codex \
  -c "model_reasoning_effort=high" \
  --dangerously-bypass-approvals-and-sandbox \
  "Your prompt here"

# Claude Code  
claude --model claude-opus-4.5 \
  --dangerously-skip-permissions \
  -p "Your prompt here"`

我以前使用 codex exec 或 claude -p，但最近切换到 tmux：

tmux 要远好得多，因为任务中途重定向功能强大。代理跑偏了方向？不要杀死它：

`# Wrong approach:
tmux send-keys -t codex-templates "Stop. Focus on the API layer first, not the UI." Enter

# Needs more context:
tmux send-keys -t codex-templates "The schema is in src/types/template.ts. Use that." Enter`

任务在 .clawdbot/active-tasks.json 中被跟踪：

`{
  "id": "feat-custom-templates",
  "tmuxSession": "codex-templates",
  "agent": "codex",
  "description": "Custom email templates for agency customer",
  "repo": "medialyst",
  "worktree": "feat-custom-templates",
  "branch": "feat/custom-templates",
  "startedAt": 1740268800000,
  "status": "running",
  "notifyOnComplete": true
}`

完成后，它会更新 PR 编号和检查状态。（更多内容见步骤 5）

`{
  "status": "done",
  "pr": 341,
  "completedAt": 1740275400000,
  "checks": {
    "prCreated": true,
    "ciPassed": true,
    "claudeReviewPassed": true,
    "geminiReviewPassed": true
  },
  "note": "All checks passed. Ready to merge."
}`

### **步骤3：循环监控**

一个 cron 任务每 10 分钟运行一次来照看所有代理。这基本上就像一个改进的 [Ralph 循环](https://zhida.zhihu.com/search?content_id=270665735&content_type=Article&match_order=1&q=Ralph+%E5%BE%AA%E7%8E%AF&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3NzIzOTQ0MDUsInEiOiJSYWxwaCDlvqrnjq8iLCJ6aGlkYV9zb3VyY2UiOiJlbnRpdHkiLCJjb250ZW50X2lkIjoyNzA2NjU3MzUsImNvbnRlbnRfdHlwZSI6IkFydGljbGUiLCJtYXRjaF9vcmRlciI6MSwiemRfdG9rZW4iOm51bGx9.HA4XD70re25fN14XMnLgb0tQ3Fn9tlHm2vWdh-0ndEg&zhida_source=entity)，后面会详细说明。

但它不会直接轮询代理——那会非常昂贵。相反，它运行一个脚本，该脚本读取 JSON 注册表并检查：

`.clawdbot/check-agents.sh`

该脚本是完全确定性的，并且极其高效：

- 检查 tmux 会话是否存活
- 检查跟踪分支上的打开的 PR
- 通过 gh cli 检查 CI 状态
- 如果 CI 失败或关键评审反馈，自动重新生成失败的agent（最多 3 次尝试）
- 只有在需要人工关注时才发出警报

> 我不看终端。系统会告诉我何时查看。
> 

### **步骤 4：代理创建 PR**

agent通过`gh pr create --fill`提交、推送并打开 PR。此时我不会收到通知——单独的 PR 并未完成。

完成的定义（非常重要，你的代理需要知道这一点）：

- 创建了 PR
- 分支已同步到主分支（无合并冲突）
- 持续集成通过（代码风格检查、类型检查、单元测试、端到端测试）
- Codex 审查通过
- Claude Code 审查通过
- Gemini 审查通过
- 包含截图（如果 UI 有变化）

### **步骤5：自动代码审查**

每个 PR 都会由三个 AI 模型进行审查。它们捕捉到不同的事物：

- `Codex Reviewer` — 在边缘案例方面表现优异。进行最彻底的审查。能捕捉逻辑错误、缺失的错误处理、竞态条件。误报率非常低。
- `Gemini Code Assist Reviewer` — 免费且极其有用。能捕捉其他代理遗漏的安全问题、可扩展性问题。并建议具体的修复方案。安装毫无疑虑。
- `Claude Code Reviewer` — 基本无用——倾向于过度谨慎。大量建议"考虑添加..."，通常属于过度设计。除非标记为关键，否则我直接跳过。它很少能自行发现关键问题，但会验证其他审查者标记的问题。 所有三个帖子评论都直接针对该拉取请求。

### **第六步：自动化测试**

我们的 CI 流水线运行大量自动化测试：

- 代码风格检查和 TypeScript 检查
- 单元测试
- 端到端测试
- 在预览环境中运行 [Playwright](https://zhida.zhihu.com/search?content_id=270665735&content_type=Article&match_order=1&q=Playwright&zd_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJ6aGlkYV9zZXJ2ZXIiLCJleHAiOjE3NzIzOTQ0MDUsInEiOiJQbGF5d3JpZ2h0IiwiemhpZGFfc291cmNlIjoiZW50aXR5IiwiY29udGVudF9pZCI6MjcwNjY1NzM1LCJjb250ZW50X3R5cGUiOiJBcnRpY2xlIiwibWF0Y2hfb3JkZXIiOjEsInpkX3Rva2VuIjpudWxsfQ.d0EXIwE8REzn1SKO2gTaFKAVJy7MTBjv6mPOeDCcWi0&zhida_source=entity) 测试（与生产环境相同）

> 上周我添加了一条新规则：
> 
> 
> **如果 PR 修改了任何 UI，必须在 PR 描述中包含截图。否则 CI 会失败。这大大缩短了审查时间——我可以直接看到具体的变化，无需点击预览**
> 

### **步骤 7：人工审查**

现在我看到 Telegram 通知："PR #341 已准备好进行审核。" 此时：

- CI 通过
- 三位 AI 审核员批准了代码
- 截图展示了 UI 的变化
- 所有边界情况都在审核评论中记录 我的审核需要 5-10 分钟。我合并很多 PR 时不需要阅读代码——截图展示了我所需要的一切

### **步骤8：合并**

PR 合并。每天有一个 cron 任务清理孤立的 worktrees 和任务注册 json。

## **The Ralph Loop V2**

> Ralph循环从内存中
> 
> 
> **提取上下文，生成输出，评估结果，保存学习成果**
> 

我们的系统不同。当agent失败时，Zoe 不会用相同的提示重新生成它。她会查看完整的业务上下文，并找出如何解除阻塞它的方法：

- 代理上下文用完了？“只关注这三个文件。”
- 代理走错了方向？“停止。客户想要的是 X，不是 Y。这是他们在会议中说的话。”
- 代理需要澄清？“这是客户的电子邮件以及他们公司是做什么的。”

> Zoe 帮助代理完成工作。她拥有代理所不具备的上下文信息——
> 
> 
> ```
> 客户历史记录、会议笔记、我们之前尝试过的方法以及失败的原因。她利用这些信息在每次重试时编写更好的提示
> ```
> 

但她也不需要我分配任务。她会主动寻找工作：

- `早上`： **扫描 Sentry → 发现 4 个新错误 → 启动 4 个代理进行调查和修复**
- `会议后`： **扫描会议笔记 → 标记 3 个客户提到的功能请求 → 启动3个Codex代理**
- `晚上`： **扫描 git 日志 → 启动 Claude Code 更新变更日志和客户文档**

> 我接完客户电话后散步回来。回到 Telegram 上看到："7 个 PR 已准备好审核。3 个新功能，4 个 bug 修复。"
> 

当agent成功时，模式会被记录下来。"这种提示结构适用于计费功能。" "Codex 需要提前提供类型定义。" "始终包含测试文件路径。" 奖励信号是：CI 通过、所有三个代码审核通过、人工合并。任何失败都会触发循环。随着时间的推移，Zoe 写出的提示会更好，因为她记得哪些已经发布。

## **选择合适的agent**

并非所有编程agent都一样。快速参考：

- Codex 是我的主力。**后端逻辑、复杂错误、多文件重构、任何需要跨代码库推理的任务。它较慢但全面。我用于 90%的任务**。
- Claude Code 更快，更适合前端工作。**它权限问题也更少，因此非常适合 git 操作。（我过去更多用它来驱动日常工作，但现在 Codex 5.3 明显更好、更快）**
- Gemini有不同的超能力——设计感。为了制作美观的 UI 界面，我会先让文生生成 HTML/CSS 规范，然后交给 Claude Code 在我们的组件系统中实现。Gemini负责设计，Claude 负责构建。

> Zoe 为每项任务选择合适的代理，并在它们之间路由输出。账单系统错误会交给 Codex 处理。按钮样式修复交给 Claude Code。新的仪表板设计从 Gemini 开始。
> 

## **如何设置**

将这篇文章全部复制到 OpenClaw 中，并告诉它："为我实现这个代理群组设置。

它将读取架构，创建脚本，设置目录结构，并配置 cron 监控。10 分钟内完成。