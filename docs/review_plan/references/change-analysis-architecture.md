# 改动分析架构设计

> **设计原则**：统一改动源抽象，Git Client 提供基础能力，Service 层薄编排

---

## 1. 改动源抽象

### 1.1 改动源类型

```python
from typing import Literal, Union
from pydantic import BaseModel

class PRSource(BaseModel):
    """PR 改动源"""
    type: Literal["pr"] = "pr"
    pr_number: int

class CommitSource(BaseModel):
    """Commit 改动源"""
    type: Literal["commit"] = "commit"
    sha: str

class BranchSource(BaseModel):
    """分支改动源"""
    type: Literal["branch"] = "branch"
    base_branch: str
    head_branch: str | None = None  # None 表示当前分支

class UncommittedSource(BaseModel):
    """未提交改动源"""
    type: Literal["uncommitted"] = "uncommitted"

ChangeSource = Union[PRSource, CommitSource, BranchSource, UncommittedSource]
```

### 1.2 改动分析结果

```python
class ChangeAnalysis(BaseModel):
    """改动分析结果"""
    source: ChangeSource
    changed_files: list[str]
    diff: str
    impact: dict | None = None  # Serena 分析结果
    dag: dict | None = None     # DAG 分析结果
    score: dict | None = None   # 风险评分
```

---

## 2. Git Client 扩展

**位置**: `clients/git_client.py`

### 2.1 核心接口

```python
class GitClient:
    """Git client for interacting with git repository."""

    # 现有方法
    def get_current_branch(self) -> str: ...
    def get_worktree_name(self) -> str: ...

    # 新增：改动文件获取
    def get_changed_files(self, source: ChangeSource) -> list[str]:
        """获取改动文件列表（统一接口）

        Args:
            source: 改动源（PR/Commit/Branch/Uncommitted）

        Returns:
            改动文件路径列表
        """
        if isinstance(source, PRSource):
            return self._get_pr_files(source.pr_number)
        elif isinstance(source, CommitSource):
            return self._get_commit_files(source.sha)
        elif isinstance(source, BranchSource):
            return self._get_branch_files(source.base_branch, source.head_branch)
        elif isinstance(source, UncommittedSource):
            return self._get_uncommitted_files()
        else:
            raise ValueError(f"Unknown source type: {source}")

    # 新增：diff 获取
    def get_diff(self, source: ChangeSource) -> str:
        """获取 diff 输出（统一接口）

        Args:
            source: 改动源

        Returns:
            git diff 输出
        """
        if isinstance(source, PRSource):
            return self._get_pr_diff(source.pr_number)
        elif isinstance(source, CommitSource):
            return self._get_commit_diff(source.sha)
        elif isinstance(source, BranchSource):
            return self._get_branch_diff(source.base_branch, source.head_branch)
        elif isinstance(source, UncommittedSource):
            return self._get_uncommitted_diff()
        else:
            raise ValueError(f"Unknown source type: {source}")

    # 内部实现（私有方法）
    def _get_pr_files(self, pr_number: int) -> list[str]: ...
    def _get_commit_files(self, sha: str) -> list[str]: ...
    def _get_branch_files(self, base: str, head: str | None) -> list[str]: ...
    def _get_uncommitted_files(self) -> list[str]: ...
```

### 2.2 实现示例

```python
def _get_pr_files(self, pr_number: int) -> list[str]:
    """获取 PR 改动文件列表"""
    result = subprocess.run(
        ["gh", "pr", "diff", str(pr_number), "--name-only"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip().split("\n")

def _get_commit_files(self, sha: str) -> list[str]:
    """获取 commit 改动文件列表"""
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip().split("\n")

def _get_branch_files(self, base: str, head: str | None = None) -> list[str]:
    """获取分支改动文件列表"""
    head = head or "HEAD"
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip().split("\n")

def _get_uncommitted_files(self) -> list[str]:
    """获取未提交改动文件列表"""
    result = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip().split("\n")
```

---

## 3. Serena Service 扩展

**位置**: `services/serena_service.py`

### 3.1 统一分析接口

```python
class SerenaService:
    """Service for analyzing code symbols using Serena."""

    def __init__(self, client: SerenaClient | None = None, git: GitClient | None = None) -> None:
        self.client = client or SerenaClient()
        self.git = git or GitClient()

    # 现有方法
    def analyze_file(self, relative_file: str) -> dict: ...
    def analyze_files(self, files: list[str]) -> dict: ...

    # 新增：统一改动分析
    def analyze_changes(self, source: ChangeSource) -> dict:
        """分析改动符号（统一接口）

        Args:
            source: 改动源

        Returns:
            符号分析结果（impact.json 格式）
        """
        logger.info("Analyzing changes", source_type=source.type)

        # 1. 获取改动文件
        files = self.git.get_changed_files(source)

        # 2. 分析符号
        return self.analyze_files(files)
```

---

## 4. 命令层编排

**位置**: `commands/inspect.py`

### 4.1 实现示例

```python
import typer
from vibe3.clients.git_client import GitClient, PRSource, CommitSource, BranchSource, UncommittedSource
from vibe3.services.serena_service import SerenaService
from vibe3.services.dag_service import DAGService
from vibe3.services.pr_scoring_service import PRScoringService

app = typer.Typer()
git = GitClient()
serena = SerenaService(git=git)
dag = DAGService()
scoring = PRScoringService()

@app.command()
def pr(pr_number: int, json_output: bool = False):
    """PR 改动分析"""
    source = PRSource(pr_number=pr_number)
    _analyze_and_output(source, json_output)

@app.command()
def commit(sha: str, json_output: bool = False):
    """Commit 改动分析"""
    source = CommitSource(sha=sha)
    _analyze_and_output(source, json_output)

@app.command()
def base(branch: str, json_output: bool = False):
    """相对分支的改动分析"""
    source = BranchSource(base_branch=branch)
    _analyze_and_output(source, json_output)

@app.command("uncommitted")
def inspect_uncommitted(json_output: bool = False):
    """未提交改动分析"""
    source = UncommittedSource()
    _analyze_and_output(source, json_output)

def _analyze_and_output(source: ChangeSource, json_output: bool):
    """统一分析流程"""
    # 1. 符号分析
    impact = serena.analyze_changes(source)

    # 2. DAG 分析
    dag_result = dag.expand_impact(impact)

    # 3. 风险评分
    score = scoring.calculate_score(impact, dag_result)

    # 输出
    result = {
        "source": source.model_dump(),
        "impact": impact,
        "dag": dag_result,
        "score": score
    }

    if json_output:
        typer.echo(json.dumps(result, indent=2))
    else:
        _pretty_print(result)
```

---

## 5. 架构优势

### 5.1 统一抽象
- ✅ 四种改动源统一为 `ChangeSource` 类型
- ✅ Git Client 提供统一接口 `get_changed_files(source)`
- ✅ Serena Service 提供统一接口 `analyze_changes(source)`

### 5.2 职责清晰
- **Git Client**: 封装 git 操作，提供改动数据
- **Serena Service**: 符号分析，输出结构化数据
- **Command 层**: 编排流程，处理输出

### 5.3 易于扩展
- ✅ 新增改动源只需：
  1. 定义新的 Source 类型
  2. 在 Git Client 添加对应实现
- ✅ 符合开闭原则

---

## 6. 实施任务

### Phase 1 扩展

#### 6.1 Git Client 扩展
- [ ] 创建 `models/change_source.py`
  - 定义 `ChangeSource` 类型
  - 定义 `PRSource`, `CommitSource`, `BranchSource`, `UncommittedSource`
- [ ] 扩展 `clients/git_client.py`
  - `get_changed_files(source)` - 统一接口
  - `get_diff(source)` - 统一接口
  - `_get_pr_files()`, `_get_commit_files()` 等私有实现

#### 6.2 Serena Service 扩展
- [ ] 扩展 `services/serena_service.py`
  - `analyze_changes(source)` - 统一改动分析接口

#### 6.3 测试
- [ ] 编写测试覆盖四种改动源
- [ ] Mock git 命令输出

---

## 7. 与 Phase 2 衔接

Phase 2 的 `vibe inspect` 和 `vibe review` 命令可以直接使用此架构：

```bash
# Phase 2 实现
vibe inspect pr 42
  → inspect.pr(42)
  → source = PRSource(42)
  → serena.analyze_changes(source)

vibe review pr 42
  → 内部调用 vibe inspect pr 42
  → 获取上下文 → Codex review
```

**无缝衔接**：Phase 1 提供基础设施，Phase 2 直接编排使用。