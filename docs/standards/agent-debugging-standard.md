# Agent 调试标准

> **文档定位**：定义 `vibe3` agent 链路的标准调试方法，先以 supervisor / orchestra 治理链为基线，再作为调试 manager 链的统一方法
> **适用范围**：所有使用 `vibe3 run`、`vibe3 plan`、`vibe3 review`、heartbeat、orchestra、manager 的 agent 编排调试
> **权威性**：本标准是 agent 调试流程的权威依据；具体业务语义仍以对应的 `skills/`、`supervisor/`、`.agent/policies/` 为准

---

## 一、目标

调试 agent 链路时，目标不是“尽快跑通一次”，而是：

- 确认 prompt 材料是否正确装配
- 确认底层触发是否只做最小能力提供
- 确认业务逻辑是否仍留在上层 skill / supervisor
- 确认执行结果是否能被稳定观察、复盘与复现

本标准要求先把一条链路调通，再迁移到下一条链路。当前推荐顺序：

1. 先调通 supervisor / orchestra 治理链
2. 再用同样方法调试 manager 单 issue 执行链

---

## 二、总原则

### 2.1 上层负责业务，底层只负责触发

- Python 底层能力只提供：
  - prompt 装配
  - issue/plan/instruction 注入
  - async/tmux 启动
  - session/log 暴露
- Python 底层**不应**硬编码：
  - findings 类型路由
  - 治理动作判断
  - comment / close 决策
  - 是否查询 `vibe3 task status` / `vibe3 flow show`

业务逻辑必须留在：

- `skills/`：人机协作入口
- `supervisor/`：自动化治理与角色材料
- `.agent/policies/`：plan/run/review mode policy

### 2.2 先 dry-run，再单步 apply

每一条新链路都按下面顺序调试：

1. 先看 prompt 是否正确装配
2. 再跑 dry-run，确认建议或执行计划是否合理
3. 再做一次最小真实执行
4. 每执行一步都停下来检查结果

禁止一开始就把 heartbeat、批量执行、自动回收一起打开。

### 2.3 默认 async/tmux，观察优先

agent 调试默认使用 async/tmux：

- 默认使用 async 执行，避免前台阻塞
- 通过 tmux session 和 session log 观察运行过程
- 通过 `vibe3 flow show` 或 GitHub issue 查看外部结果

调试时必须优先保证“能看见发生了什么”，而不是追求链路一步到位自动化。

### 2.4 角色默认模型必须显式配置

- `plan`、`run`、`review`、`manager`、`supervisor` 是不同角色，不应因为实现方便而隐式共用同一个默认 agent preset
- 尤其是 `manager`，它承担 scene 判断、状态迁移、后续 agent 派发，不应默认继承 `run.agent_config.agent`
- 如果某个角色长期表现出“执行型过强、治理型过弱”或“过度自由探索”，优先检查该角色是否错误继承了别的默认 agent/model
- 调试时要同时核查两层真源：
  - 仓库配置真源：`config/settings.yaml`
  - codeagent preset 真源：`~/.codeagent/models.json`
- 原则上：
  - 仓库只决定“这个角色默认用哪个 agent/backend/model”
  - `models.json` 决定该 preset 的具体底层映射
  - prompt 不负责偷偷补偿模型选择错误

---

## 三、标准调试循环

每条 agent 链路都应遵循同一套调试循环：

1. **确定真源**
   - 开发链：issue + branch + flow + worktree
   - 治理链：issue + labels + comments
2. **确认 prompt 材料**
   - 先确认 `skills/`、`supervisor/`、`.agent/policies/` 是否在正确层级
3. **dry-run 验证**
   - 确认建议、计划或目标 issue 是否正确
4. **最小真实执行**
   - 只放开最小动作，不一次启用所有副作用
5. **观察执行现场**
   - 记录 tmux session、session log、CLI 输出、issue/flow 变化
6. **停下来读结果**
   - 先确认结果与 comment / issue 线程一致，再进入下一步
7. **只收当前尾巴**
   - 清掉重复 comment、错误提示、无效中间文件、旧 help 文案等残留

---

## 四、Supervisor / Orchestra 治理链调试标准

### 4.1 链路语义

治理链的标准形态是：

```text
supervisor suggest -> governance issue -> run --issue -> apply -> comment -> close
```

约束如下：

- `supervisor/issue-cleanup.md` 负责发现问题并创建治理 issue
- `supervisor/apply.md` 负责读取指定治理 issue，核查、执行、comment、close
- `vibe3 run --issue <number>` 默认读取配置中的 apply supervisor
- 治理 issue 是交接真源；不要为治理链引入 branch handoff

### 4.2 治理 issue 约定

治理 issue 的最小约定：

- labels：
  - `supervisor`
  - `state/handoff`
- 标题前缀表达 findings 类型，例如：
  - `cleanup: ...`
- body 中写清：
  - findings
  - 建议动作
  - 禁止动作
  - 核查方式

### 4.3 调试步骤

#### 第一步：检查 prompt 装配

```bash
vibe3 run --supervisor supervisor/issue-cleanup.md --dry-run
```

检查点：

- prompt 是否使用了正确的 supervisor 文件
- 是否明确要求 agent 自己运行 `vibe3 task status`、`vibe3 flow show`、`gh issue view`
- 是否避免把过多业务判断下沉到底层

#### 第二步：手动创建治理 issue

```bash
vibe3 run --supervisor supervisor/issue-cleanup.md
```

检查点：

- 是否真的创建了治理 issue，而不是只停留在 findings preview
- 创建前是否先查重，避免重复发布重叠 issue
- 是否只创建当前轮次需要的最小 issue 集

#### 第三步：手动触发 apply

```bash
vibe3 run --issue <governance_issue_number>
```

检查点：

- 是否默认使用配置中的 apply supervisor
- 是否进入 async/tmux
- 是否正确读取指定 issue，而不是自行重新查找一批 issue

#### 第四步：观察结果

观察顺序：

1. 终端输出的 tmux session
2. 终端输出的 session log
3. GitHub issue comment
4. GitHub issue close 状态

成功标准：

- issue 中只有一条正式结果 comment
- comment 与实际执行结果一致
- issue 被关闭

### 4.4 治理链调试结论

本次 supervisor / orchestra 调试沉淀出以下固定规则：

- 治理链通过 issue 交接，不通过 branch handoff 交接
- `run --issue` 是治理 issue 的统一 apply 入口
- async/tmux 与 session log 属于底层 codeagent 适配层，不属于上层 orchestration
- 底层只负责触发；是否检查 `vibe3 task status`、是否创建 issue、是否 comment / close，全部由 supervisor prompt 决定

---

## 五、Manager 链调试标准

manager 链不复用治理 issue 交接模型，而是保留 scene 模型：

```text
issue -> branch/worktree -> flow -> manager -> plan -> run -> review
```

调试 manager 时，沿用本标准中的三条不变原则：

1. 先确认 prompt / policy / scene 装配是否正确
2. 默认 async/tmux，确保执行过程可观测
3. 每跑一步就停下来检查结果，不连续堆叠多个阶段

manager 链与治理链的差异只在真源：

- 治理链以 GitHub issue 为交接真源
- manager 链以 issue + branch + worktree + flow 为交接真源

因此，调试 manager 时必须重点检查：

- 当前 branch / worktree / flow 是否一致
- manager 是否只负责 scene 推进，而没有吞掉上层业务编排
- plan/run/review 的 mode policy 是否正确注入
- manager 使用的默认 agent/model 是否来自独立配置，而不是隐式继承 `run`

### 5.1 Manager 角色与模型

- `manager` 是开发链 owner，不是普通执行 agent
- `manager` 的默认 agent/model 应单独配置在 orchestra/manager 侧，而不是沿用 `run.agent_config`
- 调试 manager 异常时，优先区分三类问题：
  - prompt 材料不对
  - scene/worktree/session 不对
  - manager 角色模型不对

如果 manager 的行为明显更像“直接实现代码”而不是“检查现场、迁移状态、决定下一步”，优先检查 manager 的默认 agent preset 是否选错

---

## 六、观测标准

### 6.1 默认观测入口

CLI 输出必须直接给出：

- `Tmux session: ...`
- `Session log: temp/logs/...`

调试者优先看：

1. tmux session
2. `temp/logs/...`
3. `vibe3 flow show`
4. GitHub issue / PR / comment

### 6.2 日志位置

session log 统一写入：

```text
temp/logs/
```

不要把调试期的 session/log 继续挂在上层 handoff 语义里。

---

## 七、反模式

以下做法属于反模式：

- 在 Python 底层按 findings 类型硬编码 supervisor 路由
- 为每个新 supervisor 增加一套专用 runtime context 适配
- 让底层帮上层预判是否 comment / close
- 治理链依赖 branch/worktree handoff
- 一次调试同时打开 dry-run、heartbeat、自动 apply、自动回收
- 看不到 tmux/session log 就继续盲跑下一轮

---

## 八、落地检查清单

开始调试一条新链路前，先检查：

- 是否已经明确这条链的真源是什么
- 是否已经明确业务逻辑留在 skill/supervisor，而不是底层
- 是否已经有 dry-run 入口
- 是否默认 async/tmux
- 是否能直接看到 session log 路径
- 是否有最小真实执行入口
- 是否规定了执行后停下来检查结果

如果以上任一项不满足，应先补调试能力，再继续扩展业务逻辑。
