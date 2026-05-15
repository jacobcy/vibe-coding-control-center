---
document_type: architecture
title: MetaClaw Hybrid 架构
status: draft
scope: meta-layer-architecture
author: Claude Sonnet
related_docs:
  - README.md
  - metalayer-prd.md
---

# MetaClaw Hybrid 架构

> **注意**：这是一个可选的高级架构设计，在 Meta Layer 基础上增加本地 LoRA 能力。基础 Meta Layer 实现不需要此架构。

## 1. 系统角色定义

| 角色 | 职责 |
|------|------|
| **The Brain (Cloud API)** | 处理复杂逻辑与规划（如 GPT-4o） |
| **The Cerebellum (Local MLX + LoRA)** | 处理风格化输出、工具调用格式、私有代码偏好 |
| **The Harness (Your Project)** | 提供执行环境（Sandbox）、工具集（Tools）和状态监控 |
| **MetaClaw** | 充当智能路由器与持续学习引擎 |

## 2. 接口协议

Agent 必须通过 OpenAI 兼容格式与 MetaClaw 通讯：

```json
{
  "model": "metaclaw-hybrid",
  "messages": [...],
  "extra_body": {
    "harness_context": {
      "project_id": "your-unique-project-id",
      "runtime_env": "macos-arm64-mlx",
      "active_tools": ["file_editor", "shell_executor", "git_provider"],
      "last_action_status": "success/error"
    },
    "learning_mode": "continual"
  }
}
```

## 3. 核心功能层级

### 3.1 状态感知层（Context Injection）

- **要求**：每次请求前，Harness 必须自动提取当前项目的关键指纹
- **内容**：最近修改的 3 个文件、当前编译错误信息
- **执行**：注入到 System Prompt 的 `[PROJECT_CONTEXT]` 块

### 3.2 动作拦截与验证（Action & Verification）

- **要求**：本地 LoRA 小模型生成 Tool Call 时，Harness 必须先在沙箱中模拟执行
- **反馈逻辑**：
  - 报错 → 将错误 Trace 发回 MetaClaw，标记为"负样本"
  - 成功 → 标记为"正样本"

### 3.3 内存挂载规范（MLX LoRA Loading）

- **要求**：MetaClaw 必须能够根据 project_id 动态切换适配器
- **路径**：`~/.metaclaw/adapters/{project_id}/latest.safetensors`

## 4. 持续学习触发器

Agent 必须在以下三个时刻向 MetaClaw 发送 LEARN 信号：

| 触发条件 | 说明 |
|---------|------|
| 用户纠偏 | 用户手动修改了 Agent 生成的代码 |
| 验证成功 | 生成的代码通过了本地单元测试 |
| 流程完结 | 任务结束时，汇总整条 Trace 供"机会性微调" |

## 5. 资源分配建议（Mac Mini）

| 进程 | 类型 | 内存 |
|------|------|------|
| Your App | CPU Bound | 1-2GB RAM |
| Harness Sandbox | Docker/VM | 2GB RAM |
| MetaClaw Server (Inference) | MLX Unified | 8-12GB (Llama-3-8B) |
| MetaClaw Server (Training) | Background Low-Priority | 利用空闲 GPU 周期 |

## 6. Agent 执行指令

> 作为我的开发助手，你现在需要接入 MetaClaw 架构。你的所有 LLM 请求必须经过 localhost:8000 代理。在执行任务时，优先尝试使用本地 LoRA 模型处理风格和格式问题；当遇到逻辑瓶颈时，通过 MetaClaw 路由请求云端大脑。每次我修改你的代码，你必须将修改前后的对比通过 /v1/feedback 接口发送，以供后台进行 MLX 微调。

---

## 与基础 Meta Layer 的关系

MetaClaw 是 Meta Layer 的**增强版本**：

- 基础 Meta Layer：Proxy + Event + Skill（极简）
- MetaClaw：增加本地 LoRA + 持续学习 + 云端路由

**实施建议**：先实现基础 Meta Layer，验证价值后再考虑 MetaClaw 增强。
