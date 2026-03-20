# Implementation Plan: 收敛 review 管道契约并拆分 prompt/hook 结构

**Issue**: #210
**Type**: Refactor
**Date**: 2026-03-20
**Status**: Draft - Awaiting User Approval

---

## 执行摘要

本次重构聚焦 review 管道自身的契约与分层治理,解决以下核心问题:

1. **Prompt 组装职责分散** - policy/scope/AST/task 分布在代码、配置、文件三处
2. **Hook-CLI 契约漂移** - `pre-push.sh` 使用 `--agent` 参数,但 CLI 并未定义此选项
3. **动态 scope 缺失模型** - base/pr 两种模式靠散传参数,无统一抽象
4. **Shell 集成测试不足** - 现有测试只 mock 内部逻辑,未覆盖真实 shell 契约

---

## 现状问题分析

### 问题 1: Hook-CLI 参数不匹配

**文件**: `scripts/hooks/pre-push.sh` (Line 63)

```bash
REVIEW_RESULT=$(uv run python src/vibe3/cli.py review base --agent code-reviewer 2>&1)
```

**问题**: CLI `review base` 命令没有定义 `--agent` 选项。当前命令签名只接受 `base_branch`、`--trace`、`--dry-run`、`--message`。

**影响**: 此参数被静默忽略,hook 实际使用 `config/settings.yaml` 中的 `agent_config.agent` 值,但开发者可能误以为可以覆盖。

### 问题 2: Prompt 拼装职责分散

**当前 prompt 来源**:

| 来源 | 内容 | 文件 |
|------|------|------|
| 文件读取 | review policy | `.codex/review-policy.md` |
| 配置 | tools guide | `config/settings.yaml:52` |
| 配置 | output format | `config/settings.yaml:63-73` |
| 配置 | review task | `config/settings.yaml:75-80` |
| 运行时 | changed_symbols | `context_builder.py:79-96` |
| 运行时 | symbol_dag | `context_builder.py:87-93` |

**问题**: 修改任一部分时,需要同时考虑文件、配置、代码三处,容易遗漏或漂移。

### 问题 3: Scope 模型缺失

**当前 `review` 命令结构**:

```
review.py
├── pr(pr_number, trace, dry_run, message)
└── base(base_branch, trace, dry_run, message)
```

**问题**:
- `pr` 和 `base` 共享大量重复逻辑(约 50 行)
- 没有统一的 scope 概念
- 后续扩展 `review ready` / 云端 review 时会更混乱

### 问题 4: 测试覆盖不完整

**现有测试文件**:
- `tests/vibe3/hooks/test_pre_push_review_gate.py` - 只测试 Python 层触发逻辑,未测试 shell 脚本
- `tests/vibe3/services/test_context_builder.py` - 只测试最终输出,未分段测试
- `tests/vibe3/commands/test_review_base.py` - 完全 mock,未测试参数传递

**缺失测试**:
- shell 脚本实际调用命令是否正确
- `--agent` 等不存在参数是否被正确拒绝
- `VERDICT: BLOCK` 是否真正阻断 push

---

## 实施阶段

### Phase 1: 引入数据模型

**目标**: 建立 `ReviewScope` 和 `ReviewRequest` 模型,替代散传参数

**新建文件**: `src/vibe3/models/review.py`

**实施步骤**:

1. **定义 ReviewScope dataclass**
   ```python
   @dataclass(frozen=True)
   class ReviewScope:
       kind: Literal["base", "pr"]
       base_branch: str | None = None
       pr_number: int | None = None

       def __post_init__(self) -> None:
           if self.kind == "base" and not self.base_branch:
               raise ValueError("base scope requires base_branch")
           if self.kind == "pr" and not self.pr_number:
               raise ValueError("pr scope requires pr_number")
   ```

2. **定义 ReviewRequest dataclass**
   ```python
   @dataclass(frozen=True)
   class ReviewRequest:
       scope: ReviewScope
       changed_symbols: dict[str, list[str]] | None = None
       symbol_dag: dict[str, list[str]] | None = None
       task_guidance: str | None = None
   ```

3. **添加工厂方法**
   ```python
   @classmethod
   def for_base(cls, base_branch: str = "origin/main") -> "ReviewScope": ...

   @classmethod
   def for_pr(cls, pr_number: int) -> "ReviewScope": ...
   ```

**验收标准**:
- [ ] 类型检查通过: `uv run mypy src/vibe3/models/review.py`
- [ ] 单元测试覆盖 `__post_init__` 验证逻辑
- [ ] 文件行数 < 100 行

**风险**: 低 - 新增文件,不影响现有功能

---

### Phase 2: 拆分 context_builder

**目标**: 从"大字符串拼装器"拆为职责清晰的 section builders

**修改文件**: `src/vibe3/services/context_builder.py`

**当前问题**: 单函数 134 行,职责混杂

**实施步骤**:

1. **提取 build_policy_section**
   - 输入: `policy_path` 或从 config 读取
   - 输出: policy markdown 字符串
   - 职责: 读取 `.codex/review-policy.md`

2. **提取 build_tools_guide_section**
   - 输入: `tools_guide_path` 或从 config 读取
   - 输出: tools guide 字符串
   - 职责: 读取 `.agent/rules/cli-usage.md`

3. **提取 build_ast_analysis_section**
   - 输入: `changed_symbols`, `symbol_dag`
   - 输出: JSON 格式的 AST 分析段落
   - 职责: 格式化运行时注入的符号信息

4. **提取 build_review_task_section**
   - 输入: `task_guidance` 或从 config 读取
   - 输出: review task 段落
   - 职责: 组装任务指导信息

5. **提取 build_output_contract_section**
   - 输入: `output_format` 或默认值
   - 输出: VERDICT 格式要求段落
   - 职责: 定义输出契约

6. **重构 build_review_context 为 orchestration 函数**
   - 接收 `ReviewRequest` 参数
   - 调用各 section builder
   - 组装最终 prompt

**验收标准**:
- [ ] 每个 section builder 有独立单元测试
- [ ] 原有集成测试继续通过
- [ ] 主函数 < 50 行
- [ ] 文件总行数 < 300 行

**风险**: 中 - 需要确保输出格式与现有行为一致

---

### Phase 3: 重构 review command

**目标**: 使用 `ReviewRequest` 统一 base/pr 逻辑,消除重复代码

**修改文件**:
- `src/vibe3/commands/review.py`
- `src/vibe3/services/review_runner.py`

**实施步骤**:

1. **提取共享逻辑到私有函数**
   ```python
   def _run_review(request: ReviewRequest, config: VibeConfig, dry_run: bool) -> None:
       # 共享的 review 执行逻辑
   ```

2. **简化 pr/base 命令为薄包装**
   ```python
   @app.command()
   def pr(pr_number: int, trace: bool = False, dry_run: bool = False, message: str | None = None) -> None:
       scope = ReviewScope.for_pr(pr_number)
       request = ReviewRequest(scope=scope, task_guidance=message)
       _run_review(request, config, dry_run)
   ```

3. **更新 review_runner 接口**
   - 接收 `ReviewRequest` 参数
   - 传递给 `context_builder`

**验收标准**:
- [ ] `pr` 和 `base` 命令的重复代码 < 10 行
- [ ] CLI 调用方式保持不变(外部兼容)
- [ ] 命令测试覆盖 base/pr 两种模式

**风险**: 中 - 需要确保 CLI 行为不变

---

### Phase 4: 修复 Hook-CLI 契约并抽象入口

**目标**: 让 `pre-push.sh` 只负责编排,不维护协议细节

**修改文件**:
- `scripts/hooks/pre-push.sh`
- 新建: `src/vibe3/commands/review_gate.py`

**当前问题**:
- Hook 使用 `--agent` 参数但 CLI 未定义
- Hook 内嵌 review 协议细节

**实施步骤**:

1. **创建 review_gate command**
   ```python
   @app.command("review-gate")
   def review_gate(
       check_block: Annotated[bool, typer.Option("--check-block")] = False,
   ) -> None:
       """Pre-push review gate: check risk and optionally run review.

       Exit codes:
       - 0: Pass (low risk or review passed)
       - 1: Block (high risk with BLOCK verdict)
       - 2: Error (inspect/review execution failed)
       """
   ```

2. **封装 review gate 逻辑**
   - 调用 `inspect base --json` 获取 risk level
   - HIGH/CRITICAL 时触发 `review base`
   - 解析 verdict,返回正确的 exit code

3. **简化 pre-push.sh**
   ```bash
   # Before (87 lines, with inline review logic)
   REVIEW_RESULT=$(uv run python src/vibe3/cli.py review base --agent code-reviewer 2>&1)

   # After (simplified)
   uv run python src/vibe3/cli.py review-gate --check-block
   ```

**验收标准**:
- [ ] `review-gate --check-block` 有独立测试
- [ ] `VERDICT: BLOCK` 正确返回 exit code 1
- [ ] Shell 脚本行数减少 50%+

**风险**: 高 - 改变 hook 行为,需充分测试

---

### Phase 5: 固化 Contract Tests

**目标**: 让 shell-level contract test 成为正式护栏

**修改/新建文件**:
- `tests/vibe3/hooks/test_pre_push_review_gate.py` (扩展)
- 新建: `tests/vibe3/commands/test_review_gate.py`
- 新建: `tests/vibe3/integration/test_review_shell_contract.py`

**实施步骤**:

1. **补充 section builder 单元测试**
   - `test_build_policy_section_reads_file`
   - `test_build_ast_analysis_section_formats_json`
   - `test_build_review_task_section_uses_config`
   - `test_build_output_contract_section_includes_verdict`

2. **补充命令测试**
   - `test_review_base_creates_correct_scope`
   - `test_review_pr_creates_correct_scope`
   - `test_review_rejects_unknown_params` (验证 `--agent` 等无效参数被拒绝)

3. **补充 shell 集成测试**
   ```python
   def test_pre_push_calls_review_gate_command():
       """Verify pre-push.sh calls review-gate, not review base --agent."""
       result = subprocess.run(
           ["bash", "-n", "scripts/hooks/pre-push.sh"],  # syntax check
           capture_output=True,
       )
       assert result.returncode == 0

       # Verify it uses review-gate
       with open("scripts/hooks/pre-push.sh") as f:
           content = f.read()
       assert "review-gate" in content
       assert "--agent" not in content  # No stale params

   def test_review_gate_blocks_on_verdict():
       """Verify review-gate returns 1 on BLOCK verdict."""
       with patch(...) as mock_review:
           mock_review.return_value = mock_result(verdict="BLOCK")
           result = runner.invoke(app, ["review-gate", "--check-block"])
       assert result.exit_code == 1
   ```

4. **添加回归测试标记**
   ```python
   @pytest.mark.regression("issue-210")
   def test_pre_push_syncs_on_field_rename():
       """Ensure hook uses correct field names from inspect JSON."""
   ```

**验收标准**:
- [ ] 测试覆盖率 > 80%
- [ ] 所有回归点有明确测试用例
- [ ] CI 中运行 shell 集成测试

**风险**: 低 - 测试层面改动

---

### Phase 6: 清理配置漂移

**目标**: 明确配置真源与运行时生成的边界

**修改文件**:
- `config/settings.yaml`
- `src/vibe3/services/context_builder.py`

**实施步骤**:

1. **审查 settings.yaml review 相关配置**
   - 识别静态配置
   - 识别运行时注入需求

2. **添加配置来源注释**
   ```yaml
   review:
     # Static: read by context_builder at runtime
     policy_file: ".codex/review-policy.md"

     # Static: agent configuration for codeagent-wrapper
     agent_config:
       agent: "code-reviewer"

     # Template: may include placeholders for runtime values
     review_task: |
       - Run `git diff <base>...HEAD` to see file changes
   ```

3. **更新代码注释**
   - 在每个 section builder 中标明数据来源
   - 添加 `# Source: config/settings.yaml` 或 `# Source: runtime parameter`

**验收标准**:
- [ ] 配置项有清晰的职责边界
- [ ] 代码注释标明数据来源
- [ ] 无运行时覆盖静态配置的行为

**风险**: 低 - 文档层面改动

---

## 涉及文件清单

### 核心文件(必须修改)

| 文件 | 操作 | 预估行数 |
|------|------|----------|
| `src/vibe3/models/review.py` | 新建 | ~80 |
| `src/vibe3/services/context_builder.py` | 重构 | 134 → ~250 |
| `src/vibe3/commands/review.py` | 重构 | 189 → ~120 |
| `src/vibe3/services/review_runner.py` | 调整 | 205 → ~180 |
| `src/vibe3/commands/review_gate.py` | 新建 | ~60 |
| `scripts/hooks/pre-push.sh` | 简化 | 87 → ~40 |

### 测试文件

| 文件 | 操作 |
|------|------|
| `tests/vibe3/models/test_review.py` | 新建 |
| `tests/vibe3/services/test_context_builder.py` | 扩展 |
| `tests/vibe3/commands/test_review.py` | 扩展 |
| `tests/vibe3/commands/test_review_gate.py` | 新建 |
| `tests/vibe3/hooks/test_pre_push_review_gate.py` | 扩展 |
| `tests/vibe3/integration/test_review_shell_contract.py` | 新建 |

### 配置文件

| 文件 | 操作 |
|------|------|
| `config/settings.yaml` | 添加注释 |

---

## 风险与缓解

### 风险 1: Hook 行为变更导致 push 失败

**概率**: 中
**影响**: 高

**缓解措施**:
1. Phase 5 先补充测试,再重构 hook
2. `review-gate` 提供 `--dry-run` 选项用于调试
3. 保留原 `review base` 命令,让用户可以手动调用

### 风险 2: 重构影响现有 review 功能

**概率**: 低
**影响**: 中

**缓解措施**:
1. 保持外部 API 兼容(CLI 调用方式不变)
2. 增加测试覆盖
3. 分阶段实施,每阶段独立验证

### 风险 3: 配置迁移导致用户配置失效

**概率**: 低
**影响**: 中

**缓解措施**:
1. 保留向后兼容的配置读取逻辑
2. 只添加注释,不改变配置结构
3. 提供配置迁移指南(如有必要)

---

## 非目标

- 本 issue 不处理 `inspect` / `commands` 业务逻辑下沉(#206)
- 不引入云端 review 能力
- 不修改 review prompt 的具体内容(只重组结构)
- 不删除或迁移 `.codex/review-policy.md` 文件

---

## 验收标准

- [ ] 所有 phase 的验收标准通过
- [ ] `uv run pytest` 全部通过
- [ ] `uv run mypy src/vibe3` 类型检查通过
- [ ] 代码行数符合规范(< 800 行/文件)
- [ ] 文档更新完成(代码注释 + CLAUDE.md)

---

## 预期收益

1. **降低契约漂移概率**: 修改点集中,hook/CLI/config 边界清晰
2. **提高可测试性**: 每个 section builder 可独立测试
3. **易于演进**: 为本地/云端 review 分离奠定基础
4. **减少维护负担**: Shell 脚本行数减少 50%+

---

## 实施顺序建议

```
Phase 1 (数据模型) ─────────────────────────────────────────────────┐
                                                                    │
Phase 2 (拆分 context_builder) ─────────────────────────────────────┤
                                                                    │
Phase 3 (重构 review command) ──────────────────────────────────────┤  顺序依赖
                                                                    │
Phase 5.1-5.2 (补充单元/命令测试) ───────────────────────────────────┤
                                                                    │
Phase 4 (修复 Hook 契约) ───────────────────────────────────────────┤
                                                                    │
Phase 5.3 (补充 shell 集成测试) ─────────────────────────────────────┤
                                                                    │
Phase 6 (清理配置漂移) ─────────────────────────────────────────────┘
```

---

**请确认是否批准此计划开始实施。如有疑问或需要调整,请告知。**