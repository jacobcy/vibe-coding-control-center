---
document_type: reference
title: Oh My OpenCode 最佳实践指南
status: verified
scope: external-plugin-system
author: Sisyphus Agent
created: 2026-05-22
last_updated: 2026-05-22
related_docs:
  - oh-my-opencode-guide.md
  - opencode-lsp-setup-guide.md
source_urls:
  - https://github.com/code-yeongyu/oh-my-openagent
  - https://opencodedocs.com/code-yeongyu/oh-my-opencode/platforms/provider-setup/
  - https://medium.com/@rosgluk/oh-my-opencode-specialised-agents-deep-dive-and-model-guide-d064d8f2a3fa
---

# Oh My OpenCode 最佳实践指南

> **参考来源**：官方文档、社区实践、gist 配置示例
> **验证日期**：2026-05-22

## 概述

Oh My OpenCode (oMo) 是 OpenCode 的插件系统，提供专业化 AI Agent 架构、模型路由、LSP 集成等能力。本文档总结生产环境中的最佳实践配置。

## 核心原则

### 1. 不要硬编码单一模型

**问题**：硬编码单一模型会破坏自动 fallback 机制。

```jsonc
// ❌ 错误：没有 fallback，provider 不可用时 agent 完全失败
"oracle": {
  "model": "anthropic/claude-opus-4-7"
}

// ✅ 正确：配置 fallback 链
"oracle": {
  "model": "anthropic/claude-opus-4-7",
  "fallback_models": [
    { "model": "openai/gpt-5.2", "variant": "high" },
    { "model": "google/gemini-3-pro" }
  ]
}
```

### 2. 利用 Category 路由而非直接指定模型

**问题**：直接指定模型名会绕过 category 路由机制。

```jsonc
// ❌ 错误：硬编码模型，失去灵活性
task(category="quick", prompt="...")  // 使用 quick category 的默认模型

// ✅ 正确：让 category 决定模型
// 在 oh-my-opencode.json 中配置 category 默认模型
"categories": {
  "quick": { "model": "opencode/gpt-5-nano" },
  "deep": { "model": "anthropic/claude-sonnet-4-6", "variant": "max" }
}
```

### 3. 限制昂贵 Provider 的并发

**问题**：多个 background task 同时调用昂贵模型会超过 API 限制。

```jsonc
// ✅ 正确：配置并发限制
"background_task": {
  "defaultConcurrency": 3,
  "providerConcurrency": {
    "anthropic": 3,
    "openai": 3,
    "opencode": 10,
    "my-provider": 5
  },
  "modelConcurrency": {
    "anthropic/claude-opus-4-7": 2,
    "openai/gpt-5.4": 2,
    "my-provider/deepseek-v4-pro": 2
  }
}
```

## Agent 配置最佳实践

### Agent 角色与推荐模型

| Agent | 角色 | 推荐模型 | 特点 |
|---|---|---|---|
| **Sisyphus** | 主编排器 | Claude Opus / Kimi K2.5 / GLM-5 | 需要 strong reasoning |
| **Prometheus** | 战略规划 | GPT-5.2 (high) / Claude Opus | 双 Prompt 支持，GPT 更高效 |
| **Oracle** | 架构咨询 | GPT-5.2 / Claude Opus | 需要 deep reasoning |
| **Metis** | 需求分析 | DeepSeek-V4-Pro / Claude Sonnet | 分析复杂度 |
| **Momus** | 计划评审 | DeepSeek-V4-Pro / GPT-5.2 | 需要严谨性 |
| **Librarian** | 文档搜索 | GLM-4.7 / GPT-5-nano | 速度优先，不需要 Opus |
| **Explore** | 代码搜索 | GLM-4.7 / GPT-5-nano | 速度优先 |
| **Atlas** | Todo 编排 | Kimi K2.5 / GPT-5.2 | 双 Prompt 支持 |
| **Multimodal-Looker** | 图像分析 | Gemini / Kimi K2.5 | 需要 vision 能力 |

### 安全的模型替换

**同一模型族内替换是安全的**：

```jsonc
// ✅ 安全：同族替换
"sisyphus": { "model": "anthropic/claude-opus-4-7" }
  → "anthropic/claude-sonnet-4-6"  // OK
  → "kimi-for-coding/k2p5"         // OK (Claude-like)
  → "opencode-go/glm-5"            // OK (Claude-like)

// ✅ 安全：双 Prompt agent 可以跨族
"prometheus": { "model": "anthropic/claude-opus-4-7" }
  → "openai/gpt-5.2"  // OK，自动切换到 GPT prompt
```

**危险的模型替换**：

```jsonc
// ❌ 危险：Hephaestus 需要 GPT-5.3-codex，Claude 无法复制
"hephaestus": { "model": "anthropic/claude-opus-4-7" }  // 会失败

// ❌ 浪费：给不需要的 agent 用昂贵模型
"explore": { "model": "anthropic/claude-opus-4-7" }  // 巨大浪费
"librarian": { "model": "anthropic/claude-opus-4-7" } // 同上
```

### 为 Agent 添加指导 Prompt

```jsonc
"agents": {
  "prometheus": {
    "model": "my-provider/qwen3.6-plus",
    "prompt_append": "Leverage deep & quick agents heavily, always in parallel."
  },
  "sisyphus": {
    "model": "my-provider/glm-5",
    "prompt_append": "Focus on minimal changes and atomic commits."
  }
}
```

## Category 配置最佳实践

### Category 用途与推荐配置

| Category | 用途 | 推荐模型 | 注意事项 |
|---|---|---|---|
| **visual-engineering** | 前端/UI | Gemini 3 Pro / Kimi K2.5 | 需要视觉能力 |
| **ultrabrain** | 困难逻辑 | GPT-5.4 (xhigh) / Claude Opus | 最强推理 |
| **deep** | 自主问题解决 | Claude Sonnet / DeepSeek-V4 | 平衡能力与成本 |
| **quick** | 简单任务 | GPT-5-nano / GLM-4.7 | 速度优先 |
| **unspecified-low** | 低复杂度 | GLM-4.7 / GPT-5-nano | 通用轻量 |
| **unspecified-high** | 高复杂度 | Claude Sonnet / GPT-5.2 | 通用重量 |
| **writing** | 文档 | GLM-4.7 / GPT-5-nano | 不需要强推理 |
| **artistry** | 创意工作 | Gemini / Kimi K2.5 | 需要创造力 |

### Category Fallback 链示例

```jsonc
"categories": {
  "ultrabrain": {
    "model": "my-provider/deepseek-v4-pro",
    "fallback_models": [
      { "model": "my-provider/qwen3.6-plus" },
      { "model": "my-provider/glm-5" }
    ]
  },
  "quick": {
    "model": "my-provider/glm-5",
    "fallback_models": [
      { "model": "my-provider/gpt-4o-mini" }
    ]
  }
}
```

## 完整配置示例

### 基础配置（最小可用）

```jsonc
{
  "$schema": "https://raw.githubusercontent.com/code-yeongyu/oh-my-opencode/master/assets/oh-my-opencode.schema.json",
  "agents": {
    "sisyphus": { "model": "my-provider/glm-5" },
    "oracle": { "model": "my-provider/qwen3.6-plus" },
    "librarian": { "model": "my-provider/glm-5" },
    "explore": { "model": "my-provider/glm-5" }
  },
  "categories": {
    "quick": { "model": "my-provider/glm-5" },
    "deep": { "model": "my-provider/deepseek-v4-pro" }
  }
}
```

### 生产配置（推荐）

```jsonc
{
  "$schema": "https://raw.githubusercontent.com/code-yeongyu/oh-my-opencode/master/assets/oh-my-opencode.schema.json",
  "agents": {
    "sisyphus": {
      "model": "my-provider/glm-5",
      "fallback_models": [
        { "model": "my-provider/gpt-4o-mini" }
      ]
    },
    "prometheus": {
      "model": "my-provider/qwen3.6-plus",
      "prompt_append": "Leverage deep & quick agents heavily, always in parallel.",
      "fallback_models": [
        { "model": "my-provider/deepseek-v4-pro" },
        { "model": "my-provider/glm-5" }
      ]
    },
    "oracle": {
      "model": "my-provider/qwen3.6-plus",
      "fallback_models": [
        { "model": "my-provider/deepseek-v4-pro" },
        { "model": "my-provider/glm-5" }
      ]
    },
    "metis": {
      "model": "my-provider/deepseek-v4-pro",
      "fallback_models": [
        { "model": "my-provider/glm-5" }
      ]
    },
    "momus": {
      "model": "my-provider/deepseek-v4-pro",
      "fallback_models": [
        { "model": "my-provider/glm-5" }
      ]
    },
    "librarian": {
      "model": "my-provider/glm-5",
      "fallback_models": [
        { "model": "my-provider/gpt-4o-mini" }
      ]
    },
    "explore": {
      "model": "my-provider/glm-5",
      "fallback_models": [
        { "model": "my-provider/gpt-4o-mini" }
      ]
    },
    "atlas": {
      "model": "my-provider/glm-5"
    },
    "multimodal-looker": {
      "model": "my-provider/kimi-k2.5"
    },
    "sisyphus-junior": {
      "model": "my-provider/glm-5"
    }
  },
  "categories": {
    "visual-engineering": {
      "model": "my-provider/kimi-k2.5"
    },
    "ultrabrain": {
      "model": "my-provider/deepseek-v4-pro",
      "fallback_models": [
        { "model": "my-provider/qwen3.6-plus" },
        { "model": "my-provider/glm-5" }
      ]
    },
    "deep": {
      "model": "my-provider/deepseek-v4-pro",
      "fallback_models": [
        { "model": "my-provider/glm-5" }
      ]
    },
    "artistry": {
      "model": "my-provider/kimi-k2.5"
    },
    "quick": {
      "model": "my-provider/glm-5",
      "fallback_models": [
        { "model": "my-provider/gpt-4o-mini" }
      ]
    },
    "unspecified-low": {
      "model": "my-provider/glm-5"
    },
    "unspecified-high": {
      "model": "my-provider/deepseek-v4-pro",
      "fallback_models": [
        { "model": "my-provider/glm-5" }
      ]
    },
    "writing": {
      "model": "my-provider/glm-5"
    }
  },
  "background_task": {
    "defaultConcurrency": 3,
    "providerConcurrency": {
      "my-provider": 5
    },
    "modelConcurrency": {
      "my-provider/deepseek-v4-pro": 2,
      "my-provider/qwen3.6-plus": 2,
      "my-provider/glm-5": 5
    }
  },
  "experimental": {
    "aggressive_truncation": true,
    "task_system": true
  }
}
```

## LSP 配置最佳实践

### 添加 Markdown LSP

OpenCode 默认不包含 Markdown LSP，需要手动配置：

```bash
# 安装 marksman
brew install marksman  # macOS
# 或
npm install -g marksman  # 通用
```

在 `oh-my-opencode.json` 中添加：

```jsonc
{
  "lsp": {
    "marksman": {
      "command": ["marksman", "server"],
      "extensions": [".md"],
      "priority": 10
    }
  }
}
```

### LSP 配置优先级

1. **用户配置**：`~/.config/opencode/oh-my-opencode.json`
2. **项目配置**：`.opencode/oh-my-opencode.json`
3. **内置配置**：OpenCode 默认 LSP

### 禁用不需要的 LSP

```jsonc
{
  "lsp": {
    "biome": { "disabled": true },
    "eslint": { "disabled": true }
  }
}
```

## 自托管 / 本地模型配置

### 使用 Ollama 本地模型

**Step 1**: 在 `opencode.json` 中添加 provider：

```jsonc
{
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://localhost:11434/v1"
      }
    }
  }
}
```

**Step 2**: 在 `oh-my-opencode.json` 中配置 agent：

```jsonc
{
  "agents": {
    "explore": {
      "model": "ollama/qwen2.5-coder:7b",
      "temperature": 0.1,
      "stream": false  // Ollama 必须禁用 stream
    },
    "librarian": {
      "model": "ollama/qwen2.5-coder:7b",
      "temperature": 0.1,
      "stream": false
    }
  },
  "categories": {
    "quick": { "model": "ollama/qwen2.5-coder:7b" },
    "writing": { "model": "ollama/qwen2.5-coder:7b" }
  },
  "background_task": {
    "defaultConcurrency": 2,
    "providerConcurrency": {
      "ollama": 4  // 本地可以更高并发
    }
  }
}
```

### 混合云 + 本地配置

```jsonc
{
  "agents": {
    // 本地：快速任务
    "explore": { "model": "ollama/qwen2.5-coder:7b" },
    "librarian": { "model": "ollama/qwen2.5-coder:7b" },
    
    // 云端：推理任务
    "oracle": { "model": "openai/gpt-5.2", "variant": "high" },
    "momus": { "model": "openai/gpt-5.4", "variant": "xhigh" }
  },
  "categories": {
    "quick": { "model": "ollama/qwen2.5-coder:7b" },
    "deep": { "model": "openai/gpt-5.3-codex", "variant": "medium" },
    "ultrabrain": { "model": "openai/gpt-5.4", "variant": "xhigh" }
  }
}
```

## 故障排除

### 问题：ProviderModelNotFoundError

**原因**：配置的模型不存在或 provider 未认证

**解决方案**：
1. 运行 `bunx oh-my-opencode doctor --verbose` 检查配置
2. 检查 provider 认证状态
3. 添加 `fallback_models` 作为后备

### 问题：Background task 并发超限

**原因**：并发请求超过 API 限制

**解决方案**：
```jsonc
"background_task": {
  "modelConcurrency": {
    "anthropic/claude-opus-4-7": 1  // 降低并发
  }
}
```

### 问题：JSONC 配置不生效

**原因**：Bug #1763 - LSP 配置在 JSONC 文件中不被加载

**解决方案**：
- 使用 `.json` 文件而非 `.jsonc`
- 或等待 bug 修复

## 诊断命令

```bash
# 检查配置和模型可用性
bunx oh-my-opencode doctor --verbose

# 查看可用模型
opencode models

# 检查 provider 认证
opencode auth login
```

## 参考资源

- **官方仓库**：https://github.com/code-yeongyu/oh-my-openagent
- **配置文档**：https://opencodedocs.com/code-yeongyu/oh-my-opencode/platforms/provider-setup/
- **Agent 指南**：https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/agent-model-matching.md
- **社区配置示例**：https://gist.github.com/srmdn/448d142a122208c47e586a0d78323b3e
- **深度分析**：https://medium.com/@rosgluk/oh-my-opencode-specialised-agents-deep-dive-and-model-guide-d064d8f2a3fa
