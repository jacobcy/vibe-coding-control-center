meta-layer-simple.spec.md

⸻

1. 设计原则（必须遵守）

2. 不做智能判断
3. 不做复杂筛选
4. 不做训练
5. 一切保持可解释、可 debug


⸻

1. 系统目标

实现一个最小 Meta Layer：

记录 → 总结 → 注入（少量）


⸻

2. Skill 系统（核心）

⸻

2.1 Skill 数据结构（必须用这个）

{
  "id": "uuid",
  "content": "调用 API 前必须初始化 client",
  "created_at": 1710000000
}


⸻

2.2 存储路径

~/.meta-layer/skills.json


⸻

2.3 数量限制（强制）

最多 50 条

超过：

删除最旧的


⸻

2.4 去重规则（必须实现）

如果 content 完全相同 → 不新增

👉 不做 embedding
👉 不做语义判断

⸻

3. Skill 注入策略（极简）

⸻

唯一规则：

skills[-3:]


⸻

注入格式：

[LEARNED_SKILLS]
- xxx
- xxx
- xxx


⸻

禁止做：
	•	❌ 关键词匹配
	•	❌ 分类
	•	❌ 相关性计算

⸻

4. Skill 生成（最重要）

⸻

4.1 触发条件

task 结束时


⸻

4.2 输入（固定格式）

以下是执行过程：

事件：
- tool_failed: ...
- user_corrected: ...
- test_failed: ...

请总结一条经验（必须具体、可执行，一句话）


⸻

4.3 输出要求（强约束）

必须满足：

- 具体（不能抽象）
- 可执行（能指导行为）
- 单条（只允许一句）


⸻

❌ 禁止输出：

“要注意错误”
“需要优化代码”


⸻

4.4 写入规则

if skill 不为空 AND 不重复:
    append


⸻

5. Event 系统（极简版）

⸻

5.1 支持事件

[
  "tool_failed",
  "tool_success",
  "test_failed",
  "test_passed",
  "user_corrected"
]


⸻

5.2 存储

{
  "events": []
}


⸻

👉 不做分析
👉 不做分类

⸻

6. Trace（任务记录）

⸻

结构：

{
  "task_id": "",
  "events": [],
  "messages": []
}


⸻

用途：

👉 只用于：

生成 skill


⸻

👉 不做：
	•	统计
	•	打分
	•	replay

⸻

7. Proxy 行为（必须实现）

⸻

输入流程：

1. 接收请求
2. 注入 skills[-3:]
3. 转发给 LLM


⸻

输出流程：

1. 返回结果
2. 记录 messages


⸻

8. Harness 集成（只做这三件事）

⸻

1️⃣ tool 后上报

"type": "tool_failed"


⸻

2️⃣ test 后上报

"type": "test_failed"


⸻

3️⃣ 用户修改上报

"type": "user_corrected"


⸻

👉 不允许更多逻辑

⸻

9. CLI（必须有）

⸻


meta-layer start
meta-layer skills
meta-layer clear


⸻

10. 成功标准（你必须验证）

⸻

Day 1

skills = []


⸻

Day 3

[
  "调用 API 前必须初始化 client",
  "路径必须使用绝对路径"
]


⸻

Day 7

👉 明显减少重复错误

⸻

11. 明确不做的（防止失控）

⸻

❌ 不允许：
	•	embedding
	•	小模型
	•	LoRA
	•	skill 分类
	•	智能选择

⸻

12. 过滤

⸻

def is_valid_skill(skill: str, existing: list[str]) -> bool:
    s = skill.strip()

    if len(s) < 10: return False
    if any(bad in s.lower() for bad in ["注意", "优化", "检查", "确保", "问题"]): return False
    if len(set(s)) < len(s) * 0.5: return False  # 去掉重复字符垃圾
    if s in existing: return False
    if s.endswith("..."): return False
    if "必须" not in s and "需要" not in s: return False  # 强制可执行语气

    return True

⸻

13. 最关键一句（给你压住方向）

⸻

❗ 先让系统“有记忆”
再考虑“如何聪明使用记忆”

