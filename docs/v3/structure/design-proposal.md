# Structure / Snapshot / Diff 设计方案

**版本**: v0.2
**日期**: 2026-03-22
**状态**: Draft
**定位**: 为多 agent 编排提供结构级质量控制层，不替代现有 inspect/review 主链

---

## 1. 这份设计要解决什么

我们已经明确：

- GitHub labels 负责状态机
- handoff 负责交接
- GitHub Project 负责 UI

但还缺一个稳定的**质量治理层**，用于回答：

- 这轮改动有没有把结构做坏
- agent 有没有越界扩散改动
- 是否出现重复实现、边界膨胀、错层依赖

`structure / snapshot / diff` 就是这一层。

---

## 2. 当前基线

### 2.1 已存在能力

仓库当前真实已有的入口是：

```bash
vibe3 inspect structure <file>
vibe3 inspect structure
```

当前能力是：

- 单文件结构分析
- `src/vibe3` 目录的结构摘要
- Python 文件 import / imported_by 补充展示

### 2.2 当前缺口

还没有：

- 可持久化的 snapshot
- 结构级 diff
- 稳定的 machine-readable 结构基线
- 与 handoff / review / 状态迁移联动的质量闸

### 2.3 关键边界

这套系统不负责：

- 业务状态机
- handoff 文本正文
- 自动判定“代码一定正确”
- 替代现有 PR risk gate

它只负责给 review、handoff、orchestrator 提供**结构级事实**。

---

## 3. 目标定义

### 3.1 三层能力

### A. structure

按当前代码树提取结构事实：

- 文件
- 函数/符号
- 目录/模块聚合
- 依赖关系摘要

### B. snapshot

把某一时刻的结构事实落成稳定基线，供后续比较与交接复用。

### C. diff

对比两个 snapshot 或一个 snapshot 与当前工作树，输出结构变化。

---

## 4. 与多 Agent 编排的关系

### 4.1 这不是孤立工具

目标态里，这套能力必须接到编排链路里：

```text
issue
  -> state/*
  -> flow execution
  -> handoff/review
  -> structure snapshot / diff
  -> merge / recycle
```

### 4.2 典型使用点

#### 进入 handoff 前

- 生成当前结构快照
- 把 snapshot id 或路径写入 handoff

#### 进入 review 前

- 对比 baseline snapshot 和当前 snapshot
- 让 reviewer 看到“结构有没有失控”

#### 进入垃圾代码回收流程时

- 用 diff 判断是否出现边界漂移、重复实现、异常膨胀

---

## 5. 命令面设计

### 5.1 命名决策

**职责分离**：
- `vibe3 inspect files` - 即时分析文件结构（文件级，不持久化）
- `vibe3 snapshot` - 代码库快照管理（模块级，持久化，可对比）

### 5.2 文件分析命令

即时分析，每次运行重新计算：

```bash
# 单文件分析
vibe3 inspect files src/vibe3/services/task_service.py

# 目录摘要（实时计算，不持久化）
vibe3 inspect files
```

输出：文件级结构、函数列表、LOC、依赖关系。

### 5.3 快照管理命令

代码库级结构快照，持久化存储，支持历史对比：

```bash
# 创建快照
vibe3 snapshot build

# 列出所有快照
vibe3 snapshot list

# 查看快照
vibe3 snapshot show              # 最新快照
vibe3 snapshot show <id>         # 指定快照

# 对比快照
vibe3 snapshot diff --baseline <id>    # 与指定快照对比
vibe3 snapshot diff --baseline main    # 与当前 main 对比
```

### 5.4 存储位置

```
.git/vibe3/structure/
  snapshots/
    <snapshot-id>.json
  latest.json
```

注意：worktree 环境下使用 `git rev-parse --git-common-dir` 获取共享 git 目录。

### 5.5 与现有命令的关系

| 命令 | 分析对象 | 粒度 | 持久化 | 用途 |
|------|----------|------|--------|------|
| `inspect files` | 文件/目录 | 文件级 | 否 | 人类快速查看 |
| `inspect symbols` | 符号 | 符号级 | 否 | 引用分析 |
| `snapshot build/show/diff` | 代码库 | 模块级 | 是 | Agent 编排、质量治理 |

---

## 6. 数据与存储设计

### 6.1 存储位置

snapshot 是派生数据，不应进入 Git。

推荐存储在：

```text
.git/vibe3/structure/
  snapshots/
    <snapshot-id>.json
  latest.json
```

理由：

- 与 `.git/vibe3` 现有本地运行态一致
- 避免提交快照造成冲突
- 明确它不是仓库正文的一部分

### 6.2 Snapshot 最小模型

```json
{
  "snapshot_id": "2026-03-22T10-30-00Z_HEAD_abcd1234",
  "branch": "task/example",
  "commit": "abcd1234",
  "created_at": "2026-03-22T10:30:00Z",
  "root": "src/vibe3",
  "files": [],
  "modules": [],
  "metrics": {},
  "dependencies": []
}
```

最小要求：

- 可稳定序列化
- 字段顺序稳定
- 便于 handoff / review 引用

### 6.3 Diff 最小模型

```json
{
  "baseline": "snapshot-a",
  "current": "snapshot-b",
  "summary": {
    "files_changed": 3,
    "modules_changed": 2
  },
  "module_changes": [],
  "dependency_changes": [],
  "warnings": []
}
```

---

## 7. 质量信号设计

### 7.1 第一版必须支持的信号

1. 文件数量变化
2. 模块 LOC 变化
3. 函数数量变化
4. 依赖新增/移除
5. 目录级结构膨胀提示

### 7.2 第二版再补

1. duplication detection
2. 可疑目录越界
3. 更细粒度的 symbol 漂移

### 7.3 明确不做

1. 完整调用图
2. 数据流分析
3. 自动代码评分
4. 用 LLM 替代结构事实提取

---

## 8. 与现有能力的衔接

### 8.1 直接复用

- `vibe3 inspect structure` 的单文件/目录结构分析入口
- `dag_service` 的依赖关系能力
- `review` 链路的 explainability 输出

### 8.2 需要新增

- snapshot build/load/show
- diff build/show
- 稳定的 JSON schema
- 与 handoff / review 的挂接点

---

## 9. 与 handoff / review 的协议

### 9.1 handoff

handoff 不保存完整 snapshot 内容，只保存：

- `snapshot_id`
- 生成时间
- 是否存在高风险结构变化
- 需要接手者关注的模块

### 9.2 review

review 消费的不是“原始大 JSON”，而是 diff 摘要：

- 哪些模块变大了
- 新增了哪些依赖
- 是否出现重复实现趋势

### 9.3 状态机联动

推荐联动点：

- 进入 `state/handoff` 前：应有 snapshot
- 进入 `state/review` 前：应有 diff
- 进入垃圾代码回收流程前：应有 diff + warning

---

## 10. 实施顺序

### 第一阶段：snapshot 最小版

1. 保持 `vibe3 inspect structure` 入口不变
2. 增加 `--build`
3. 增加稳定存储位置
4. 输出最小 snapshot JSON

### 第二阶段：show / diff

1. 增加 `--show`
2. 增加 `--diff`
3. 输出文本摘要和 JSON 摘要

### 第三阶段：编排联动

1. handoff 引用 snapshot
2. review 引用 diff
3. 状态迁移前增加最小检查

### 第四阶段：重复与回收

1. duplication detection
2. 垃圾代码回收信号
3. orchestrator 消费结构风险

---

## 11. 验收标准

达到以下状态时，说明这套设计成立：

1. `vibe3 inspect structure --build` 能生成稳定 snapshot
2. `vibe3 inspect structure --diff` 能输出结构变化摘要
3. handoff 能引用 snapshot，而不是复制正文
4. review 能消费 diff，而不是只看纯 git diff
5. snapshot/diff 能作为垃圾代码回收的事实输入

---

## 12. 结论

`structure / snapshot / diff` 在目标态里不是“另一个分析工具”，而是：

- 多 agent 编排的质量治理层
- handoff 与 review 的结构事实来源
- 垃圾代码回收的核心输入之一

所以它的正确定位不是替代当前 inspect/review，而是在现有链路上补齐“可持久化、可比较、可审计”的能力。
