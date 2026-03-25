MetaClaw-Harness 集成规范 (v1.0)
1. 系统角色定义
The Brain (Cloud API): 处理复杂逻辑与规划（如 GPT-4o）。
The Cerebellum (Local MLX + LoRA): 处理风格化输出、工具调用格式、私有代码偏好。
The Harness (Your Project): 提供执行环境（Sandbox）、工具集（Tools）和状态监控。
MetaClaw: 充当 智能路由器 与 持续学习引擎。
2. 接口协议 (Interface Protocol)
Agent 必须通过 OpenAI 兼容格式与 MetaClaw 通讯，但在 extra_body 中需包含以下元数据：
json
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
请谨慎使用此类代码。

3. 核心功能层级实现规范 (Harness Layer Spec)
A. 状态感知层 (Context Injection)
要求：每次请求前，Harness 必须自动提取当前项目的 关键指纹（如：最近修改的 3 个文件、当前编译错误信息）。
执行：将这些信息注入到 System Prompt 的特定块中，标记为 [PROJECT_CONTEXT]。
B. 动作拦截与验证 (Action & Verification)
要求：当本地 LoRA 小模型生成一个工具调用（Tool Call）时，Harness 必须先在 沙箱 中模拟执行。
反馈逻辑：
如果报错：将错误 Trace 发回 MetaClaw，标记为 “负样本”。
如果成功：标记为 “正样本”。
C. 内存挂载规范 (MLX LoRA Loading)
要求：在 Mac Mini 上，MetaClaw 必须能够根据 project_id 动态切换不同的适配器（Adapters）。
路径：~/.metaclaw/adapters/{project_id}/latest.safetensors。
4. 持续学习（Meta-Learning）触发器
你的 Agent 必须在以下三个时刻向 MetaClaw 发送 LEARN 信号：
用户纠偏 (Manual Correction): 当用户手动修改了 Agent 生成的代码时。
验证成功 (Test Passed): 当生成的代码通过了本地单元测试时。
流程完结 (Task Completion): 任务结束时，汇总整条 Trace 供 MetaClaw 进行“机会性微调”。
5. Mac Mini 性能分配建议 (Resource Allocation)
Process A (Your App): CPU Bound, 1-2GB RAM.
Process B (Harness Sandbox): Docker/VM, 2GB RAM.
Process C (MetaClaw Server):
Inference: MLX Unified Memory, 8GB-12GB (Llama-3-8B).
Training: Background Low-Priority (利用 Mac 的空闲 GPU 周期)。
6. Agent 执行指令 (Prompt for your Agent)
你可以直接把这段话喂给你的 Agent：
"作为我的开发助手，你现在需要接入 MetaClaw 架构。你的所有 LLM 请求必须经过 localhost:8000 代理。在执行任务时，优先尝试使用本地 LoRA 模型处理风格和格式问题；当遇到逻辑瓶颈时，通过 MetaClaw 路由请求云端大脑。每次我修改你的代码，你必须将修改前后的对比通过 /v1/feedback 接口发送，以供后台进行 MLX 微调。"