# PRD: Structure Snapshot - 代码结构快照系统

1. Goal

Provide a stable, hierarchical code structure snapshot for:
	•	human inspection
	•	agent-based review
	•	branch-level structural diff

⸻

2. CLI Design

structure build        # 生成 snapshot
structure show         # 查看结构摘要
structure diff A B     # 对比两个 snapshot


⸻

3. Output Layout

.project-root/
  .structure/
    snapshot.json

单一文件，避免分散复杂性（先不要拆 module 文件）

⸻

4. Core Data Model（核心）

4.1 snapshot.json

{
  "version": "1.0",

  "global": {
    "total_files": 120,
    "total_loc": 18000,
    "total_modules": 12
  },

  "modules": [
    {
      "name": "services/user",
      "path": "services/user",

      "metrics": {
        "files": 5,
        "loc": 820
      },

      "dependencies": [
        "utils",
        "db"
      ],

      "structure": {
        "functions": 34,
        "function_hashes": ["abc123", "def456"]
      }
    }
  ],

  "duplication": [
    {
      "hash": "abc123",
      "count": 4,
      "modules": ["services/user", "utils"]
    }
  ]
}


⸻

5. Module Definition（重要）

module = 目录（folder）

规则：

- 每个“有代码文件的目录” = 一个 module
- 忽略：
  - __tests__ / test
  - node_modules
  - .git


⸻

6. Data Extraction Rules

⸻

6.1 Metrics（复用你现有）

{
  "files": number,
  "loc": number
}


⸻

6.2 Dependencies（轻量）

来源：

import / require / from ... import

规则：
	•	只记录 module-level
	•	去重
	•	忽略第三方（可选）

⸻

6.3 Function Hash（关键）

规则：

AST → normalize → hash

normalize：
	•	去变量名
	•	去常量值
	•	保留结构

目标：

相同逻辑 → 相同 hash


⸻

6.4 Duplication（全局）

hash → 出现次数 > 1

聚合为：

{
  "hash": "...",
  "count": 4,
  "modules": [...]
}


⸻

7. Commands

⸻

7.1 structure build

功能
	•	扫描 repo
	•	构建 snapshot
	•	写入 .structure/snapshot.json

⸻

过程

scan files
↓
group by module
↓
collect metrics
↓
extract dependencies
↓
compute function hashes
↓
build duplication map
↓
write snapshot


⸻

7.2 structure show

输出（文本）

[Global]
modules: 12
files: 120
loc: 18000

[Top Modules by LOC]
utils           9200
services        5400

[Duplication]
hash abc123 × 6 (modules: utils, services)

[Dependencies]
services → utils
services → db


⸻

👉 只做 summary，不打印细节

⸻

7.3 structure diff A B

⸻

输入

structure diff main feature-branch

内部：

build snapshot(A)
build snapshot(B)
compare


⸻

输出

[Global Changes]
LOC +300
files +12

[Module Changes]
services/user:
  LOC +120
  functions +5

[Duplication Changes]
hash abc123: 2 → 5

[Dependency Changes]
+ services → db/raw


⸻

Diff JSON（给 agent）

{
  "modules": {
    "services/user": {
      "loc_change": 120,
      "functions_change": 5,
      "dependencies_added": ["db/raw"]
    }
  },

  "duplication": {
    "abc123": {
      "before": 2,
      "after": 5
    }
  }
}


⸻

8. Non-Goals（明确边界）

不做：
	•	❌ PR实时分析
	•	❌ call graph
	•	❌ 数据流分析
	•	❌ 自动代码质量判断
	•	❌ LLM分析（这一层不做）

⸻

9. Agent Integration（关键）

agent 输入：

- snapshot.json
- diff.json（可选）

agent 负责：
	•	是否需要重构
	•	是否重复实现
	•	是否结构异常

⸻

10. Implementation Notes（落地建议）

⸻

10.1 优先级
	1.	metrics（你已有）
	2.	module grouping
	3.	dependency extraction
	4.	hash（最后做）

⸻

10.2 语言支持

建议：
	•	第一版只做 Python / TS
	•	或直接 tree-sitter

⸻

10.3 稳定性要求

snapshot.json 必须：
	•	key 顺序稳定
	•	字段不随意变化
	•	version 字段必须存在

⸻

11. 最小可交付（MVP）

做到以下即可上线：

✔ structure build
✔ module metrics
✔ dependencies
✔ duplication（hash）
✔ structure show
✔ structure diff（基础版）


⸻

12. 一句话总结

这是一个“结构快照系统”，不是分析系统；它的价值在于为 agent 提供稳定、可对比的代码结构上下文。

