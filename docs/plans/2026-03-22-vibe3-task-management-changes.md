# Vibe3 Task 管理修改计划

**创建时间**: 2026-03-22
**最后更新**: 2026-03-22
**目的**: 记录具体的修改点、代码改动和实施步骤

---

## 零、已完成的工作（2026-03-22）

### 0.1 概念统一

**已完成**:
- ✅ 更新核心文档（glossary, issue-standard, github-labels-standard）
- ✅ 更新命令参数（`--task-issue` / `--repo-issue` / `TASK_ID` / `ISSUE_URL` → `issue`）
- ✅ 更新输出文本（`repo_issues` → `related_issues` + `dependencies`）
- ✅ 更新用户指南（vibe3-user-guide.md）
- ✅ 明确命令语义（flow show vs task show）
- ✅ 兼容旧数据语义（`repo` → `related`）

**验证**: 见 [docs/plans/2026-03-22-doc-cleanup-summary.md](2026-03-22-doc-cleanup-summary.md)

---

## 一、核心目标

本次修改解决两个核心问题：

### 1.1 统一混乱的命名方式

**问题**：当前代码中 issue 相关参数命名混乱，存在歧义和误用：

| 命令 | 参数名 | 类型 | 存储内容 |
|------|--------|------|----------|
| `flow new` | `task_issue` | `int \| None` | issue number |
| `flow bind` | `task_id` | `str` (解析后 int) | issue number |
| 数据库字段 | `task_issue_number` | `int` | issue number |

**解决方案**：统一使用 `issue` 作为参数名
- `flow new --task-issue` → `flow new --issue`
- `flow bind <task_id>` → `flow bind <issue>`
- 参数类型统一为 `str`（支持数字或 URL），内部解析为 `int`

**理由**：
1. 所有参数都指向同一个概念：GitHub issue number
2. 统一命名避免混淆，减少认知负担
3. 符合标准文档定义

### 1.2 Issue 角色语义转变

**从分类视图转为关系视图**：

| 原设计 | 新设计 | 语义变化 |
|--------|--------|----------|
| `role = "task"` | `role = "task"` | Flow 的主要执行目标（不变） |
| `role = "repo"` | `role = "related"` | ❌ "repo" 是分类视角<br>✅ "related" 是关系视角 |
| - | `role = "dependency"` | 新增：依赖的其他 task |

**语义转变**：
- **旧语义**：`repo` = "需求来源 issue"，`task` = "执行 issue"（分类视角）
- **新语义**：`related` = "相关 issue"，`dependency` = "依赖 issue"（关系视角）
- **关键区别**：
  - 分类视角：issue 有类型属性（是 repo issue 还是 task issue）
  - 关系视角：issue 在 flow 中有角色（相对于 flow 的关系）

**影响**：
- `task link --role repo` → `task link --role related`
- 默认 role 从 `"repo"` 改为 `"related"`
- 数据库 `flow_issue_links.issue_role` 字段值更新
- GitHub label 同步规则更新（related 不添加标签，task/dependency 添加 vibe-task）

**重要区别**：
- **flow bind**: Issue → Flow 关系（存 SQLite）
  - 支持 `task/related/dependency` 三种 role
  - 绑定 issue 到 flow，指定其在 flow 中的角色

- **task link**: 当前 flow 的补充关系入口（当前存 SQLite）
  - 只支持 `related/dependency` 两种 role
  - **不支持 `--role task`**
  - 后续标签自动化必须复用同一套 role 语义

---

## 二、待实施修改

### 2.1 flow 命令参数修改（P1 - 必需）

#### 修改点 1: flow new - name 参数

**文件**: `src/vibe3/commands/flow.py`

**当前代码**:
```python
def new(
    name: Annotated[str, typer.Argument(help="Flow name")],  # ❌ 必需参数
    task_issue: Annotated[
        int | None, typer.Option("--task-issue", help="Task issue number to bind")
    ] = None,
    ...
) -> None:
```

**目标代码**:
```python
def new(
    name: Annotated[str | None, typer.Argument(help="Flow name (default: branch name without prefix)")] = None,
    issue: Annotated[
        int | None, typer.Option("--issue", help="Issue number to bind as task")
    ] = None,
    ...
) -> None:
```

**修改内容**:
- **name 参数**：
  - 类型: `str` → `str | None`
  - 默认值: 无 → `None`
  - 帮助文本: "Flow name" → "Flow name (default: branch name without prefix)"
- **issue 参数**：
  - 参数名: `task_issue` → `issue`
  - Option: `--task-issue` → `--issue`
  - 帮助文本: "Task issue number to bind" → "Issue number to bind as task"
  - 变量引用: 全部更新

**语义**:
- `name` 可选，不提供时从 `branch` 自动生成 `flow_slug`
- 例如：`branch = "task/my-feature"` → `flow_slug = "my-feature"`

---

#### 修改点 2: flow show - 参数名修正

**文件**: `src/vibe3/commands/flow.py`

**当前代码**:
```python
def show(
    flow_name: Annotated[str | None, typer.Argument(help="Flow to show")] = None,
    ...
) -> None:
    branch = flow_name if flow_name else git.get_current_branch()
```

**目标代码**:
```python
def show(
    branch: Annotated[str | None, typer.Argument(help="Branch name")] = None,
    ...
) -> None:
    branch = branch if branch else git.get_current_branch()
```

**修改内容**:
- 参数名: `flow_name` → `branch`
- 帮助文本: "Flow to show" → "Branch name"
- 变量引用: 直接使用 `branch` 参数

**语义**: 参数是 branch name（指针），不是 flow_slug（显示名称）

---

#### 修改点 3: flow bind - 统一命名 + 支持 role 参数

**文件**: `src/vibe3/commands/flow.py`

**当前代码**:
```python
def bind(
    task_id: Annotated[str, typer.Argument(help="Task issue number or URL")],
    ...
) -> None:
    from vibe3.commands.task import parse_issue_url
    issue_number = parse_issue_url(task_id)
    task_service.link_issue(branch, issue_number, role="task", actor=actor)  # 硬编码 role="task"
```

**目标代码**:
```python
def bind(
    issue: Annotated[str, typer.Argument(help="Issue number (or URL)")],
    role: Annotated[
        Literal["task", "related", "dependency"],
        typer.Option(help="Issue role in flow")
    ] = "task",  # 新增 --role 参数
    ...
) -> None:
    from vibe3.commands.task import parse_issue_ref
    issue_number = parse_issue_ref(issue)
    task_service.link_issue(branch, issue_number, role=role, actor=actor)  # 使用参数
```

**修改内容**:
- 参数名: `task_id` → `issue`（统一命名）
- 帮助文本: "Task issue number or URL" → "Issue number (or URL)"
- 函数调用: `parse_issue_url` → `parse_issue_ref`
- **新增**: `--role` 参数，支持 `task/related/dependency`，默认 `"task"`
- 调用服务层: 传递 role 参数

**语义**: 绑定 issue 到 flow，指定其在 flow 中的角色

---

### 2.2 task 命令参数修改（P1 - 必需）

#### 修改点 4: task link - 统一命名 + Role 语义转变

**文件**: `src/vibe3/commands/task.py`

**当前代码**:
```python
def parse_issue_url(issue_url: str) -> int:
    """Parse issue number from GitHub URL or plain number."""
    if issue_url.isdigit():
        return int(issue_url)
    match = re.search(r"github\.com/[^/]+/[^/]+/issues/(\d+)", issue_url)
    if match:
        return int(match.group(1))
    raise ValueError(f"Invalid issue URL or number: {issue_url}")

@app.command()
def link(
    issue_url: Annotated[str, typer.Argument(help="Issue URL or number")],
    role: Annotated[Literal["task", "repo"], typer.Option(help="Issue role")] = "repo",
    ...
) -> None:
    issue_number = parse_issue_url(issue_url)
```

**目标代码**:
```python
def parse_issue_ref(issue_ref: str) -> int:
    """Parse issue number from reference (number or GitHub URL)."""
    if issue_ref.isdigit():
        return int(issue_ref)
    match = re.search(r"github\.com/[^/]+/[^/]+/issues/(\d+)", issue_ref)
    if match:
        return int(match.group(1))
    raise ValueError(f"Invalid issue reference: {issue_ref}")

@app.command()
def link(
    issue: Annotated[str, typer.Argument(help="Issue number (or URL)")],
    role: Annotated[Literal["task", "related", "dependency"], typer.Option(help="Issue role")] = "related",
    ...
) -> None:
    issue_number = parse_issue_ref(issue)
```

**修改内容**:
- **函数重命名**：
  - 函数名: `parse_issue_url` → `parse_issue_ref`
  - 函数参数: `issue_url` → `issue_ref`
  - 帮助文本: 更新描述

- **命令参数统一命名**：
  - 参数名: `issue_url` → `issue`
  - 帮助文本: "Issue URL or number" → "Issue number (or URL)"

- **Role 语义转变（核心修改）**：
  - Role 类型: `Literal["task", "repo"]` → `Literal["related", "dependency"]`
  - Role 默认值: `"repo"` → `"related"`
  - **语义变化**：
    - ❌ 旧语义：`repo` = "需求来源 issue"（分类视角）
    - ✅ 新语义：`related` = "相关 issue"，`dependency` = "依赖 issue"（关系视角）
  - **关键区别**：
    - `task link` 当前为当前 flow 记录补充 issue 关系（存 SQLite）
    - 只支持 `related` 和 `dependency`，不支持 `task`
    - GitHub label / body 自动化属于后续工作

---

### 2.3 服务层修改（P1 - 必需）

#### 修改点 5: TaskService.link_issue

**文件**: `src/vibe3/services/task_service.py`

**当前代码**:
```python
def link_issue(
    self,
    branch: str,
    issue_number: int,
    role: Literal["task", "repo"] = "repo",  # ❌ 旧语义
    actor: str = "unknown",
) -> IssueLink:
```

**目标代码**:
```python
def link_issue(
    self,
    branch: str,
    issue_number: int,
    role: Literal["task", "related", "dependency"] = "related",  # ✅ 新语义
    actor: str = "unknown",
) -> IssueLink:
```

**修改内容**:
- Role 类型: `Literal["task", "repo"]` → `Literal["task", "related", "dependency"]`
- Role 默认值: `"repo"` → `"related"`
- 所有调用处检查并更新

**调用场景区分**:
- `flow bind`: 调用 `link_issue(branch, issue, role="task")` — Issue → Flow 关系
- `task link`: 调用 `link_issue(branch, issue, role="related/dependency")` — Issue → Issue 关系
- 服务层支持三种 role，但不同命令使用不同子集

---

### 2.4 输出文本修改（✅ 已完成）

输出文本已更新：`repo_issues` → `related_issues` + `dependencies`。详细变更见 git commit 记录。

---

## 三、实施步骤

### Step 1: 修改 task.py（统一命名 + Role 语义转变）

**文件**: `src/vibe3/commands/task.py`

**修改内容**:
```bash
1. 重命名函数 parse_issue_url → parse_issue_ref
2. 更新函数参数: issue_url → issue_ref
3. 修改 link 命令参数: issue_url → issue
4. 更新 role 类型: Literal["task", "repo"] → Literal["task", "related", "dependency"]
5. 修改默认 role: "repo" → "related"
```

**验证**:
```bash
# 测试解析函数
uv run python -c "
from vibe3.commands.task import parse_issue_ref
assert parse_issue_ref('219') == 219
assert parse_issue_ref('https://github.com/owner/repo/issues/219') == 219
"

# 测试命令（新语义）
vibe3 task link 219 --role related      # ✅ 新语义：相关 issue
vibe3 task link 218 --role dependency   # ✅ 新语义：依赖 issue
vibe3 task link 219                     # ✅ 默认 role = "related"
vibe3 task link 219 --role task         # ❌ 应该报错：不支持 --role task
```

---

### Step 2: 修改 flow.py（统一命名 + name 参数可选）

**文件**: `src/vibe3/commands/flow.py`

**修改内容**:
```bash
1. 修改 new 命令:
   - name 参数: str → str | None，添加默认值 None
   - issue 参数: task_issue → issue, --task-issue → --issue

2. 修改 show 命令参数: flow_name → branch

3. 修改 bind 命令:
   - 参数: task_id → issue
   - 新增: --role 参数，支持 task/related/dependency，默认 "task"

4. 导入 parse_issue_ref（替换 parse_issue_url）
```

**验证**:
```bash
# 测试 flow new（name 可选）
vibe3 flow new --issue 220              # name 从 branch 自动生成
vibe3 flow new my-feature --issue 220   # 自定义 name

# 测试 flow show
vibe3 flow show task/my-feature
vibe3 flow show  # 默认当前分支

# 测试 flow bind（支持 role）
vibe3 flow bind 220                     # 默认 role=task
vibe3 flow bind 219 --role related      # 绑定为 related
vibe3 flow bind 218 --role dependency   # 绑定为 dependency
```

---

### Step 3: 修改服务层代码

**文件**: `src/vibe3/services/task_service.py`

**修改内容**:
```bash
1. 更新 link_issue 方法签名：
   - role 类型: Literal["task", "repo"] → Literal["task", "related", "dependency"]
   - role 默认值: "repo" → "related"

2. 检查所有调用 link_issue 的地方，确认参数正确
```

**验证**:
```bash
# 检查服务层
uv run python -c "
from vibe3.services.task_service import TaskService
service = TaskService()
# 测试 role 类型检查
service.link_issue('test-branch', 219, role='related')  # 应该通过
service.link_issue('test-branch', 218, role='dependency')  # 应该通过
"
```

---

### Step 4: 更新文档

**文件**: `docs/standards/vibe3-user-guide.md`

**修改内容**:
```bash
# 检查并更新命令示例
1. flow new --task-issue → flow new --issue
2. flow new <name> → flow new [<name>]（说明 name 可选）
3. flow show [flow_name] → flow show [branch]
4. flow bind <task_id> → flow bind <issue>
5. task link <issue_url> → task link <issue>
6. task link --role repo → task link --role related（语义转变）
7. 增加 dependency role 使用示例
```

---

### Step 5: 全局搜索和验证

```bash
# 搜索旧命名
grep -r "task_issue" src/vibe3/
grep -r "flow_name" src/vibe3/
grep -r "task_id" src/vibe3/commands/flow.py
grep -r "issue_url" src/vibe3/commands/task.py
grep -r "parse_issue_url" src/vibe3/

# 确保全部替换
```

---

## 四、影响范围

### 4.1 代码文件

| 文件 | 修改点 | 影响 |
|------|--------|------|
| `src/vibe3/commands/task.py` | `parse_issue_ref` 函数，`link` 命令 | 参数命名 + role 语义（只支持 related/dependency） |
| `src/vibe3/commands/flow.py` | `new`, `show`, `bind` 命令 | 参数命名 + name 可选 + bind 支持 role |
| `src/vibe3/services/task_service.py` | `link_issue` 方法 | role 类型定义（支持 task/related/dependency） |

### 4.2 文档文件

| 文件 | 修改点 |
|------|--------|
| `docs/standards/vibe3-command-standard.md` | ✅ 已更新（task link role 定义） |
| `docs/standards/vibe3-user-guide.md` | 命令示例 + role 语义说明 |

### 4.3 用户影响

**向后兼容性**:
- ⚠️ **破坏性变更**：`task link --role repo` 不再支持，需要改为 `--role related`
- ✅ `--issue` 是新参数，不影响旧用法（旧参数 `--task-issue` 会被移除）
- ✅ `parse_issue_ref` 仍然支持数字和 URL（功能不变）
- ✅ 用户使用方式基本不变（参数位置相同）

**影响**:
- ⚠️ `flow new --task-issue` 需要改为 `--issue`
- ⚠️ 帮助文本更新，需要重新阅读

---

## 五、风险评估

### 5.1 功能风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 参数名改变导致脚本失效 | 中 | 提供迁移文档 |
| 解析函数改名导致导入错误 | 低 | 全局搜索替换 |
| Role 语义转变导致误用 | **高** | 详细文档说明 + 示例 |
| 数据库中旧 role 值处理 | 中 | 提供迁移脚本（`repo` → `related`） |
| 测试覆盖不足 | 中 | 手动测试所有命令 |

### 5.2 用户影响

| 影响 | 程度 | 应对 |
|------|------|------|
| 需要学习新参数名 | 低 | 更新文档 |
| 需要理解 role 语义转变 | **中** | 提供对比说明文档 |
| 旧脚本需要修改 | 中 | 提供迁移指南 |
| `--role repo` 不再支持 | **高** | 明确错误提示 + 迁移指引 |

---

## 七、验证清单

### 7.1 功能验证

```bash
# task link（验证 role 语义转变）
vibe3 task link 219 --role related       # ✅ 新语义：相关 issue
vibe3 task link 218 --role dependency    # ✅ 新语义：依赖 issue
vibe3 task link 219                      # ✅ 默认 role = "related"
vibe3 task link 219 --role task          # ❌ 应该报错：不支持的 role
vibe3 task link 219 --role repo          # ❌ 应该报错：不支持的 role

# flow bind（验证 Issue → Flow 关系）
vibe3 flow bind 220                      # ✅ 绑定为 task issue
vibe3 flow bind 219 --role related       # ✅ 绑定为 related issue
vibe3 flow bind 218 --role dependency    # ✅ 绑定为 dependency issue

# flow new（验证 name 可选 + issue 参数）
vibe3 flow new --issue 220               # ✅ name 从 branch 自动生成
vibe3 flow new my-feature --issue 220    # ✅ 自定义 name
vibe3 flow new my-feature                # ✅ 不绑定 issue

# flow show（验证 branch 参数）
vibe3 flow show                          # ✅ 默认当前分支
vibe3 flow show task/my-feature          # ✅ 指定分支
```

### 7.2 数据迁移验证

```bash
# 检查数据库中的旧 role 值
sqlite3 .git/vibe3/handoff.db "SELECT DISTINCT issue_role FROM flow_issue_links;"

# 如果有 "repo" 值，需要迁移
# 迁移脚本：UPDATE flow_issue_links SET issue_role = 'related' WHERE issue_role = 'repo';
```

### 7.3 文档验证

```bash
# 检查文档中的命令示例
grep -r "flow new" docs/
grep -r "flow show" docs/
grep -r "flow bind" docs/
grep -r "task link" docs/
```

---

## 八、回滚计划

如果发现问题，可以快速回滚：

```bash
# 回滚代码
git checkout HEAD -- src/vibe3/commands/task.py
git checkout HEAD -- src/vibe3/commands/flow.py
git checkout HEAD -- src/vibe3/services/task_service.py

# 回滚文档
git checkout HEAD -- docs/standards/vibe3-user-guide.md

# 回滚数据库（如果已迁移）
sqlite3 .git/vibe3/handoff.db "UPDATE flow_issue_links SET issue_role = 'repo' WHERE issue_role = 'related';"
```

---

## 九、后续工作

### 9.1 可选优化（P2）

**优化 task list 显示**:
- 添加 `--tree` 模式
- 添加 `--by-related` 分组

### 9.2 不建议实施

- ❌ 封装 `gh issue create`
- ❌ 实现 `flow promote` 命令

---

## 十、决策记录

### 10.1 为什么统一使用 `issue` 参数名？

**决策**: 所有命令统一使用 `issue` 作为参数名

**理由**:
1. 所有参数都指向同一个概念：GitHub issue number
2. 消除命名混乱（`task_issue` vs `task_id`）
3. 减少认知负担，降低误用
4. 符合标准文档定义

### 10.2 为什么从 `repo` 改为 `related`？

**决策**: Role 从 `task/repo` 改为 `task/related/dependency`

**理由**:
1. **语义转变**：从分类视角转为关系视角
   - ❌ `repo` = "需求来源 issue"（分类视角，有歧义）
   - ✅ `related` = "相关 issue"（关系视角，清晰）
2. **关系视图更准确**：
   - Issue 在 flow 中有角色（相对于 flow 的关系）
   - 不是 issue 的类型属性
3. **扩展性更好**：
   - 支持更多关系类型（如 `dependency`）
   - 未来可以继续扩展

### 10.3 为什么保留 URL 解析？

**决策**: 保留 `parse_issue_ref` 支持 URL 解析

**理由**:
1. 用户经常从浏览器复制 issue URL
2. 不违反项目原则（只是解析，不是跨 repo 操作）
3. 提供用户便利

### 10.4 为什么参数叫 issue 而不是 issue_number？

**决策**: 参数类型是 `str`，叫 `issue`

**理由**:
1. 支持两种格式（数字和 URL）
2. 更简洁（`issue` vs `issue_number`）
3. 符合常见用法

### 10.5 为什么 flow new 的 name 参数改为可选？

**决策**: `name` 参数可选，默认从 branch 生成

**理由**:
1. 减少重复输入（branch name 通常已包含足够信息）
2. 符合实际使用场景：用户通常不关心 flow_slug
3. 保留灵活性：需要自定义时仍可提供

### 10.6 为什么 task link 不支持 --role task？

**决策**: `task link` 只支持 `related` 和 `dependency`，不支持 `task`

**理由**:
1. **语义正确性**：
   - `task link` 是 **Issue → Issue** 关系（存 GitHub）
   - 一个 issue 不能把另一个 issue 作为 task
   - Task 是 flow 的属性，不是 issue 之间的关系

2. **职责分离**：
   - `flow bind`: Issue → Flow 关系，支持 `task/related/dependency`
   - `task link`: Issue → Issue 关系，只支持 `related/dependency`

3. **避免混淆**：
   - 明确区分两种不同的关系
   - 防止用户误用

---

**文档状态**: 本文档已完整记录核心目标、实施步骤和决策记录。
