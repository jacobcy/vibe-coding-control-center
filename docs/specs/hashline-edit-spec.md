# Spec: Hashline Edit - `vibe hash` 锚点编辑协议

## 1. Overview

本 spec 定义 `vibe hash` 的第一版技术规格。

目标是在当前 repo 内提供一套给 agent 使用的锚点读/搜/改能力，避免模型基于陈旧文本直接覆盖写文件。

第一版仅包含 CLI，不包含 MCP 暴露。

## 2. Command Contracts

### 2.1 `vibe hash read <file>`

#### 输入

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `file` | `str` | repo 内相对路径或可解析到 repo 内的路径 | `src/vibe3/server/mcp.py` |

#### 输出

人类可读文本输出，逐行格式为：

```text
<line_no>#<hash>|<content>
```

示例：

```text
1#8f3a2b7c|"""MCP Server for Orchestra - exposes orchestra state to external AI agents."""
2#1c09bd42|
3#9a0c18ee|import json
```

#### 错误

| 错误码 | 说明 | 触发条件 |
|--------|------|----------|
| `PATH_OUT_OF_SCOPE` | 路径越界 | 文件不在 repo root 下 |
| `FILE_NOT_FOUND` | 文件不存在 | 目标文件不存在 |
| `NOT_A_FILE` | 不是普通文件 | 路径指向目录等 |
| `UNREADABLE_FILE` | 文件不可读 | 权限或编码读取失败 |

### 2.2 `vibe hash grep <pattern> [path]`

#### 输入

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `pattern` | `str` | 搜索模式，第一版按字面字符串处理 | `create_mcp_server` |
| `path` | `str` | 搜索根，默认当前 repo | `src/vibe3` |

#### 输出

逐条输出匹配项，最少包含：

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `file` | `str` | 匹配文件路径 | `src/vibe3/server/mcp.py` |
| `line` | `int` | 行号 | `101` |
| `hash` | `str` | 当前行 hash | `1f23ab45` |
| `text` | `str` | 当前行内容 | `def create_mcp_server(` |

文本模式建议为：

```text
src/vibe3/server/mcp.py:101:101#1f23ab45|def create_mcp_server(
```

#### 错误

| 错误码 | 说明 | 触发条件 |
|--------|------|----------|
| `PATH_OUT_OF_SCOPE` | 路径越界 | 搜索路径不在 repo root 下 |
| `SEARCH_ROOT_NOT_FOUND` | 搜索根不存在 | 指定 path 不存在 |

### 2.3 `vibe hash edit <file> --edits-file <json>`

#### 输入

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `file` | `str` | 目标文件路径 | `src/vibe3/server/mcp.py` |
| `edits-file` | `str` | JSON payload 文件路径 | `temp/hash-edit.json` |

#### JSON payload

第一版支持 3 类操作：

```json
{
  "edits": [
    {
      "op": "set_line",
      "ref": "3#9a0c18ee",
      "content": "import json as jsonlib"
    },
    {
      "op": "insert_after",
      "ref": "3#9a0c18ee",
      "content": "from pathlib import Path"
    },
    {
      "op": "replace_range",
      "start_ref": "10#abc12345",
      "end_ref": "12#def67890",
      "lines": [
        "new line 1",
        "new line 2"
      ]
    }
  ]
}
```

#### 输出

成功时返回摘要：

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `ok` | `bool` | 是否成功 | `true` |
| `file` | `str` | 目标文件 | `src/vibe3/server/mcp.py` |
| `applied` | `int` | 应用的 edit 数 | `2` |
| `written` | `bool` | 是否写回磁盘 | `true` |

失败时返回非零退出，并输出结构化错误摘要。

#### 错误

| 错误码 | 说明 | 触发条件 |
|--------|------|----------|
| `INVALID_PAYLOAD` | payload 不合法 | 缺字段、未知 op、JSON 解析失败 |
| `PATH_OUT_OF_SCOPE` | 路径越界 | 目标文件不在 repo root 下 |
| `HASH_MISMATCH` | 锚点不匹配 | 目标行内容已变化 |
| `LINE_REF_NOT_FOUND` | 锚点行不存在 | 行号超界或行被删除 |
| `OVERLAPPING_EDITS` | 编辑冲突 | 多个 edit 作用范围重叠 |
| `EMPTY_EDITS` | 空编辑列表 | `edits` 为空 |
| `WRITE_FAILED` | 写入失败 | 权限、磁盘或原子写入失败 |

## 3. Core Invariants

以下规则在任何情况下都必须成立：

1. 所有可写路径必须限制在 repo root 内。
2. `vibe hash edit` 只能在全部锚点校验通过时写入；任一 edit 失败则整次写入失败。
3. 第一版禁止无锚点替换；所有写操作都必须绑定至少一个 line ref。
4. 同一轮 edit 中若存在重叠范围，必须拒绝执行。
5. 读命令输出的 hash 必须由当前文件内容实时生成，不可缓存旧结果返回。
6. grep 返回的匹配锚点格式必须与 read/edit 使用的锚点格式一致。

## 4. Hash Rules

第一版 hash 规则：

1. 基于“单行内容”计算
2. 计算前统一移除 `\r`
3. 计算前对行内容执行 `rstrip()`，忽略尾随空白差异
4. hash 输出使用短十六进制字符串，长度固定

实现建议：

- 直接使用 Python 标准库哈希函数截断输出
- 不引入额外 native 依赖

说明：

- 第一版不要求与外部项目的 hash 算法二进制兼容
- 只要求在本仓库内格式稳定、行为可预测

## 5. Edit Semantics

### `set_line`

- 定位单行 `ref`
- 将该行替换为新内容
- 保留该行在文件中的位置

### `insert_after`

- 定位单行 `ref`
- 在其后插入一行或多行
- 不修改 anchor 行本身内容

### `replace_range`

- 定位 `start_ref` 到 `end_ref`
- 范围必须按当前文件顺序有效
- 用 `lines` 完整替换该闭区间内容

## 6. Mismatch Behavior

当出现 `HASH_MISMATCH` 或 `LINE_REF_NOT_FOUND` 时，命令必须：

1. 不写文件
2. 返回失败退出码
3. 输出最少以下诊断信息：
   - 原始 ref
   - 当前检测到的实际行内容
   - 若可定位，则返回新的建议 ref

示例：

```text
HASH_MISMATCH: expected 3#9a0c18ee
actual line 3: import json as js
suggested ref: 3#77bc91af
```

## 7. Files / Modules

建议模块拆分：

- `src/vibe3/hashline/models.py`
- `src/vibe3/hashline/hash_utils.py`
- `src/vibe3/hashline/refs.py`
- `src/vibe3/hashline/reader.py`
- `src/vibe3/hashline/grep.py`
- `src/vibe3/hashline/editor.py`
- `src/vibe3/commands/hash.py`

CLI 注册点：

- 在 [`src/vibe3/cli.py`](/Users/jacobcy/src/vibe-center/main/.worktrees/wt-claude-v3/src/vibe3/cli.py:48) 增加 `app.add_typer(hash.app, name="hash")`

测试建议：

- `tests/vibe3/hashline/test_hash_utils.py`
- `tests/vibe3/hashline/test_refs.py`
- `tests/vibe3/hashline/test_editor.py`
- `tests/vibe3/commands/test_hash_commands.py`

## 8. Boundary Behavior

### 空文件

- `read` 返回空输出
- `grep` 返回空结果
- `edit` 若引用任意行，返回 `LINE_REF_NOT_FOUND`

### 大文件

- 第一版按整文件内存处理
- 不做流式编辑
- 只要在常规源码文件范围内可接受即可

### 并发修改

- 第一版不提供文件锁
- 通过“读后 hash 校验”降低误改风险
- 如果读写期间文件被外部修改，应表现为 mismatch 或 write 失败

### 非 UTF-8 / 二进制文件

- 第一版只支持文本文件
- 编码无法按文本解析时，返回 `UNREADABLE_FILE`

## 9. Non-Functional Constraints

- 不新增 Bun / Node / daemon 依赖
- 仅使用当前 Python/uv 运行时
- 输出需足够稳定，便于 agent 解析
- 错误信息需尽量短且可操作
- 只做定向回归测试，不做本地全量测试默认要求

## 10. Delivery Phases

### Phase 1

- hash 核心算法
- line ref 解析
- `vibe hash read`
- 单元测试

### Phase 2

- `vibe hash grep`
- `vibe hash edit`
- overlap / mismatch / payload 校验
- CLI 测试

### Phase 3

- 文档补充
- agent 使用约定
- 评估是否需要 MCP 暴露

## 11. Effort Estimate

以“移植思路 + Python 重写宿主层”为前提，估算如下：

| 模块 | 工作量 |
|------|--------|
| 核心 hash / ref / model | 0.5 天 |
| reader / grep | 0.5 天 |
| editor / conflict detection | 1 天 |
| CLI 接线 | 0.5 天 |
| 测试与修边 | 0.5 到 1 天 |

总体：

- 实现最小版：约 2 到 3 天
- 如果同步做 MCP：额外增加 0.5 到 1 天

结论：

- 借鉴成本低于从零设计协议
- 但仍然需要认真处理编辑冲突、错误模型和测试
- 所以它不是“半天抄完”的活，但确实是一个工作量可控的中小功能
