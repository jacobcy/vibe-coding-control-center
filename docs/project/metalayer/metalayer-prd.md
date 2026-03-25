meta-layer.spec.md

1. 目标

构建一个独立服务（Meta Layer），用于：
	•	注入上下文（context）
	•	注入经验（skills）
	•	记录执行过程（events / trace）
	•	在任务结束后生成经验（skills）

⸻

2. 系统定位

Agent → Meta Layer → LLM
                  ↓
               Harness


⸻

3. 必须实现的能力

⸻

3.1 Proxy 服务

接口

POST /v1/chat/completions


⸻

行为

Step 1：获取 context
来源：
	•	Git（最近文件）
	•	上次 error
	•	当前分支

输出：

{
  "recent_files": [],
  "last_error": "",
  "branch": ""
}


⸻

Step 2：获取 skills
来源：

~/.meta-layer/skills.json

结构：

[
  "经验1",
  "经验2"
]


⸻

Step 3：重写 prompt
拼接：

[PROJECT_CONTEXT]
...

[LEARNED_SKILLS]
...

[USER_INPUT]
...


⸻

Step 4：转发请求到 LLM

⸻

Step 5：记录 response（用于 trace）

⸻

⸻

3.2 Event 接口

POST /events


⸻

支持类型

{
  "type": "tool_success | tool_failed | test_passed | test_failed | user_corrected",
  "payload": {}
}


⸻

行为
	•	写入当前 task trace

⸻

⸻

3.3 Trace 系统

存储路径：

~/.meta-layer/traces/{task_id}.json


⸻

结构：

{
  "task_id": "",
  "events": [],
  "messages": [],
  "result": ""
}


⸻

⸻

3.4 Skill 生成（核心）

触发

POST /task/end


⸻

行为

调用 LLM：

根据以下执行过程，总结一条经验（一句话）：

- events
- 用户修改
- 错误信息


⸻

输出

经验句子


⸻

存储

~/.meta-layer/skills.json


⸻

规则：
	•	最多 100 条
	•	超出则删除最旧

⸻

⸻

3.5 Skill 注入策略

每次请求：

skills[-5:]


⸻

⸻

3.6 CLI（必须）

meta-layer start
meta-layer clear-skills
meta-layer inspect-trace


⸻

⸻

4. 不做（必须遵守）
	•	不做 RL
	•	不做 LoRA
	•	不做 embedding
	•	不做多模型 routing

⸻

⸻

5. 完成标准
	•	能代理 LLM 请求
	•	能记录 events
	•	能生成 skill
	•	skill 能影响下一次行为

=====

下面给你一份最小可运行的 Meta Layer 示例代码（单文件版）。
目标：先跑通闭环（代理 → 事件 → trace → skill → 注入），再逐步拆模块。

依赖：fastapi, uvicorn, httpx, python-dotenv（可选）
启动：uvicorn server:app --port 3000

⸻

✅ server.py（最小实现）

import os
import json
import uuid
import time
from typing import List, Dict, Any

import httpx
from fastapi import FastAPI, Request

# ===== 基础配置 =====
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "https://api.openai.com/v1/chat/completions")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
BASE_DIR = os.path.expanduser("~/.meta-layer")
SKILL_PATH = os.path.join(BASE_DIR, "skills.json")
TRACE_DIR = os.path.join(BASE_DIR, "traces")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(TRACE_DIR, exist_ok=True)

# 初始化 skill 文件
if not os.path.exists(SKILL_PATH):
    with open(SKILL_PATH, "w") as f:
        json.dump([], f)

app = FastAPI()

# ===== 内存状态（简化）=====
CURRENT_TRACE = {
    "task_id": None,
    "events": [],
    "messages": [],
    "result": None,
}


# ===== 工具函数 =====

def load_skills() -> List[str]:
    with open(SKILL_PATH, "r") as f:
        return json.load(f)


def save_skills(skills: List[str]):
    skills = skills[-100:]  # 限制最大数量
    with open(SKILL_PATH, "w") as f:
        json.dump(skills, f, indent=2)


def collect_context() -> Dict[str, Any]:
    # 简化版（后续可接 git / error / branch）
    return {
        "recent_files": [],
        "last_error": "",
        "branch": "unknown"
    }


def build_prompt(original_messages: List[Dict]) -> List[Dict]:
    context = collect_context()
    skills = load_skills()[-5:]

    system_injection = f"""
[PROJECT_CONTEXT]
- recent_files: {context['recent_files']}
- last_error: {context['last_error']}
- branch: {context['branch']}

[LEARNED_SKILLS]
{chr(10).join(['- ' + s for s in skills])}
"""

    injected = [{"role": "system", "content": system_injection}]
    return injected + original_messages


def start_trace():
    CURRENT_TRACE["task_id"] = str(uuid.uuid4())
    CURRENT_TRACE["events"] = []
    CURRENT_TRACE["messages"] = []
    CURRENT_TRACE["result"] = None


def save_trace():
    path = os.path.join(TRACE_DIR, f"{CURRENT_TRACE['task_id']}.json")
    with open(path, "w") as f:
        json.dump(CURRENT_TRACE, f, indent=2)


async def summarize_skill(trace: Dict) -> str:
    prompt = f"""
以下是一个任务执行过程：

事件：
{json.dumps(trace['events'], indent=2)}

请总结一条经验（短句）：
"""

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            LLM_ENDPOINT,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60
        )

    try:
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""


# ===== API =====

@app.post("/v1/chat/completions")
async def proxy_chat(req: Request):
    body = await req.json()

    if CURRENT_TRACE["task_id"] is None:
        start_trace()

    messages = body.get("messages", [])
    CURRENT_TRACE["messages"].extend(messages)

    # 注入 context + skills
    new_messages = build_prompt(messages)
    body["messages"] = new_messages

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            LLM_ENDPOINT,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            },
            json=body,
            timeout=60
        )

    return resp.json()


@app.post("/events")
async def record_event(req: Request):
    data = await req.json()

    CURRENT_TRACE["events"].append({
        "type": data.get("type"),
        "payload": data.get("payload", {}),
        "ts": time.time()
    })

    return {"status": "ok"}


@app.post("/task/end")
async def end_task():
    CURRENT_TRACE["result"] = "completed"

    # 生成 skill
    skill = await summarize_skill(CURRENT_TRACE)

    if skill:
        skills = load_skills()
        skills.append(skill)
        save_skills(skills)

    save_trace()

    # reset
    CURRENT_TRACE["task_id"] = None

    return {
        "status": "done",
        "new_skill": skill
    }


# ===== CLI debug =====

@app.get("/skills")
def get_skills():
    return load_skills()


@app.get("/health")
def health():
    return {"status": "ok"}


⸻

🚀 怎么验证这个系统是“活的”

1️⃣ 启动

uvicorn server:app --port 3000


⸻

2️⃣ 把你的 Agent 指向：

http://localhost:3000/v1/chat/completions


⸻

3️⃣ 模拟一个流程

调用 LLM（正常聊天）

⸻

上报一个失败

curl -X POST http://localhost:3000/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "tool_failed",
    "payload": {"error": "file not found"}
  }'


⸻

结束任务

curl -X POST http://localhost:3000/task/end


⸻

4️⃣ 查看 skill

curl http://localhost:3000/skills


⸻

👉 如果你看到：

[
  "在这个项目中，文件路径需要提前检查是否存在"
]

👉 说明系统已经开始“学习”

