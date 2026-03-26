harness-integration.spec.md

1. 目标

在不改变现有架构的前提下，让 Harness：

👉 向 Meta Layer 提供执行信号

⸻

2. 原则
	•	不改核心架构
	•	不增加复杂度
	•	只增加“上报”

⸻

⸻

3. 必须修改的点（仅 3 处）

⸻

3.1 Tool 执行后

位置：
	•	shell_executor
	•	file_editor
	•	git_provider

⸻

修改

post("/events", {
  "type": "tool_success" | "tool_failed",
  "payload": {
    "tool": "...",
    "error": "...",
    "output": "..."
  }
})


⸻

⸻

3.2 Test 执行后

post("/events", {
  "type": "test_passed" | "test_failed"
})


⸻

⸻

3.3 用户修改代码

触发条件：
	•	git diff
	•	文件被改

⸻


post("/events", {
  "type": "user_corrected",
  "payload": {
    "diff": "..."
  }
})


⸻

⸻

4. 可选增强（不是必须）
	•	compile error 上报
	•	lint error 上报
	•	PR review 上报

⸻

⸻

5. 不允许做的事

❌ 不允许：
	•	在 Harness 里写 skill 逻辑
	•	在 Harness 里写 prompt 注入
	•	在 Harness 里调用 LLM 总结经验

⸻

👉 Harness 只负责：

执行 + 上报


⸻

⸻

6. 配置

meta_layer_url: http://localhost:3000


⸻

⸻

7. 完成标准
	•	所有 tool 行为可追踪
	•	test 可追踪
	•	用户修改可追踪
	•	不影响原有功能
