# PRD: Hashline Edit - 面向 Agent 的安全锚点编辑能力

## 1. Overview

Hashline Edit 提供一套面向 AI agent 的“带内容锚点的读/搜/改协议”，用于降低 stale context 导致的误编辑风险。

本能力的目标不是替代 AST 分析，也不是做通用文件系统工具，而是为 agent 提供一种更安全的精确编辑路径：

1. 先读取带 hash 锚点的文件内容
2. 基于锚点生成编辑意图
3. 在写入前校验目标行是否仍然匹配
4. 不匹配时拒绝写入，并返回新的重试线索

推荐对外命令面为 `vibe hash`，而不是绑定在 `vibe3 inspect` 下。

## 2. Goals

- 为 agent 提供稳定、可脚本化的锚点编辑协议
- 在 repo 内实现最小可用版本，复用现有 `vibe3` CLI 体系
- 第一版覆盖 3 个核心动作：
  - `vibe hash read`
  - `vibe hash grep`
  - `vibe hash edit`
- 明确拒绝 fuzzy replace 和无锚点覆盖写入
- 为未来 MCP 暴露保留复用空间，但第一版不依赖 MCP 落地

## 3. Non-Goals

- 不做 AST/符号分析替代品
- 不做通用 filesystem server
- 不做跨 repo 或任意路径写入
- 不做 rename / delete / chmod 等扩展文件操作
- 不自动触发 formatter、lint、metadata publish 等宿主耦合逻辑
- 不直接移植 TypeScript/Bun 工具层；只借鉴核心算法与协议

## 4. User / Agent Scenarios

### 场景 A：agent 精确修改单文件

```text
vibe hash read src/vibe3/server/mcp.py
  -> agent 获取带锚点内容
agent 生成 edit payload
vibe hash edit src/vibe3/server/mcp.py --edits-file temp/hash-edit.json
  -> 若锚点未变，应用成功
  -> 若锚点已变，拒绝并提示最新锚点
```

### 场景 B：agent 先搜后改

```text
vibe hash grep "create_mcp_server" src/vibe3
  -> 返回匹配行及其锚点
agent 选中目标文件和目标行
vibe hash edit ...
```

### 场景 C：未来复用到 MCP

CLI 已有稳定核心逻辑后，可在现有 `src/vibe3/server/mcp.py` 上追加对应 tool，复用相同读/改引擎。

## 5. Core Data Flow

```text
文件路径 / 搜索模式
  -> 读取文件并生成 line#hash 锚点
  -> agent 基于锚点生成 edit payload
  -> edit 命令校验锚点
      -> 匹配：应用改动并写回
      -> 不匹配：拒绝改动并返回 mismatch 诊断
```

## 6. Command Surface

第一版命令面：

- `vibe hash read <file>`
- `vibe hash grep <pattern> [path]`
- `vibe hash edit <file> --edits-file <json>`

为什么不放进 `inspect`：

- `inspect` 的职责是“信息提供层”
- hashline 同时包含读和写
- 如果强塞进 `inspect`，写操作会让职责边界变模糊

## 7. Success Criteria

### 功能成功判据

- agent 能通过 `vibe hash read` 获得稳定的带锚点文本
- agent 能通过 `vibe hash grep` 获得带锚点的匹配结果
- `vibe hash edit` 只在锚点匹配时写入
- 锚点不匹配时，命令必须拒绝写入并返回可操作的诊断信息

### 边界成功判据

- 默认只允许操作当前 repo root 下文件
- 不支持 rename / delete / fuzzy replace
- 空编辑、冲突编辑、越界编辑必须显式失败

### 工程成功判据

- 核心逻辑与 CLI/MCP 包装解耦
- 有定向回归测试覆盖 read / grep / edit / mismatch / overlap
- 第一版不引入 Bun、Node runtime 或额外守护进程依赖

## 8. Implementation Strategy

采用“借鉴协议，重写宿主层”的方案。

### 可借鉴部分

- hash 计算规则
- line ref 解析
- 锚点校验逻辑
- edit 去重 / 排序 / 冲突检测
- mismatch 提示格式

### 不借鉴部分

- OpenAgent / Pi / Bun 绑定代码
- formatter 自动触发
- plugin metadata / runtime hooks
- 宽松替换 fallback

## 9. Effort Assessment

结论：如果按“Python 重写核心逻辑 + `vibe hash` CLI”执行，工作量不大，属于一个中小型功能。

### 粗略拆分

- 核心数据结构与 hash 算法：0.5 天
- read / grep / edit 核心引擎：1 天
- CLI 接线：0.5 天
- 测试与边界修正：0.5 到 1 天
- 文档与 agent 使用约定：0.5 天

### 总体估算

- 乐观：2 天
- 稳健：2.5 到 3 天

前提：

- 只做第一版最小范围
- 不同步做 MCP
- 不加 formatter / rename / delete 等扩展能力

## 10. Risks

- hash 规则如果选得太脆弱，会导致频繁 mismatch
- hash 规则如果选得太宽松，会削弱“防误改”价值
- edit payload 设计如果过于复杂，会增加 agent 使用难度
- 如果第一版同时做 CLI + MCP，会放大测试面和维护成本

## 11. Recommendation

建议立项为：

1. 先做 `vibe hash` CLI 第一版
2. 用 Python 重写核心逻辑
3. 完成定向测试后，再评估是否向 MCP 暴露

这样收益明确、范围可控，也最符合当前仓库的工具分层。
