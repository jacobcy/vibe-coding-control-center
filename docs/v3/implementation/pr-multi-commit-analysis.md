# Feature: PR Multi-Commit Analysis（最终方案）

## 🎯 方案选择

**采用方式2：直接分析关键文件**

### 为什么选择方式2？

| 对比 | 方式1（筛选commits） | 方式2（分析关键文件） |
|------|-------------------|-------------------|
| **性能** | ❌ 可能重复分析同一文件 | ✅ 每个文件只分析1次 |
| **逻辑** | ❌ 间接（通过commit） | ✅ 直接（文件本身） |
| **信息** | ⚠️ 需要聚合去重 | ✅ 完整直接 |
| **需求匹配** | ⚠️ 只在追溯时需要 | ✅ 符合审查需求 |

**场景举例**：
- 20个commits中，10个都改了 `config/settings.py`
- 方式1：分析10次同一个文件 → 重复
- 方式2：只分析1次 → 高效

## 📊 实现方案

### 流程

```
PR 分析
  ↓
1. 获取 PR 整体改动文件列表（快速）
  ↓
2. 筛选关键文件（critical/public-api paths）
  ↓
3. 对关键文件跑完整分析（Serena + DAG + Scoring）
  ↓
4. 输出改动函数 + 风险评估
```

### 核心逻辑

```python
# src/vibe3/commands/inspect_helpers.py

def build_pr_analysis(pr_number: int, verbose: bool = False) -> dict[str, object]:
    """分析 PR：聚焦关键文件.

    流程：
    1. 获取 PR 所有改动文件
    2. 筛选关键文件（触及 critical/public-api paths）
    3. 只对关键文件跑完整分析
    4. 输出综合报告
    """
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient

    log = logger.bind(domain="inspect", action="pr_analysis", pr_number=pr_number)
    log.info("Analyzing PR")

    # 1. 获取 PR 整体改动
    git = GitClient(github_client=GitHubClient())
    svc = SerenaService(git_client=git)

    impact = svc.analyze_changes(PRSource(pr_number=pr_number))
    all_changed_files = impact.get("changed_files", [])

    log.info(f"PR has {len(all_changed_files)} changed files")

    # 2. 筛选关键文件
    config = get_config()
    critical_paths = config.review_scope.critical_paths
    public_api_paths = config.review_scope.public_api_paths

    critical_files = []
    for file in all_changed_files:
        is_critical = any(p in str(file) for p in critical_paths)
        is_public_api = any(p in str(file) for p in public_api_paths)

        if is_critical or is_public_api:
            critical_files.append({
                "path": file,
                "critical_path": is_critical,
                "public_api": is_public_api,
            })

    log.info(
        f"Found {len(critical_files)} critical files out of {len(all_changed_files)}"
    )

    # 3. 分析关键文件（只分析1次）
    critical_symbols_by_file: dict[str, list[str]] = {}
    critical_file_dags: dict[str, list[str]] = {}

    for file_info in critical_files:
        file = file_info["path"]
        if not file.endswith(".py"):
            continue

        # 3.1 提取改动的函数（轻量级：diff hunks + AST）
        changed_funcs = svc.get_changed_functions(
            file, source=PRSource(pr_number=pr_number)
        )
        if changed_funcs:
            critical_symbols_by_file[file] = changed_funcs

        # 3.2 DAG 影响范围
        dag = dag_service.expand_impacted_modules([file])
        if dag.impacted_modules:
            critical_file_dags[file] = dag.impacted_modules

    # 4. DAG 影响范围（全部文件）
    overall_dag = dag_service.expand_impacted_modules(all_changed_files)

    # 5. 风险评分（基于整体）
    dims = PRDimensions(
        changed_files=len(all_changed_files),
        impacted_modules=len(overall_dag.impacted_modules),
        changed_lines=0,  # TODO
        critical_path_touch=len([f for f in critical_files if f["critical_path"]]) > 0,
        public_api_touch=len([f for f in critical_files if f["public_api"]]) > 0,
    )
    score = generate_score_report(dims)

    # 6. 获取 commits 信息（用于显示）
    gh = GitHubClient()
    commit_shas = gh.get_pr_commits(pr_number)

    # 获取每个commit的message
    commits_info = []
    for sha in commit_shas[:5]:  # 只显示前5个
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s", sha],
            capture_output=True,
            text=True,
            check=True,
        )
        message = result.stdout.strip()
        commits_info.append({
            "sha": sha[:7],
            "message": message,
        })

    return {
        "pr_number": pr_number,
        "total_commits": len(commit_shas),
        "total_files": len(all_changed_files),
        "critical_files": critical_files,
        "critical_symbols": critical_symbols_by_file,
        "dag": {
            "changed_files": all_changed_files,
            "impacted_modules": overall_dag.impacted_modules,
            "critical_file_dags": critical_file_dags,
        },
        "score": score,
        "recent_commits": commits_info,  # 可选：显示最近的commits
    }
```

### CLI 输出

```python
# src/vibe3/commands/inspect.py

@app.command()
def pr(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    json_out: _JSON_OPT = False,
    verbose: _VERBOSE_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Analyze PR - focus on critical files."""
    if trace:
        enable_trace()

    result = build_change_analysis("pr", str(pr_number), verbose=verbose)

    if json_out:
        typer.echo(json.dumps(result, indent=2, default=str))
        return

    # 格式化输出
    typer.echo(f"=== PR #{pr_number} Analysis ===")
    typer.echo(f"Files: {result['total_files']} | Commits: {result['total_commits']}")
    typer.echo()

    # 关键文件
    if result["critical_files"]:
        typer.echo(f"关键文件 ({len(result['critical_files'])}):")
        for file_info in result["critical_files"]:
            tags = []
            if file_info["critical_path"]:
                tags.append("critical")
            if file_info["public_api"]:
                tags.append("public-api")
            typer.echo(f"  ⚠️  {file_info['path']} ({', '.join(tags)})")
        typer.echo()

    # 改动的关键函数
    if result["critical_symbols"]:
        typer.echo("改动的关键函数:")
        for file, funcs in result["critical_symbols"].items():
            typer.echo(f"  {file}:")
            for func in funcs:
                typer.echo(f"    - {func}")
        typer.echo()

    # DAG 影响范围
    dag = result["dag"]
    typer.echo(f"影响模块 ({len(dag['impacted_modules'])}):")
    for module in dag["impacted_modules"][:5]:  # 只显示前5个
        typer.echo(f"  - {module}")
    if len(dag["impacted_modules"]) > 5:
        typer.echo(f"  ... 还有 {len(dag['impacted_modules']) - 5} 个")
    typer.echo()

    # 风险评分
    score = result["score"]
    typer.echo(f"风险评分: {score['level']} ({score['score']}/10)")
    if score["block"]:
        typer.echo("  ⚠️  建议阻止合并")

    # 可选：显示最近的commits
    if verbose and result.get("recent_commits"):
        typer.echo()
        typer.echo(f"最近的 commits:")
        for commit in result["recent_commits"]:
            typer.echo(f"  {commit['sha']} {commit['message']}")
```

## 📊 输出示例

### 基础输出

```bash
$ vibe inspect pr 42

=== PR #42 Analysis ===
Files: 15 | Commits: 8

关键文件 (3):
  ⚠️  src/vibe3/config/settings.py (critical, public-api)
  ⚠️  src/vibe3/clients/git_client.py (critical)
  ⚠️  src/vibe3/services/serena_service.py (critical)

改动的关键函数:
  src/vibe3/config/settings.py:
    - get_config
    - ConfigPaths
  src/vibe3/clients/git_client.py:
    - GitClient.__init__
    - get_diff

影响模块 (5):
  - vibe3.config
  - vibe3.clients
  - vibe3.services
  - vibe3.commands
  - vibe3.utils

风险评分: MEDIUM (6/10)
```

### 详细模式

```bash
$ vibe inspect pr 42 --verbose

=== PR #42 Analysis ===
Files: 15 | Commits: 8

关键文件 (3):
  ⚠️  src/vibe3/config/settings.py (critical, public-api)
  ⚠️  src/vibe3/clients/git_client.py (critical)
  ⚠️  src/vibe3/services/serena_service.py (critical)

改动的关键函数:
  src/vibe3/config/settings.py:
    - get_config
    - ConfigPaths
  src/vibe3/clients/git_client.py:
    - GitClient.__init__
    - get_diff

影响模块 (5):
  - vibe3.config
  - vibe3.clients
  - vibe3.services
  - vibe3.commands
  - vibe3.utils

风险评分: MEDIUM (6/10)

最近的 commits:
  3d6c66c feat: improve code path configuration
  b22f491 docs: add code path definitions
  96bce18 refactor: simplify code_limits
  ...
```

### JSON 输出

```bash
$ vibe inspect pr 42 --json
{
  "pr_number": 42,
  "total_commits": 8,
  "total_files": 15,
  "critical_files": [
    {
      "path": "src/vibe3/config/settings.py",
      "critical_path": true,
      "public_api": true
    },
    ...
  ],
  "critical_symbols": {
    "src/vibe3/config/settings.py": ["get_config", "ConfigPaths"],
    ...
  },
  "dag": {
    "changed_files": [...],
    "impacted_modules": ["vibe3.config", ...],
    "critical_file_dags": {...}
  },
  "score": {
    "score": 6,
    "level": "MEDIUM",
    "block": false,
    "breakdown": {...}
  }
}
```

## 📋 实施步骤

### Phase 1: 核心实现
- [ ] 添加 `GitHubClient.get_pr_commits()`（获取commits列表）
- [ ] 修改 `build_change_analysis()` 添加 PR 分支
- [ ] 实现 `build_pr_analysis()` 聚焦关键文件
- [ ] 更新 CLI 输出格式

### Phase 2: 测试
- [ ] 测试小 PR（3-5 files, 3-5 commits）
- [ ] 测试大 PR（20+ files, 10+ commits）
- [ ] 测试无关键文件的 PR

### Phase 3: 可选增强
- [ ] 添加 `--show-commits` 选项（追溯哪个commit改的）
- [ ] 添加进度显示（如果分析很多文件）

## 💡 核心优势

| 方面 | 优势 |
|------|------|
| **性能** | ✅ 每个文件只分析1次，不重复 |
| **逻辑** | ✅ 直接关注文件改动，不绕弯 |
| **信息** | ✅ 完整的改动信息，不遗漏 |
| **可维护** | ✅ 复用现有逻辑，简单清晰 |
| **用户体验** | ✅ 输出直观，符合审查需求 |

## 🔮 未来扩展

### 可选追溯功能

```bash
$ vibe inspect pr 42 --show-commits

config/settings.py:
  - get_config (commits: 3d6c66c, 96bce18)
  - ConfigPaths (commit: b22f491)

git_client.py:
  - GitClient.__init__ (commit: 96bce18)
```

实现方式：
```python
def trace_commits_for_file(file: str, commits: list[str]) -> dict[str, list[str]]:
    """追溯每个改动函数是由哪些commits改的."""
    # 对每个commit，检查是否改了这个函数
    ...
```

但这是**可选功能**，不是主流程。

---

**总结**：采用方式2（直接分析关键文件），性能更好，逻辑更清晰，符合用户需求。