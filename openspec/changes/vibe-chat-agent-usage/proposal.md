# Proposal: Vibe Chat - Agent Usage Guide

## 背景

用户需要快速了解各个 AI agent（codex, copilot 等）的命令行使用方法。v1 版本有 `vibe chat` 功能，但 v2 版本缺失。

## 目标

创建 `vibe chat` 命令，提供：
1. **Agent 使用指南** - 显示 codex, copilot 等工具的常用命令
2. **交互式选择** - 让用户选择要使用的 agent
3. **一键启动** - 直接启动选定的 agent

## 使用场景

1. 用户想知道如何使用 codex 进行代码审查
2. 用户需要查看 copilot 的常用参数
3. 用户想快速启动某个 agent

## 实现方案

### 1. 新增 `vibe chat` 命令

**语法**:
```bash
vibe chat [--agent=<name>]
```

**参数**:
- `--agent=codex` - 显示 codex 使用指南
- `--agent=copilot` - 显示 copilot 使用指南
- `--agent=<other>` - 支持其他 agent

**无参数时**:
- 显示所有可用 agent 列表
- 交互式选择

### 2. Agent 配置文件

创建 `.agent/agents.yml` 或 `.agent/agents.json`:

```yaml
agents:
  codex:
    name: OpenAI Codex
    install: npm install -g @openai/codex
    description: Professional code review and analysis
    commands:
      review: codex review --uncommitted
      review-base: codex review --base main
      interactive: codex
    examples:
      - "codex review --uncommitted  # 审查未提交的代码"
      - "codex review --base main    # 对比 main 分支审查"

  copilot:
    name: GitHub Copilot CLI
    install: Install GitHub Copilot CLI extension
    description: General-purpose AI assistant
    commands:
      interactive: copilot
      prompt: copilot -p "<prompt>" --allow-all-tools
    examples:
      - "copilot                    # 启动交互模式"
      - "copilot -p 'Fix bug' --allow-all-tools  # 非交互执行"
```

### 3. Shell 实现

**文件**: `lib/chat.sh`

**核心函数**:
```bash
vibe_chat() {
  local agent="${1:-}"

  if [[ -z "$agent" ]]; then
    # 显示所有 agent 列表
    _chat_list_agents
    # 交互式选择
    agent=$(_chat_select_agent)
  fi

  # 显示 agent 使用指南
  _chat_show_usage "$agent"
}

_chat_list_agents() {
  # 读取 .agent/agents.yml
  # 显示表格: name | description | status (installed?)
}

_chat_show_usage() {
  local agent="$1"
  # 显示安装方法
  # 显示常用命令
  # 显示示例
}
```

## 验收标准

1. ✅ `vibe chat` 显示所有可用 agent
2. ✅ `vibe chat --agent=codex` 显示 codex 使用指南
3. ✅ `vibe chat --agent=copilot` 显示 copilot 使用指南
4. ✅ 检测 agent 是否已安装
5. ✅ 提供安装指南（如果未安装）

## 相关文档

- `vibe flow review --local` 依赖此功能
- `.agent/workflows/SUBAGENT_GUIDELINES.md` 引用此功能

## 优先级

**Medium** - 提升用户体验，但不阻塞核心功能
