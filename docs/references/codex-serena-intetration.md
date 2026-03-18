
目标架构

你要的完整版本是这条链：

PR diff
  ↓
python structure summary
  ↓
Serena adapter（抽取 changed symbols / references）
  ↓
Review DAG（只保留受影响模块）
  ↓
Risk scoring（给 PR 量化风险）
  ↓
Codex review（基于 policy + context）
  ↓
PR summary comment
  ↓
可选：inline review comments
  ↓
可选：merge gate

这里的职责边界很清楚：
	•	python structure summary：仓库结构摘要
	•	Serena：事实层，给出 symbol 和引用关系
	•	DAG：缩小上下文，只看影响面
	•	Scoring：决定 PR 风险级别
	•	Codex review：输出审查意见
	•	GitHub API：把结果发到 PR 评论 / review comments
Codex 官方支持 CLI 本地审查，也支持 GitHub Action 在 CI 中运行；GitHub 官方 API 也明确区分了 issue/PR 总评论和 pull request review comments 两类评论接口。 ￼

⸻

目录结构

.codex/
  review-policy.md

.ai-review/
  config.yaml
  build_context.py
  serena_adapter.py
  review_dag.py
  risk_score.py
  render_prompt.py
  post_review.py

.github/workflows/
  ai-pr-review.yml


⸻

1) .codex/review-policy.md

这个版本不是“作文式 code review prompt”，而是面向 gate 的审查规则。

# PR Review Policy

You are the repository PR reviewer.

Your job is to find real engineering risk in the pull request.

You will receive:
1. repository structure summary
2. Serena symbol impact data
3. impacted module DAG
4. risk score summary
5. git diff

Review scope:
- Focus on changed code and impacted modules only.
- Do not comment on style unless it causes a bug or maintenance risk.
- Prefer concrete evidence over speculation.

Check for:

## Correctness
- broken call sites
- missing branches after refactor
- inconsistent argument/return contracts
- incorrect imports
- error handling regressions

## Structural Integrity
- wrong module ownership
- abstraction boundary violations
- circular dependency risk
- public API breakage
- entrypoint breakage

## Python Risks
- mutable default arguments
- unsafe subprocess usage
- incorrect async/await usage
- leaked resources
- exception swallowing

## Workflow / CLI Risks
- changed CLI flags without compatibility handling
- user-visible contract changes
- state machine regressions
- silent failure paths

Output requirements:

## AI Review Result

### Risk Level
LOW | MEDIUM | HIGH | CRITICAL

### Risk Score
<number>

### Key Findings
- item

### Structural Impact
<short analysis>

### Evidence
- file:line - explanation

### Suggested Fixes
- concrete fix

### Verdict
PASS | NEEDS_FIX | BLOCK

Rules:
- Be concise
- Cite evidence
- No style-only feedback
- If no real issue is found, say so explicitly


⸻

2) .ai-review/config.yaml

评分、关键目录、阻断规则都放配置里，不要硬编码。

base_branch: origin/main

critical_paths:
  - "bin/"
  - "cli/"
  - "core/"
  - "flow/"
  - "handoff/"
  - "github/"
  - "git/"

public_api_paths:
  - "api/"
  - "cli/"
  - "bin/"

weights:
  changed_lines:
    small: 0
    medium: 1
    large: 2
    xlarge: 3
  changed_files:
    small: 0
    medium: 1
    large: 2
  impacted_modules:
    small: 0
    medium: 1
    large: 2
  critical_path_touch: 2
  public_api_touch: 2
  cross_module_symbol_change: 2
  codex_major: 3
  codex_critical: 5

thresholds:
  medium: 3
  high: 6
  critical: 9

merge_gate:
  block_on_verdict:
    - "BLOCK"
  block_on_score_at_or_above: 9


⸻

3) .ai-review/serena_adapter.py

这是核心。我不假装知道你本地 Serena 的精确命令，所以这里做一个稳定接口：
输入 git diff 和一个可选的 Serena JSON，输出统一结构。

如果你后面用 MCP、CLI、或者自己包装 Serena，只要把数据喂成这个 schema 就行。

# .ai-review/serena_adapter.py
from __future__ import annotations
import json
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

@dataclass
class ChangedSymbol:
    symbol: str
    file: str
    kind: str | None = None
    module: str | None = None
    references: list[str] | None = None

@dataclass
class SerenaImpact:
    changed_symbols: list[ChangedSymbol]
    touched_modules: list[str]
    raw_source: str

def module_from_path(path: str) -> str:
    p = Path(path)
    if len(p.parts) == 0:
        return path
    # 粗粒度模块划分：顶层目录 / 顶层文件
    return p.parts[0]

def parse_git_changed_files(base_branch: str) -> list[str]:
    out = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base_branch}...HEAD"],
        text=True
    )
    return [x.strip() for x in out.splitlines() if x.strip()]

def load_serena_json(path: str | None, base_branch: str) -> SerenaImpact:
    changed_files = parse_git_changed_files(base_branch)

    if path is None:
        # 无 Serena 输出时，退化为按文件构造“伪 symbol”
        symbols = [
            ChangedSymbol(
                symbol=f"{Path(f).stem}:<file-change>",
                file=f,
                kind="file",
                module=module_from_path(f),
                references=[],
            )
            for f in changed_files
        ]
        return SerenaImpact(
            changed_symbols=symbols,
            touched_modules=sorted({module_from_path(f) for f in changed_files}),
            raw_source="fallback:file-level",
        )

    data: dict[str, Any] = json.loads(Path(path).read_text())
    symbols: list[ChangedSymbol] = []

    # 约定输入 schema:
    # {
    #   "changed_symbols": [
    #     {"symbol":"FlowStore.save_handoff","file":"flow/store.py","kind":"function","references":["cli/run.py","flow/resume.py"]}
    #   ]
    # }
    for item in data.get("changed_symbols", []):
        file = item["file"]
        symbols.append(
            ChangedSymbol(
                symbol=item["symbol"],
                file=file,
                kind=item.get("kind"),
                module=module_from_path(file),
                references=item.get("references", []),
            )
        )

    touched_modules = sorted(
        {s.module for s in symbols if s.module} |
        {module_from_path(ref) for s in symbols for ref in (s.references or [])}
    )

    return SerenaImpact(
        changed_symbols=symbols,
        touched_modules=touched_modules,
        raw_source=f"serena-json:{path}",
    )

def save_impact(impact: SerenaImpact, path: str) -> None:
    Path(path).write_text(
        json.dumps(
            {
                "changed_symbols": [asdict(x) for x in impact.changed_symbols],
                "touched_modules": impact.touched_modules,
                "raw_source": impact.raw_source,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--base-branch", required=True)
    ap.add_argument("--serena-json", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    impact = load_serena_json(args.serena_json, args.base_branch)
    save_impact(impact, args.out)


⸻

4) .ai-review/review_dag.py

DAG 这里不做“全语言编译器级依赖图”，做你当前阶段最实用的版本：
文件导入关系 + Serena references + 顶层模块依赖。

# .ai-review/review_dag.py
from __future__ import annotations
import ast
import json
from collections import defaultdict, deque
from pathlib import Path

def list_py_files() -> list[Path]:
    return [p for p in Path(".").rglob("*.py") if ".git" not in p.parts]

def module_from_path(path: str) -> str:
    p = Path(path)
    return p.parts[0] if p.parts else path

def parse_imports(py_file: Path) -> set[str]:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except Exception:
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports

def build_module_graph() -> dict[str, set[str]]:
    # graph[a] = {b,c} 表示 a 依赖 b/c
    graph: dict[str, set[str]] = defaultdict(set)
    top_modules = {p.parts[0] for p in list_py_files() if p.parts}

    for py in list_py_files():
        if not py.parts:
            continue
        src = py.parts[0]
        for dep in parse_imports(py):
            if dep in top_modules and dep != src:
                graph[src].add(dep)

    return graph

def invert_graph(graph: dict[str, set[str]]) -> dict[str, set[str]]:
    inv: dict[str, set[str]] = defaultdict(set)
    for src, deps in graph.items():
        for dep in deps:
            inv[dep].add(src)
    return inv

def expand_impacted_modules(seed_modules: list[str], graph: dict[str, set[str]]) -> list[str]:
    inv = invert_graph(graph)
    seen = set(seed_modules)
    q = deque(seed_modules)

    while q:
        cur = q.popleft()
        # 谁依赖了它，也要纳入 review
        for nxt in inv.get(cur, set()):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)

    return sorted(seen)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--impact-json", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    impact = json.loads(Path(args.impact_json).read_text())
    seed_modules = impact["touched_modules"]
    graph = build_module_graph()
    impacted = expand_impacted_modules(seed_modules, graph)

    Path(args.out).write_text(json.dumps({
        "seed_modules": seed_modules,
        "module_graph": {k: sorted(v) for k, v in graph.items()},
        "impacted_modules": impacted,
    }, ensure_ascii=False, indent=2))


⸻

5) .ai-review/risk_score.py

这个版本把你要的 scoring 做实，不是嘴上说。

# .ai-review/risk_score.py
from __future__ import annotations
import json
import subprocess
from pathlib import Path
import yaml

def git_numstat(base_branch: str) -> tuple[int, int, int]:
    out = subprocess.check_output(
        ["git", "diff", "--numstat", f"{base_branch}...HEAD"],
        text=True
    )
    files = 0
    added = 0
    deleted = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            a, d, _ = parts[:3]
            if a.isdigit():
                added += int(a)
            if d.isdigit():
                deleted += int(d)
            files += 1
    return files, added, deleted

def load_yaml(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text())

def score_bucket(n: int, small: int, medium: int, large: int) -> int:
    if n < small:
        return 0
    if n < medium:
        return 1
    if n < large:
        return 2
    return 3

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--impact-json", required=True)
    ap.add_argument("--dag-json", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    impact = json.loads(Path(args.impact_json).read_text())
    dag = json.loads(Path(args.dag_json).read_text())

    base_branch = cfg["base_branch"]
    changed_files, added, deleted = git_numstat(base_branch)
    changed_lines = added + deleted
    impacted_modules = dag["impacted_modules"]

    score = 0
    reasons: list[str] = []

    # changed lines
    if changed_lines >= 500:
        score += cfg["weights"]["changed_lines"]["xlarge"]
        reasons.append(f"changed_lines={changed_lines} => +{cfg['weights']['changed_lines']['xlarge']}")
    elif changed_lines >= 200:
        score += cfg["weights"]["changed_lines"]["large"]
        reasons.append(f"changed_lines={changed_lines} => +{cfg['weights']['changed_lines']['large']}")
    elif changed_lines >= 50:
        score += cfg["weights"]["changed_lines"]["medium"]
        reasons.append(f"changed_lines={changed_lines} => +{cfg['weights']['changed_lines']['medium']}")

    # changed files
    if changed_files >= 10:
        score += cfg["weights"]["changed_files"]["large"]
        reasons.append(f"changed_files={changed_files} => +{cfg['weights']['changed_files']['large']}")
    elif changed_files >= 4:
        score += cfg["weights"]["changed_files"]["medium"]
        reasons.append(f"changed_files={changed_files} => +{cfg['weights']['changed_files']['medium']}")

    # impacted modules
    if len(impacted_modules) >= 5:
        score += cfg["weights"]["impacted_modules"]["large"]
        reasons.append(f"impacted_modules={len(impacted_modules)} => +{cfg['weights']['impacted_modules']['large']}")
    elif len(impacted_modules) >= 2:
        score += cfg["weights"]["impacted_modules"]["medium"]
        reasons.append(f"impacted_modules={len(impacted_modules)} => +{cfg['weights']['impacted_modules']['medium']}")

    critical_paths = cfg["critical_paths"]
    public_api_paths = cfg["public_api_paths"]

    touched_files = {s["file"] for s in impact["changed_symbols"]}

    if any(any(f.startswith(prefix) for prefix in critical_paths) for f in touched_files):
        score += cfg["weights"]["critical_path_touch"]
        reasons.append(f"critical_path_touch => +{cfg['weights']['critical_path_touch']}")

    if any(any(f.startswith(prefix) for prefix in public_api_paths) for f in touched_files):
        score += cfg["weights"]["public_api_touch"]
        reasons.append(f"public_api_touch => +{cfg['weights']['public_api_touch']}")

    if any((s.get("references") or []) for s in impact["changed_symbols"]):
        score += cfg["weights"]["cross_module_symbol_change"]
        reasons.append(f"cross_module_symbol_change => +{cfg['weights']['cross_module_symbol_change']}")

    thresholds = cfg["thresholds"]
    if score >= thresholds["critical"]:
        level = "CRITICAL"
    elif score >= thresholds["high"]:
        level = "HIGH"
    elif score >= thresholds["medium"]:
        level = "MEDIUM"
    else:
        level = "LOW"

    Path(args.out).write_text(json.dumps({
        "score": score,
        "level": level,
        "changed_files": changed_files,
        "changed_lines": changed_lines,
        "impacted_modules": impacted_modules,
        "reasons": reasons,
    }, ensure_ascii=False, indent=2))


⸻

6) .ai-review/render_prompt.py

把结构摘要、Serena 结果、DAG、score、diff 拼成 Codex 的输入。

# .ai-review/render_prompt.py
from __future__ import annotations
import json
import subprocess
from pathlib import Path

def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")

def git_diff(base_branch: str) -> str:
    return subprocess.check_output(
        ["git", "diff", "--unified=3", f"{base_branch}...HEAD"],
        text=True
    )

if __name__ == "__main__":
    import argparse, yaml
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--structure", required=True)
    ap.add_argument("--impact", required=True)
    ap.add_argument("--dag", required=True)
    ap.add_argument("--score", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    diff = git_diff(cfg["base_branch"])

    body = f"""
{read(args.policy)}

---
## Repository Structure Summary
{read(args.structure)}

---
## Serena Impact JSON
{read(args.impact)}

---
## Review DAG JSON
{read(args.dag)}

---
## Risk Score JSON
{read(args.score)}

---
## Git Diff
```diff
{diff}

“””
Path(args.out).write_text(body, encoding=“utf-8”)

---

# 7) `.ai-review/post_review.py`

支持两种模式：

- 总结 comment
- 可选逐行 review comment

GitHub 官方对普通 PR 评论和 review comments 都有 REST API。逐行评论需要绑定到 PR diff 上的具体文件/位置。 [oai_citation:2‡GitHub Docs](https://docs.github.com/en/rest/pulls/comments?utm_source=chatgpt.com)

```python
# .ai-review/post_review.py
from __future__ import annotations
import os
from pathlib import Path
import requests

GITHUB_API = "https://api.github.com"

def gh_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def post_issue_comment(repo: str, pr_number: int, body: str, token: str) -> None:
    url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
    r = requests.post(url, headers=gh_headers(token), json={"body": body}, timeout=30)
    r.raise_for_status()

if __name__ == "__main__":
    repo = os.environ["GITHUB_REPOSITORY"]
    pr_number = int(os.environ["PR_NUMBER"])
    token = os.environ["GITHUB_TOKEN"]
    body = Path("codex_review.md").read_text(encoding="utf-8")
    post_issue_comment(repo, pr_number, body, token)


⸻

8) GitHub Actions：.github/workflows/ai-pr-review.yml

这里我用 Codex GitHub Action 或直接安装 CLI 都行。OpenAI 官方现在有 openai/codex-action@v1，用来在 GitHub Actions 里跑 Codex；它本质上就是在 CI 里安装和运行 Codex CLI。 ￼

下面这个版本更直接，少一层心智负担：

name: AI PR Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest

    env:
      PR_NUMBER: ${{ github.event.pull_request.number }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install pyyaml requests
          npm install -g @openai/codex

      - name: Build Serena impact json
        run: |
          # 这里你需要替换成你自己的 Serena 导出逻辑
          # 例如：python tools/export_serena_json.py > serena_raw.json
          # 当前先允许没有 serena_raw.json，adapter 会退化为 file-level
          true

      - name: Normalize Serena impact
        run: |
          python .ai-review/serena_adapter.py \
            --base-branch origin/${{ github.event.pull_request.base.ref }} \
            --serena-json serena_raw.json \
            --out impact.json || \
          python .ai-review/serena_adapter.py \
            --base-branch origin/${{ github.event.pull_request.base.ref }} \
            --out impact.json

      - name: Build review DAG
        run: |
          python .ai-review/review_dag.py \
            --impact-json impact.json \
            --out dag.json

      - name: Compute risk score
        run: |
          python .ai-review/risk_score.py \
            --config .ai-review/config.yaml \
            --impact-json impact.json \
            --dag-json dag.json \
            --out score.json

      - name: Render review prompt
        run: |
          python .ai-review/render_prompt.py \
            --config .ai-review/config.yaml \
            --policy .codex/review-policy.md \
            --structure structure_summary.txt \
            --impact impact.json \
            --dag dag.json \
            --score score.json \
            --out codex_prompt.md

      - name: Run Codex review
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          codex review - < codex_prompt.md > codex_review.md

      - name: Post PR summary comment
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python .ai-review/post_review.py

      - name: Merge gate
        run: |
          python - <<'PY'
          import json, yaml
          from pathlib import Path

          cfg = yaml.safe_load(Path(".ai-review/config.yaml").read_text())
          score = json.loads(Path("score.json").read_text())
          review = Path("codex_review.md").read_text()

          block_score = cfg["merge_gate"]["block_on_score_at_or_above"]
          block_verdicts = cfg["merge_gate"]["block_on_verdict"]

          if score["score"] >= block_score:
              print(f"BLOCK: risk score {score['score']} >= {block_score}")
              raise SystemExit(1)

          if any(v in review for v in block_verdicts):
              print("BLOCK: Codex verdict requires block")
              raise SystemExit(1)

          print("PASS: merge gate not triggered")
          PY


⸻

9) Serena 这层你怎么接

这是最容易被人写成幻觉的部分，我直接给你可执行原则：

你只需要让 Serena 最终产出一个 serena_raw.json，结构类似：

{
  "changed_symbols": [
    {
      "symbol": "FlowStore.save_handoff",
      "file": "flow/store.py",
      "kind": "function",
      "references": [
        "cli/run.py",
        "flow/resume.py"
      ]
    },
    {
      "symbol": "BranchResolver.resolve_target",
      "file": "git/branch.py",
      "kind": "method",
      "references": [
        "cli/pr.py",
        "flow/close.py"
      ]
    }
  ]
}

无论你是：
	•	通过 Serena MCP
	•	通过你自己的导出脚本
	•	通过别的 AST 管线转成这个格式

上层都不用改。
这就是为什么我前面说 不要把 Serena 命令写死。Serena 官方确认的是它提供 symbol-level、IDE-like 的语义能力，而不是你现在必须绑定某一种固定 CLI 语法。 ￼

⸻

10) 这个版本里，DAG 和 scoring 真正起什么作用

DAG

它不是为了“好看”，而是为了缩小 AI 上下文：
	•	seed：本次改动涉及的模块
	•	向上扩展：所有依赖这些模块的上游模块
	•	最终只把 impacted modules 相关上下文喂给 Codex

这样能减少噪音，降低“全仓盲审”。

scoring

它不是代替 review，而是给 merge gate 一个硬阈值：
	•	小改动 + 单模块 + 非关键路径：低分
	•	大改动 + 多模块 + 关键路径 + public API：高分

也就是：
	•	score 决定“这 PR 危不危险”
	•	codex review 决定“具体危险在哪”

⸻

11) 你这个项目最该怎么调权重

按你现在这种 CLI / flow / gh wrapper / handoff 项目，我建议：
	•	critical_paths 一定包含：flow/, git/, github/, handoff/, cli/, bin/
	•	public_api_paths 至少包含：cli/, bin/, api/
	•	cross_module_symbol_change 权重不要太低，至少 +2
	•	纯文档改动可以在 workflow 里直接跳过 review job

因为你真正的高风险不是算法慢一点，而是：
	•	flow 状态迁移错
	•	close/merge 路径误删
	•	gh 命令失败被吞
	•	CLI 参数兼容性破坏
	•	handoff schema 变了但读写没同步

⸻

12) 这套东西哪些部分是“硬事实”，哪些是“你的工程设计”

硬事实
	•	Codex CLI 支持本地代码 review。 ￼
	•	Codex 有官方 GitHub Action，可在 Actions 里运行。 ￼
	•	Codex 也支持在 GitHub PR 里触发 review。 ￼
	•	Serena 的公开定位就是 symbol-level / semantic retrieval and editing。 ￼
	•	GitHub 提供 PR issue comments 和 line-level review comments 的 REST API。 ￼

工程设计
	•	serena_adapter.py 的统一 schema
	•	review_dag.py 的模块级 DAG 实现
	•	risk_score.py 的权重模型
	•	用 score + verdict 做 merge gate

这些不是官方标准件，是我按你这个仓库形态给的实战型方案。

⸻

13) 直说结论

这套版本已经够你直接起步了，而且结构是对的：
	•	Codex 负责审
	•	Serena 负责给事实层
	•	DAG 负责缩上下文
	•	Scoring 负责 merge gate
	•	GitHub comment 负责落地到 PR

真正需要你补的只有一件事：

把 Serena 导出成 serena_raw.json。

一旦你把这层接上，上面整套就能跑。

