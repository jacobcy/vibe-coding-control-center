# Test Strategy: Mock vs Real-Test Classification

本文档定义核心业务逻辑的测试策略，明确区分"必须真实测试"与"允许 mock"的边界，避免核心逻辑被 mock 覆盖导致虚假验证通过。

## 1. Mock vs Real-Test 分类矩阵

### 禁止 mock（必须真实测试）

以下逻辑必须使用真实测试，不允许 mock 核心逻辑：

#### 文件/路径解析逻辑
- `_get_git_root()` — Git 根目录查找
- 路径拼接与转换（相对路径 → 绝对路径）
- Worktree 路径解析
- 配置文件路径查找

#### Git 命令执行结果解析
- Branch 名提取（从 `git branch` 输出）
- Worktree 路径解析（从 `git worktree list` 输出）
- Remote URL 解析
- Commit SHA 提取

#### 外部工具调用的核心逻辑（非网络部分）
- 命令参数构建（如构建 `git worktree add` 命令参数）
- 命令输出解析（如解析 JSON、解析表格输出）
- 错误码映射（如 exit code → exception type）

#### 业务规则计算
- 风险评分计算（如 `calculate_risk_score()`）
- 状态判断逻辑（如 `should_trigger_flow()`）
- 优先级排序（如 `sort_by_priority()`）
- 条件分支逻辑（如 `if-else` 决策树）

#### 配置读取与默认值 fallback 链路
- 配置文件读取 + 默认值应用
- 环境变量读取 + fallback 链路
- 多层配置合并逻辑

### 允许 mock 的场景

以下场景允许使用 mock，但应明确标注：

#### 外部服务调用
- GitHub API 调用（`gh` 命令、REST API）
- 网络请求（HTTP/HTTPS）
- 第三方服务 API

#### 时间相关函数
- `datetime.now()`
- `time.time()`
- 时间格式化函数（当测试需要固定时间戳时）

#### 随机数生成
- `random.random()`
- UUID 生成（当需要确定性测试时）

#### Subprocess 调用中的外部进程执行
- 允许 mock 外部进程的执行结果
- **但进程参数构建必须真实测试**（见"禁止 mock"部分）

## 2. 测试覆盖要求

### 核心函数测试要求

每个核心函数至少满足以下测试覆盖：

#### 至少一个真实测试
- 从真实工作目录执行
- 不 mock 核心逻辑（允许 mock 外部服务/时间/随机数）
- 验证实际输出或行为

#### 不同工作目录测试
- 从 repo root 执行
- 从 subdirectory 执行（如 `src/vibe3/commands/`）
- 验证路径解析逻辑的目录无关性

#### 边界情况覆盖
- 空输入
- 异常路径（如不存在的文件、无效的 branch 名）
- None/空字符串处理
- 极端值（如超长字符串、嵌套极深的路径）

### 测试命名约定

为区分真实测试与 mock 测试，建议在测试名称中标注：

```python
# 真实测试（不 mock 核心逻辑）
def test_get_git_root_real():
    """Real test: 从真实工作目录查找 git root"""
    ...

# Mock 测试（mock 了外部服务）
def test_github_api_mocked(mocker):
    """Mock test: GitHub API 调用（mock 外部服务）"""
    ...
```

## 3. "验证通过"声明的证据要求

### 声明要求

当 executor 在执行报告中声称"验证通过"时：

#### 必须提供真实测试证据
- 引用真实测试的文件路径和测试名称
- 提供测试执行的输出片段
- 说明测试覆盖了哪些核心逻辑

#### 不能仅凭 mock 测试通过
- 如果核心逻辑只有 mock 测试，视为验证不充分
- 必须补充真实测试或明确说明为何无法真实测试

### 执行报告模板

在执行报告的 "Verification" 部分，应明确标注：

```markdown
## Verification

### Real Tests (核心逻辑真实测试)
- `tests/vibe3/path/test_file.py::test_get_git_root_real`: ✅ PASS
  - 验证：从 repo root 和 subdirectory 都能正确找到 git root
  - 输出：...

### Mock Tests (外部服务 mock 测试)
- `tests/vibe3/path/test_api.py::test_github_api_mocked`: ✅ PASS
  - Mock 范围：GitHub API 调用
  - 验证：参数构建和结果解析逻辑
```

## 4. 检查清单

### Executor 自检清单

在声称验证完成前，确认：

- [ ] 核心业务逻辑是否有真实测试（非 mock）？
- [ ] 是否从不同工作目录测试过？
- [ ] 边界情况是否覆盖？
- [ ] "验证通过"的声明是否有真实测试证据？
- [ ] 执行报告中是否明确标注了哪些是真实测试、哪些使用了 mock？

### Reviewer 检查清单

在审查执行报告时，确认：

- [ ] 核心逻辑是否有真实测试（引用本文档的分类矩阵）？
- [ ] Executor 报告中的 "验证通过" 是否有真实测试证据？
- [ ] 如果核心函数只有 mock 测试，是否视为验证证据不足？

## 5. 示例场景

### 场景 1：路径解析函数

```python
# src/vibe3/path/utils.py
def get_git_root(start_dir: Path) -> Path:
    """从 start_dir 向上查找 git root"""
    ...
```

**测试策略**：
- ✅ 真实测试：从真实 repo 的不同目录调用，验证返回正确的 git root
- ❌ Mock 测试：不应 mock `subprocess.run` 或文件系统操作
- ✅ 边界测试：从非 git 目录调用，验证抛出正确异常

### 场景 2：GitHub API 调用

```python
# src/vibe3/services/github.py
def get_issue_comments(issue_number: int) -> list[Comment]:
    """调用 GitHub API 获取 issue comments"""
    ...
```

**测试策略**：
- ✅ Mock 测试：mock `requests.get` 或 `gh` 命令，验证参数构建和结果解析
- ✅ 真实测试（可选）：使用测试 token 发送真实请求（CI 环境或手动验证）
- ❌ 不应 mock 结果解析逻辑本身

### 场景 3：风险评分计算

```python
# src/vibe3/analysis/risk.py
def calculate_risk_score(changes: list[Change]) -> int:
    """基于变更集计算风险评分"""
    ...
```

**测试策略**：
- ✅ 真实测试：使用真实的变更集数据，验证评分计算逻辑
- ❌ Mock 测试：不应 mock 计算逻辑本身
- ✅ 边界测试：空变更集、单个变更、大量变更

## 6. 反模式警示

### 反模式 1：Mock 核心逻辑

```python
# ❌ 错误：mock 了路径解析逻辑
def test_get_git_root_bad(mocker):
    mocker.patch('subprocess.run', return_value=Mock(stdout='/fake/root'))
    result = get_git_root(Path.cwd())
    assert result == Path('/fake/root')  # 只验证了 mock 生效，没验证真实逻辑
```

### 反模式 2：声称验证通过但无真实测试

```markdown
# ❌ 错误的执行报告
## Verification
- All tests pass ✅
  - tests/test_path.py: 10 passed

# 问题：没有说明哪些是真实测试，没有提供真实测试证据
```

### 反模式 3：只从单一工作目录测试

```python
# ❌ 不充分：只从 repo root 测试
def test_get_git_root_incomplete():
    result = get_git_root(Path.cwd())  # 假设 cwd 是 repo root
    assert result == Path.cwd()

# 问题：没有验证从 subdirectory 调用的行为
```

## 7. 参考链接

- 本文档被 @vibe/supervisor/policies/run.md 引用：executor 验证原则
- 本文档被 @vibe/supervisor/policies/review.md 引用：审查检查清单
