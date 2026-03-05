# Spec V2: Agent Identity Tracking & Logical Binding (Flow Bind)

## 1. 核心问题陈述 (Problem Statement)
当前系统在物理工作树创建（`flow`）与任务状态更新（`task`）之间存在严重的**语义耦合与边界越权**：
1. **指令混用**：`vibe flow new --task` 既用于在新目录建分支，又被作为 hack 手段在旧目录里原地绑定任务。
2. **越权篡改**：作为纯元数据同步模块的 `vibe task update`，在其底层逻辑 `_vibe_task_update` 中竟然直接修改了 Git 的物理签名 (`git config user.name`)。
3. **责任追溯缺失 (Accountability Gap)**：在多 Agent 协作流中，谁创建了任务、谁写了代码、谁做了 Review、谁最终 Commit 提交并不清晰。任务大盘缺乏针对 Agent 生命周期行为的跟踪记录（Audit Trail）。

## 2. 解决方案：动静分离与追踪固化

### 2.1 物理层命令分离 (Flow Bind)
彻底剥离“新建物理环境”与“复用已有环境”。

- **造新车间 (`vibe flow new <task/feature>`)**：必须且必定创建新的独立分支及物理隔离环境。
- **换靶子打 (`vibe flow bind <task-id>`) [新增]**：
  - **职责**：在**当前的物理沙盒**内，切换聚焦的任务目标，但不做任何切分支或毁坏性物理动作。
  - **动作**：加载目标任务数据 -> 刷新当前目录的签名 (`wtrenew/wtinit`) -> 生成本地任务抽屉 `.vibe/*` -> 最后调用纯数据命令 `vibe task update --worktree` 同步大盘。

### 2.2 剥夺特权：Task 回归纯数据管理
- 从 `lib/task_actions.sh` 中移除一切 `git config` 设置逻辑。
- 所有的 `git` 签名修改（刻章机）必须且只能在 `vibe flow`（物理编排）或用户直接使用 `wtinit`/`wtrenew` 时触发。

### 2.3 责任追踪系统 (Agent Signature Accountability)
为了做到“谁起草、谁干活、谁提交、谁背锅”一目了然，在大盘任务元数据结构中引入**参与者日志 (Contributors Log)**。

#### 数据结构变更 (`task.json`)
扩充记录字段：
```json
{
  "task_id": "...",
  "status": "...",
  "agent_log": {
    "planned_by": "claude",
    "executed_by": ["opencode", "claude"],
    "committed_by": "codex",
    "latest_actor": "claude"
  }
}
```

#### 工作流 Hook 埋点设置
为了在执行时做到完美的签名自检，在对应的 Vibe Workflow 中植入**身份审计 (Signature Check)** 与**成果登记**：

1. **`/vibe-start` 和 `/vibe-continue` (Execution 唤醒时)**：
   - 运行环境自检：Agent 必须**先确认自己的真实身份**，然后再与 `git config user.name` 的物理签名比对。
   - 在后台日志或上下文中备注：`"当前操作者: [自己的真实身份]"`。
   - 如果发现环境被别人的签名占用（或者还没设置），禁止盲目盗用别人的签名。必须先自我纠偏：调用 `wtinit <真实名字>` 或 `wtrenew` 把签名修正成自己。

2. **`/vibe-save` (阶段性存档时)**：
   - 在追加 Markdown 研发日志时，附加署名（如：*@Agent-Claude: 修复了核心报错Bug*）。
   - 将这部分数据同步更新，表明“这段烂代码/好代码是谁写的”。

3. **`/vibe-commit` (提交合并时)**：
   - 在 PR 草稿摘要或 Commit Message 尾部，加上 Co-authored-by 或 Agent 签名，作为最终审计证据。
   - 记录 `committed_by` 以追究最终质量责任。

4. **`/vibe-done` (收口结算时)**：
   - 结算报告必须生成一行“参与者审计”，罗列出这整个工单的接力全记录（例如：*Planning: claude | Exec: opencode -> claude | Commit: codex*），记录在案，清清楚楚。
