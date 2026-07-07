# Vibe Center 错误处理规范

> **文档定位**：定义系统错误处理策略，区分系统错误与业务错误
> **适用范围**：所有 Python 代码（v3）和 Agent 决策逻辑
> **基线**：`.specify/specs/010-exception-model/spec.md`（#3307 RFC 方向 C）

> **边界说明**：本文档定义**异常分类模型**（class taxonomy + recoverability）。
> Orchestra 运行时的 `CRITICAL / ERROR / WARNING`、`failed_gate`、`blocked` 语义，
> 以及 error code → severity → FailedGate 的运行时映射，由
> [error-severity-and-blocking-standard.md](./v3/error-severity-and-blocking-standard.md)
> 和 `ErrorHandlingContract`（`src/vibe3/exceptions/`）定义。两者是**正交维度**（见 §一）。

---

## 一、正交双轴模型（Canonical Model）

本系统错误处理由**两个独立维度**组成。任一异常在两个轴上各有归属，互不决定：

### Axis A — 类层级（Class Taxonomy）：这是什么类型的故障

- 根类 `VibeError(Exception)`，签名为 `(message, recoverable)`
- `UserError(VibeError)`：用户可操作的恢复（换分支、修 manifest、停 session）
- `SystemError(VibeError)`：系统/编程故障（git 输出异常、拓扑无法解析、契约违反）
- `recoverable` 布尔元数据描述"是否可恢复"，**不**决定绕过语义

类层级归**本标准**拥有（见 §二）。

### Axis B — 运行时严重度与门禁（Severity / Gate）：运行时如何处置

- `ErrorHandlingContract`（`exceptions/error_severity.py`、`error_classification.py`、`error_codes.py`）把 error code 映射到 severity（CRITICAL/ERROR/WARNING）、阈值、日志级别、issue 动作、FailedGate 动作
- `git_error_patterns.py` 只识别重试安全的瞬时子串，**不做** taxonomy 映射

严重度/门禁归 `ErrorHandlingContract` + [error-severity-and-blocking-standard.md](./v3/error-severity-and-blocking-standard.md) 拥有。

### 为什么正交

一个 `UserError` 可以对应 warning 级 severity（不阻断），一个 `SystemError` 可以对应 CRITICAL（FailedGate）。类层级回答"谁的错"，严重度回答"运行时怎么处置"。把两者硬绑会导致：批量场景被迫造一个 `BatchError` 类来同时表达"这是批量"和"运行时降级"，而批量本质是**控制流**，不是异常层级。

> **术语说明**：本文件不再用 `Tier 1/2/3` 描述错误分类（避免与 [glossary.md](./glossary.md) §3 架构分层混淆）。错误分类以 `UserError` / `SystemError` 名之。

---

## 二、类层级（Axis A）

### SystemError（系统错误）🔴

**定义**：系统基础设施故障或编程契约违反，影响功能正确性

**特征**：
- 代码依赖缺失或损坏（如 Serena 不可用）
- 外部服务故障（如 GitHub API 失败）
- 配置文件损坏或格式错误
- 类型错误、空指针等编程错误
- 内部契约违反（如向本地存储写 truth 字段）

**处理原则**：
- ✅ 立即抛出，Fail-fast
- ✅ 不捕获、不降级、不返回错误字典
- ✅ 记录完整错误栈

```python
# ✅ 系统错误立即抛出
def analyze_file(self, file: str) -> dict:
    overview = self.client.get_symbols_overview(file)  # SerenaError 向上传播
    return {"symbols": overview}

# ❌ 禁止：捕获后返回错误字典（静默失败）
def analyze_file(self, file: str) -> dict:
    try:
        overview = self.client.get_symbols_overview(file)
        return {"status": "ok", "symbols": overview}
    except SerenaError as e:
        return {"status": "error", "error": str(e)}
```

### UserError（业务错误）🟡

**定义**：用户操作不符合规范，但系统仍可正常运行；用户可采取行动恢复

**特征**：
- 输入不符合格式要求（如 commit message 缺少前缀）
- 业务规则校验失败（如覆盖率不足）
- 在受保护分支上创建 flow（换分支即可）

**处理原则**：
- ✅ 返回详细的错误提示
- ✅ `recoverable=True`
- ✅ 记录到日志（warning 级别）
- ⚠️ **绕过（`-y`/`--yes`）由 command 拥有，不由 UserError 隐含**（见 §六 Q2）

```python
# ✅ UserError 抛出，command 决定是否提供 --yes 绕过
def validate_commit_message(msg: str) -> None:
    if not msg.startswith(("feat:", "fix:", "refactor:")):
        raise UserError("Commit message must start with feat/fix/refactor")

# command 层
def commit_cmd(message: str, yes: bool = False) -> None:
    try:
        validate_commit_message(message)
    except UserError as e:
        if not yes:
            raise Exit(1)  # 提示用户
        console.print(f"[yellow]⚠️  {e.message} (--yes)[/]")
```

---

## 三、批量续跑（Pattern，非异常类）

**批量场景不是异常层级，是控制流模式。** 旧标准的 `BatchError` 类已**移除**——代码中从无此类的真实用例（#3307 深挖确认 8 个游离异常无一具批量语义）。

批量续跑的正确实现：在 command/service 层收集错误，继续执行独立任务，结束后统一报告并抛 `SystemError`（或按需 `Exit`）。

```python
# ✅ 批量续跑模式：收集 → 继续 → 统一报告
def analyze_files(self, files: list[str]) -> dict:
    results, errors = [], []
    for file in files:
        try:
            results.append(self.analyze_file(file))
        except SerenaError as e:  # SystemError 子类
            errors.append({"file": file, "error": str(e)})
            # 继续其他文件

    if errors:
        logger.error(f"Failed to analyze {len(errors)}/{len(files)} files")
        raise SystemError(f"Batch analysis failed: {len(errors)} errors")  # 复用 SystemError

    return {"results": results}
```

> **为什么不造 `BatchError` 类**：批量聚合是"如何收集并报告多个失败"的协议，与"单个失败的类型"是不同维度。强行造类会让"批量里的某个 SystemError"失去类型归属，破坏 Axis A 的分类价值。

---

## 四、已登记的游离异常（Documented Exceptions）

以下异常因诊断价值或历史原因**不继承 `VibeError`**，作为**文档化例外**保留现状。新增游离异常必须在此表登记并写明理由（迁移成本收益不划算时）。

| 类 | 现基类 | 语义归属（若迁移） | 模块 | 保留理由 |
|---|---|---|---|---|
| `ReviewKernelConfigError` | ValueError | UserError | analysis | manifest 无效，本地诊断，被 `review_observation` 显式 except 转换 |
| `GitMetadataParseError` | ValueError | SystemError | analysis | git 输出异常，ValueError 语义贴近"解析失败" |
| `RepositoryLayoutError` | RuntimeError | SystemError | utils | worktree 拓扑故障，经 `utils/__init__` 公开导出 |
| `TruthFieldWriteError` | Exception | SystemError | models | 编程契约守卫（禁止写 truth 字段） |
| `MainBranchProtectedError` | Exception | UserError | models | 受保护分支建 flow，经 `models/__init__` 导出，command 已 except |
| `CommandAdapterError` | Exception | SystemError | execution | adapter 注册冲突，内部 |
| `ResourceRootNotFoundError` | RuntimeError | SystemError | adapters | 资源根解析失败，内部（adapters README 标注未重导出） |
| `LiveSessionsDetectedError` | RuntimeError | UserError | services/flow | cleanup 竞态守卫，`pr_service` 已 except |

**迁移边界**：上述 8 类**暂不迁移**（#3307 选 C）。若未来某类需要跨层统一处理（如 CLI 要统一 catch UserError 做提示），再单独立 issue 迁移该类，并从本表移除。

---

## 五、CLI 层错误处理

CLI 层捕获 `VibeError` 子类，按 Axis A 类型分流；severity/gate 处置走 Axis B。

```python
# src/vibe3/cli.py
def main() -> None:
    try:
        app()
    except SystemError as e:
        logger.exception(f"System error: {e}")
        console.print(f"\n[red]System error: {e.message}[/]")
        sys.exit(99)
    except UserError as e:
        logger.warning(f"User error: {e}")
        console.print(f"\n[yellow]{e.message}[/]")
        sys.exit(1)
```

> 游离异常（§四）不被 CLI 的 `VibeError` catch 兜住，各自在 command 层显式处理或按其基类（ValueError/RuntimeError）上浮。这是已接受的边界。

---

## 六、RFC #3307 四问答复

**Q1：`BatchError` 是共享 runtime 契约，还是仅 agent/coding 模式？**
→ **模式**。已从标准移除为类。批量续跑是 command/service 层控制流（§三）。

**Q2：`UserError` 是否隐含可绕过（`-y`）？**
→ **否**。`UserError` 只表示"用户可操作的恢复"；是否提供 `-y`/`--yes` 绕过由 **command 拥有**。`recoverable` 元数据描述可恢复性，与绕过是两回事。

**Q3：每个 local 诊断异常都必须继承 `VibeError` 吗？**
→ **SHOULD，非 MUST**。§四登记的 8 类作为文档化例外保留。新增类默认继承 `VibeError` 子树；保留游离形态需在 §四登记 + 写理由。

**Q4：类层级 taxonomy 与 error-code/FailedGate 语义各归谁？**
→ 类层级（Axis A）归**本标准**；error-code → severity → FailedGate（Axis B）归 `ErrorHandlingContract` + [error-severity-and-blocking-standard.md](./v3/error-severity-and-blocking-standard.md)。两者正交（§一）。

---

## 七、Agent 决策规则

```
IF 错误影响系统功能正确性（依赖/外部服务/契约违反）：
    抛 SystemError（fail-fast）

ELIF 错误是用户操作不符（格式/规则/受保护资源）：
    抛 UserError（command 决定是否给 -y 绕过）

ELIF 批量任务中单个失败：
    收集错误，继续其他任务，结束后统一报告（模式，非 BatchError 类）
```

| 场景 | 类 | 处置 |
|---|---|---|
| Serena AST 分析失败 | SystemError | 立即抛 SerenaError |
| commit message 缺前缀 | UserError | 提示，command 可给 `--yes` |
| 覆盖率检查失败 | UserError | 提示，command 可给 `--skip-coverage` |
| 受保护分支建 flow | UserError | 抛 MainBranchProtectedError（§四） |
| 批量分析 10 文件 3 失败 | 模式 | 继续，最后抛 SystemError 汇总 |
| 配置文件格式错误 | SystemError | 立即抛 |
| GitHub API 调用失败 | SystemError | 立即抛 |

---

## 八、代码审查检查清单

- [ ] `except` 块目的明确：SystemError 重抛或包装；UserError 由 command 决定绕过
- [ ] 无空 `except: pass`
- [ ] 无返回错误字典的静默失败
- [ ] 批量操作用"收集 → 继续 → 统一报告"模式（§三），不造 `BatchError` 类
- [ ] SystemError 不被当 UserError 处理
- [ ] 新增游离异常已登记 §四表

---

## 九、迁移与兼容边界

- **本标准为方向 C（双轴正交）落地**：类层级与 severity/gate 解耦
- **不迁移**：§四 8 类保留现状
- **不新增 `BatchError` 类**：批量场景用模式
- **CLI catch**：`VibeError` 子树；游离异常各自处理
- **CLAUDE.md HARD RULE 13**（错误处理分类）继续生效：SystemError fail-fast / UserError 提供恢复路径 / 批量继续后报告

---

## 关联

- 基线 spec：`.specify/specs/010-exception-model/spec.md`
- 基线 epic：#3299
- RFC 决策：#3307（方向 C）

---

**文档版本**：2.0（方向 C 双轴正交）
**创建日期**：2026-03-19
**最后更新**：2026-07-07
**作者**：Claude Agent（Opus 4.8，#3307 落地）
**状态**：active
