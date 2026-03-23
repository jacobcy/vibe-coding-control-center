# vibe3 inspect diff Check 设计

**日期**: 2026-03-22
**状态**: Draft
**定位**: 定义面向 agent 改动的本地 diff 质量闸，作为 snapshot/diff 质量层的执行入口之一

---

## 1. 问题定义

当多 agent 编排跑起来以后，风险不只是“任务有没有推进”，还包括：

- 是否越 scope 乱改
- 是否一次改了太多无关文件
- 是否引入结构级膨胀
- 是否把垃圾代码更快地产生出来

因此需要一个本地 diff 检查入口，在 handoff、review、commit 之前给出最小质量判断。

---

## 2. 目标

定义 `vibe3 inspect diff --check` 的目标态能力：

- 读取当前 git diff
- 结合 task 边界、structure snapshot、structure diff
- 输出可读的违规报告
- 为 handoff / review / 垃圾代码回收提供统一入口

这不是替代 review，也不是替代 PR risk gate。

当前仓库还没有 `vibe3 inspect diff` 命令；这份文档定义的是目标接口和落地路径。

---

## 3. 它在整体系统中的位置

```text
agent 修改代码
  -> git diff
  -> vibe3 inspect diff --check
  -> handoff / review / commit / PR
```

它属于：

- 本地执行阶段的质量闸
- 编排系统中的“产出检查”层

它不属于：

- GitHub 状态机
- handoff 正文
- Project UI

---

## 4. 输入

`vibe3 inspect diff --check` 的目标输入应包括：

1. 当前 git diff
2. 当前 flow / issue 最小上下文
3. task scope 或任务边界
4. 可选的 structure snapshot
5. 可选的 structure diff

---

## 5. 输出

### 5.1 文本输出

```text
[ERROR][SCOPE] src/unrelated.py is outside declared task scope
[WARN ][SIZE ] 12 files changed, consider splitting
[WARN ][ARCH ] dependency added: services/task -> clients/github
[OK   ][MIN  ] changes stay within expected modules
```

### 5.2 退出码

- 有 `ERROR`：退出码 1
- 只有 `WARN`：退出码 0
- 全部 `OK`：退出码 0

### 5.3 JSON 输出

供 handoff、review、未来 orchestrator 消费：

```json
{
  "ok": false,
  "errors": [],
  "warnings": [],
  "summary": {}
}
```

---

## 6. 检查维度

### 6.1 第一阶段必须有

### A. Scope 边界检查

检查是否越出当前任务边界。

可用输入：

- task 文档中的 scope
- handoff 中声明的关注模块
- 当前 flow 已绑定 issue 的上下文

### B. 改动规模检查

检查：

- 改动文件数量
- 单文件改动量
- 是否接近“整文件重写”

### C. 结构漂移检查

如果存在 structure diff，则检查：

- 新增依赖
- 模块 LOC 异常膨胀
- 函数数量异常增加

### 6.2 第二阶段再补

### D. 重复实现趋势

结合 duplication 信息判断：

- 是否新增重复实现
- 是否把已有重复继续扩散

### E. 垃圾代码回收建议

在不阻断执行的前提下给出：

- 建议拆分
- 建议回收
- 建议后续 cleanup

---

## 7. 与现有能力的关系

### 7.1 不替代 PR Risk Gate

仓库已有 `pr ready` 时触发的 risk gate，用于 PR 级风险判断。  
`vibe3 inspect diff --check` 解决的是更早阶段的问题：

- 还没到 PR
- 还没进入最终 review
- 但已经需要一个本地质量卡口

### 7.2 不替代 pre-commit

pre-commit 更偏语法、格式、基础质量。  
`vibe3 inspect diff --check` 更偏：

- agent 行为边界
- 任务范围边界
- 结构级扩散风险

### 7.3 依赖 structure/snapshot/diff

如果没有结构基线，它仍可运行，但能力会降级为：

- scope 检查
- 文件规模检查

有 snapshot/diff 时，才能升级到结构级治理。

---

## 8. 推荐规则分级

| 规则组 | 严重级别 | 说明 |
|--------|---------|------|
| `SCOPE` | ERROR | 越界改动 |
| `SIZE` | WARN | 改动过大或应拆分 |
| `ARCH` | WARN/ERROR | 结构漂移，视阈值决定 |
| `DUP` | WARN | 重复实现趋势 |
| `RECYCLE` | WARN | 建议进入垃圾代码回收 |

---

## 9. 与状态机的联动

### 9.1 推荐联动点

- 从 `state/in-progress` 进入 `state/handoff` 前运行一次
- 从 `state/in-progress` 进入 `state/review` 前运行一次
- 进入垃圾代码回收时运行一次

### 9.2 联动原则

- `diff check` 不直接改 label
- 它只提供事实和建议
- 是否阻断状态迁移，由上层规则决定

---

## 10. 最小实施路径

### 第一阶段

1. 提供 `vibe3 inspect diff --check`
2. 只做 scope + size 检查
3. 输出文本和 JSON

### 第二阶段

1. 接 structure diff
2. 加入架构漂移提示
3. 与 handoff/review 对接

### 第三阶段

1. 加 duplication 趋势
2. 接垃圾代码回收流程
3. 给 orchestrator 提供质量信号

---

## 11. 验收标准

1. agent 在本地就能发现明显越界改动
2. handoff / review 前能拿到一致的 diff 摘要
3. 结构漂移能在 PR 前暴露，而不是到 merge 后才发现
4. 垃圾代码回收有明确触发依据，而不是凭感觉

---

## 12. 结论

`vibe3 inspect diff --check` 的正确定位不是“另一个 lint”，而是：

- 多 agent 编排里的本地质量闸
- 连接 git diff 与 structure diff 的桥
- 垃圾代码回收的早期触发器
