下面给出一套工程级 codex review 使用体系。目标是：让代码审查成为 自动化质量网关（quality gate），而不是临时工具。

结构分为四层：
	1.	Review Policy
	2.	本地开发审查
	3.	PR Gate
	4.	CI 自动审计

⸻

1. Review Policy（审查规则文件）

不要把 prompt 写在命令行。
应该固化为一个 review policy 文件。

例如：

.codex/review-policy.md

示例：

Code Review Policy

Focus areas:

1. Correctness
   - logic bugs
   - race conditions
   - unsafe state mutation

2. Security
   - command injection
   - unsafe shell usage
   - secrets leakage

3. Performance
   - unnecessary allocations
   - N^2 algorithms
   - blocking IO

4. Architecture
   - consistency with repo structure
   - CLI UX compatibility
   - dependency misuse

5. Code health
   - dead code
   - unclear naming
   - missing error handling

Output format:

- Critical
- Major
- Minor
- Suggestions

调用方式：

codex review - < .codex/review-policy.md

优点：
	•	review 规则稳定
	•	CI 与本地一致
	•	团队统一审查标准

⸻

2. 本地开发审查（Developer loop）

开发阶段建议使用 uncommitted review。

codex review --uncommitted

配合 policy：

codex review --uncommitted - < .codex/review-policy.md

效果：

审查范围：

staged
unstaged
untracked

适合：
	•	commit 前
	•	debug 逻辑错误
	•	shell / CLI 安全检查

⸻

3. Commit Review（逐 commit 审查）

用于：

git bisect
历史 bug

示例：

codex review --commit HEAD

或：

codex review --commit HEAD~1

结合 policy：

codex review --commit HEAD - < .codex/review-policy.md


⸻

4. PR Review（核心用法）

PR 审查需要对比 base branch。

codex review --base main

实际 diff：

git diff main...HEAD

推荐命令：

codex review \
  --base main \
  --title "PR Review" \
  - < .codex/review-policy.md


⸻

5. Git Hook 集成

pre-commit

.git/hooks/pre-commit

示例：

#!/bin/bash

echo "Running Codex Review..."

codex review --uncommitted \
  - < .codex/review-policy.md

作用：
	•	防止明显 bug 提交
	•	本地质量网关

⸻

pre-push

更严格：

#!/bin/bash

echo "Running Codex Review (push gate)..."

codex review --base main \
  - < .codex/review-policy.md


⸻

6. CI Pipeline 审查

GitHub Actions 示例：

.github/workflows/codex-review.yml

name: codex-review

on:
  pull_request:

jobs:
  review:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install Codex CLI
        run: npm install -g codex-cli

      - name: Run review
        run: |
          codex review \
            --base origin/main \
            - < .codex/review-policy.md


⸻

7. PR Gate（质量门）

CI 可以根据 review 输出决定：

allow merge / block merge

策略：

Level	行为
Critical	阻止 merge
Major	需要修复
Minor	可忽略
Suggestion	参考


⸻

8. 针对 CLI / Shell 项目的审查 Prompt

你现在项目是：

bash
CLI
Git wrapper
automation

更合适的 policy：

Shell Safety

Detect:

- unsafe rm
- unquoted variables
- glob expansion
- pipefail missing
- subshell bugs

Git Logic

Detect:

- detached HEAD issues
- branch overwrite
- unsafe merge

CLI UX

Detect:

- inconsistent flags
- missing help text
- silent failures


⸻

9. 与 Vibe Flow 体系结合

你的流程：

repo issue
task issue
flow
branch
PR

建议：

Execute 阶段

codex review --uncommitted


⸻

Review 阶段

codex review --base main


⸻

PR merge gate

CI 自动执行：

codex review --base origin/main


⸻

10. 高级技巧（少有人用）

Review diff pipeline

可以直接：

git diff main | codex review -

优点：
	•	不依赖 git repo context
	•	适合 CI

⸻

review staged only

git diff --cached | codex review -


⸻

review patch file

codex review - < patch.diff


⸻

11. 最实用的三条命令

开发阶段：

codex review --uncommitted

PR 前：

codex review --base main

CI：

codex review --base origin/main


⸻

一、codex review + Serena AST 怎么搭

1. 最合理的架构

不要让 Codex 直接“盲审” diff。
应该先让 Serena 产出一层结构化语义上下文，再让 Codex review 基于这层上下文审。

推荐链路：

git diff / PR diff
    ↓
Serena AST / symbol analysis
    ↓
生成 impact summary
    ↓
codex review 读取 diff + impact summary + review policy
    ↓
输出审计结论

也就是先回答三个问题：
	1.	这次改了哪些 symbol
	2.	这些 symbol 被谁引用
	3.	改动是否越过模块边界或破坏约束

这些正是 Serena 擅长的点：它提供 find_symbol、find_referencing_symbols、insert_after_symbol 这类 symbol-level 工具，而不是只靠 grep。 ￼

⸻

2. 为什么这比单独 codex review 强

单独 codex review 的问题不是“看不懂代码”，而是：
	•	diff 太大时，它容易只盯改动行，忽略调用方
	•	重构类 PR 里，它容易漏掉隐式影响面
	•	shell/CLI/多模块仓库中，它可能知道“这里可疑”，但不知道“波及半径多大”

Serena AST 补的正是这一层：
它不是给出最终判断，而是把语义影响面展开，让 Codex 少靠猜。Serena 官方就强调它通过 symbol-level 的关系结构来提升 token 效率和代码理解质量。 ￼

⸻

3. 具体落地方式

方案 A：本地脚本串联

你可以做一个脚本，例如：

scripts/review-with-serena.sh

流程：
	1.	拿到 diff 范围
	2.	用 Serena 找出改动涉及的 symbol
	3.	查这些 symbol 的引用点、定义点、邻近上下文
	4.	生成一个中间文件，例如：

.codex/impact-summary.md

内容类似：

Changed symbols:
- FlowStore.save_handoff
- BranchResolver.resolve_target
- merge_guard.validate_clean_worktree

Potential impact:
- save_handoff is referenced by:
  - flow execute
  - flow resume
  - flow close
- resolve_target is referenced by:
  - task start
  - pr open
- validate_clean_worktree is on the merge path only

Risk notes:
- save_handoff signature changed from 2 args to 3 args
- One caller still passes 2 args
- BranchResolver now prefers remote branch resolution before local fallback

然后：

cat .codex/review-policy.md .codex/impact-summary.md | codex review --base main -

这才是对的。
不是“让 Serena 替 Codex 审查”，而是“让 Serena 给 Codex 提供结构化证据”。

⸻

方案 B：做成 skill / gate

如果你走 repo-local skills，这种方式更稳。

OpenAI 官方最近就明确在自家 OSS 维护里用：
	•	AGENTS.md
	•	.agents/skills/
	•	GitHub Actions

来把 PR review、验证、发布准备之类流程固化进仓库。 ￼

你可以做两个 skill：

serena-impact-analysis

负责：
	•	提取 changed symbols
	•	展开引用图
	•	标注跨模块影响
	•	输出 impact summary

codex-review-gate

负责：
	•	读取 review policy
	•	读取 impact summary
	•	执行 codex review
	•	按严重级别决定是否 fail

这样分层最清楚，也最符合你现在这种 flow / handoff / gate 的体系。

⸻

4. 适合你项目的审查重点

你现在的仓库偏：
	•	CLI
	•	shell / git wrapper
	•	flow 状态机
	•	PR / branch / handoff 编排

这种项目最容易出的问题不是算法，而是：
	•	状态错乱
	•	参数传播断裂
	•	branch / worktree 边界错误
	•	handoff 写入和读取不一致
	•	shell quoting / path / glob 风险
	•	“看起来功能能跑，实际上异常路径坏了”

所以 Serena AST 最该做的不是“找性能热点”，而是做：

语义影响检查
	•	函数签名变了，调用方是否全更新
	•	enum / status 常量变了，状态机分支是否全覆盖
	•	CLI flag 变了，帮助文档、解析逻辑、调用层是否一致
	•	handoff schema 变了，读写两侧是否兼容

边界检查
	•	merge path 是否绕过 clean-worktree check
	•	close flow 是否仍可能误删 branch
	•	resume flow 是否还能正确恢复 handoff

这类问题，单纯 grep 很差，symbol 级分析更靠谱。

⸻

二、codex review 作为 merge gate 怎么做

这里先说结论：

可以做，但不能让它成为唯一 gate。

正确位置是：

lint / typecheck / tests / build
    ↓
Serena impact analysis
    ↓
codex review
    ↓
merge decision

也就是 codex review 应该是审计 gate，不是基础验证 gate。

⸻

1. 为什么不能单独当 gate

因为 codex review 再强，它本质上仍然是模型审查器，不是编译器，也不是测试框架。

它擅长发现：
	•	可疑逻辑
	•	设计退化
	•	异常路径缺失
	•	shell 危险写法
	•	调用链断裂风险
	•	review comments 难以人工一眼发现的问题

但它不擅长替代：
	•	类型系统
	•	单测/集测
	•	formatting/lint
	•	真正运行时行为验证

所以 merge gate 应该是双层：

硬 gate
	•	build
	•	lint
	•	tests
	•	maybe smoke tests

软转硬 gate
	•	Serena AST impact analysis
	•	codex review severity classification

也就是：
如果 Codex 判为 Critical/Major，就把它硬化成阻断。

⸻

2. 推荐的 merge gate 等级

你可以定四级：

级别	含义	merge 行为
Critical	明确 bug / 安全风险 / 数据破坏风险	直接阻断
Major	高概率缺陷 / 设计性回归 / API 不一致	默认阻断
Minor	代码味道 / 可维护性问题	不阻断，留言
Suggestion	风格或优化建议	不阻断

关键点在于：
	•	Critical 必须 block
	•	Major 建议 block，除非人工 override
	•	Minor / Suggestion 只评论不拦

否则开发体验会变差，团队很快会把 gate 关掉。

⸻

3. 最稳的 CI 结构

推荐 GitHub Actions 里拆成 3 个 job：

verify

跑：
	•	lint
	•	test
	•	build
	•	shellcheck / bats / whatever

impact-analysis

跑：
	•	Serena MCP / AST 分析
	•	生成 impact-summary.md

ai-review

跑：
	•	codex review --base origin/main
	•	输入 review policy + impact summary
	•	输出 machine-readable summary
	•	根据 severity exit 1 或 exit 0

这样好处是：
即使 AI review 出问题，基础验证仍然有独立结果，不会混成一锅。

⸻

4. 推荐的 gate 提示词结构

别写成空泛的“review this code”。

应该明确让它只做merge gate 视角：

You are the merge gate reviewer.

Review the diff against the base branch using:
1. repository review policy
2. semantic impact summary from Serena
3. changed files and git diff

Decide whether this PR should be:
- BLOCK
- WARN
- PASS

BLOCK only when you find:
- correctness bugs
- broken call sites
- unsafe shell or git operations
- state machine regressions
- user-visible CLI contract breakage
- missing handling on critical error paths

Return:
- verdict
- severity
- exact evidence
- affected symbols / files
- minimal fix direction

重点是让它输出：
	•	verdict
	•	evidence
	•	affected symbols
	•	fix direction

不要只要大段 prose。

⸻

5. 最关键的现实问题：误报

把 codex review 变成 merge gate，最大问题不是漏报，而是误报导致团队烦躁。

解决办法只有三个：

第一，缩审查范围

不要每次全仓审。
只审：
	•	PR diff
	•	受影响 symbols
	•	Serena 展开的引用链

第二，要求“证据化输出”

没有文件、行、symbol、调用链证据的结论，不进入 block。

第三，保留人工 override

比如 label 或 comment override：
	•	ai-review/override-major
	•	ai-review/accepted-risk

否则这个 gate 迟早被关。

⸻

三、你这个项目里最适合的 merge gate 规则

按你现在这个 gh wrapper / flow orchestration / handoff 项目，最值得 block 的不是通用“代码味道”，而是下面这些：

必须 block
	•	可能误删 branch / worktree / stash
	•	merge/close path 跳过 clean 状态检查
	•	handoff schema 改了但旧流程没兼容
	•	CLI 参数语义变化但调用链没同步
	•	shell 命令未 quote，存在路径/空格/glob 风险
	•	GitHub API / gh 命令失败时静默吞错
	•	flow 状态迁移可能进入非法状态

只 warn
	•	命名不统一
	•	帮助文档未更新
	•	小型重复逻辑
	•	可抽象未抽象

这个划分很重要。
你要的是工程真问题 gate，不是“AI 老师批作文”。

⸻

四、一个实用落地版本

你可以直接这么设计：

本地开发

codex review --uncommitted - < .codex/review-policy.md

PR 前
	1.	Serena 生成 impact summary
	2.	合并 policy + impact summary
	3.	执行：

cat .codex/review-policy.md .codex/impact-summary.md \
  | codex review --base main -

CI merge gate
	•	verify 必须过
	•	impact-analysis 生成摘要
	•	ai-review 输出 verdict
	•	BLOCK 或 Major 失败则禁止 merge

⸻

五、直说结论

codex review + Serena AST

这组合是对的，而且比单独用 codex review 强很多。原因不是 Serena 更聪明，而是它把“影响面”从字符串层拉到了 symbol 层，能明显减少盲审。Serena 官方就是按这种 IDE-like、symbol-level 辅助定位来的，也支持通过 MCP 接到 Codex 这类终端客户端。 ￼

codex review 作为 merge gate

能做，但只能做高层审计 gate，不能替代 build/lint/test。OpenAI 近几个月公开分享的 Codex 工作流，也是在 repo-local skills、GitHub Actions、PR review 这套可重复工程流程上发力，而不是把模型当唯一裁判。 ￼

最实在的建议

你这里最优解不是“让 Codex 自动审一切”，而是：

Serena 负责把影响面讲清楚，Codex 负责把风险讲明白，CI 负责把规则执行到底。

这套才稳。
