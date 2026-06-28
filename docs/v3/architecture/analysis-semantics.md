# Inspect 证据语义

> **Updated**: 2026-06-28 — Issue #3218

`vibe3 inspect` 是 PR/review 的补充观察窗口，只输出可回指 Git object、当前文件内容或有效源码范围的证据。它不预测运行时影响，不计算风险分数，也不判断 dead code。

## 公共命令

```bash
vibe3 inspect base [<base>] --json
vibe3 inspect files <file.py> --json
vibe3 inspect symbols <file.py>:<symbol> --json
```

只保留 `base`、`files`、`symbols`。`pr`、`commit`、`uncommit`、`commands`、`dead-code` 不属于公共接口。

## `inspect base`

Schema version 为 `1`。Git 比较范围是 `merge-base(resolved_base, HEAD)..HEAD`，并分别报告：

- committed、staged、unstaged、untracked；
- HEAD、resolved base、exact merge-base SHA；
- rename、delete、binary、numstat；
- Architecture/Review Kernel 精确文件命中；
- 最低 review depth：`normal`、`focused`、`repeated`。

`kernel.impact` 只有 `none`、`small`、`large`，表示对仓库定义核心文件的命中程度，不是运行时影响预测。`impact_analysis.status` 固定为 `disabled`，原因是现有 benchmark 未通过可靠性门槛。

## `inspect files`

只接受一个 Python 文件，输出 content SHA256、总行数、AST declaration 的 1-based inclusive range 和直接 imports。不扫描目录，不生成 imported-by 或依赖扩散。

## `inspect symbols`

只接受显式 `<file>:<symbol>`。输出经校验的 definition 和静态 provider 观察到的正向引用，范围统一为 1-based inclusive。

`observed_reference_count: 0` 不等于 unused；`complete` 固定为 `false`。provider 不可用或范围无效时返回 `partial`/`disabled`/`unknowns`，不得伪造空成功。

## Review 消费契约

`ReviewRequest.observation` 复用同一个 `ReviewObservation` model。PR show/create 和 reviewer briefing 仅在当前 worktree 能提供精确 Git 比较时消费它；无法验证时省略或明确 unavailable，不回退到旧评分或 DAG 数据。

## 真源

- Git change truth：`src/vibe3/analysis/review_observation.py`
- Review Kernel：`config/v3/review_kernel.yaml`
- Architecture Kernel taxonomy：`src/vibe3/runtime/taxonomy.py`
- 单文件 AST：`src/vibe3/analysis/python_file_inspector.py`
- symbol provider adapter：`src/vibe3/analysis/symbol_reference_service.py`
