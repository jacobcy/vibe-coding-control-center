# Implementation Plan: 收敛 review 管道契约并拆分 prompt/hook 结构

**Issue**: #210
**Type**: Refactor
**Date**: 2026-03-20

## 执行摘要

本次重构聚焦 review 管道自身的契约与分层治理，解决 prompt 组装职责分散、调用契约不统一、hook 测试覆盖不足和动态 scope 模型缺失的问题。

## 目标

1. 为 review prompt 建立清晰的分层模型
2. 为 review 调用建立单一 contract 入口
3. 让 shell-level contract test 成为正式护栏
4. 清理死代码、配置漂移和重复职责

## 实施阶段

### Phase 1: 引入数据模型（ReviewScope + ReviewRequest）

**目标**: 建立明确的 review scope 模型，替代散传的可选参数

**改动文件**:
- 新建 `src/vibe3/models/review.py`

**实施步骤**:
1. 定义 `ReviewScope` dataclass：
   - `kind: Literal["base", "pr"]`
   - `base_branch: Optional[str] = None`
   - `pr_number: Optional[int] = None`

2. 定义 `ReviewRequest` dataclass：
   - `scope: ReviewScope`
   - `changed_symbols: Optional[List[SymbolRef]] = None`
   - `task_guidance: Optional[str] = None`

3. 添加 `__post_init__` 验证：
   - `kind="base"` 时必须有 `base_branch`
   - `kind="pr"` 时必须有 `pr_number`

**验收标准**:
- [ ] 类型检查通过：`uv run mypy src/vibe3/models/review.py`
- [ ] 单元测试覆盖验证逻辑

### Phase 2: 拆分 context_builder

**目标**: 从"大字符串拼装器"拆为几个职责清晰的小段

**改动文件**:
- `src/vibe3/services/context_builder.py`
- `tests/vibe3/services/test_context_builder.py`

**实施步骤**:
1. 提取 `build_review_scope_section(scope: ReviewScope) -> str`
2. 提取 `build_ast_analysis_section(symbols: List[SymbolRef]) -> str`
3. 提取 `build_review_task_section(guidance: str) -> str`
4. 提取 `build_output_contract_section() -> str`
5. 重构 `build_review_context()` 为 orchestration 函数：
   - 接收 `ReviewRequest` 参数
   - 调用各 section builder
   - 组装最终 prompt

**验收标准**:
- [ ] 每个 section builder 有独立单元测试
- [ ] 原有集成测试继续通过
- [ ] 代码行数 < 800 行

### Phase 3: 重构 review command

**目标**: 使用 `ReviewRequest` 替代散传参数

**改动文件**:
- `src/vibe3/commands/review.py`
- `src/vibe3/services/review_runner.py`

**实施步骤**:
1. 修改 `review` command 签名：
   - 移除散传的 `--base-branch` / `--pr-number`
   - 接受 `ReviewRequest` 对象（内部构建）

2. 更新 `review_runner` 接口：
   - 接收 `ReviewRequest` 参数
   - 传递给 `context_builder`

**验收标准**:
- [ ] CLI 调用方式保持不变（外部兼容）
- [ ] 内部使用 `ReviewRequest` 传递
- [ ] 命令测试覆盖 base/pr 两种模式

### Phase 4: 抽出 hook 可复用入口

**目标**: 让 `pre-push.sh` 只负责编排，不维护协议细节

**改动文件**:
- `scripts/hooks/pre-push.sh`
- 新建 `src/vibe3/commands/review_gate.py`

**实施步骤**:
1. 创建 `review_gate` command：
   - 封装 risk 读取、review 触发、verdict 解析
   - 提供 `--check-block` 选项用于 hook 调用
   - 返回明确的 exit code

2. 简化 `pre-push.sh`：
   - 调用 `uv run python -m vibe3.cli review-gate --check-block`
   - 移除内联的 review 协议细节

**验收标准**:
- [ ] Hook 测试覆盖 `--check-block` 模式
- [ ] `VERDICT: BLOCK` 正确阻断 push
- [ ] Shell 脚本行数减少 50%+

### Phase 5: 固化 contract tests

**目标**: 让 shell-level contract test 成为正式护栏

**改动文件**:
- `tests/vibe3/hooks/test_pre_push_review_gate.py`
- 新建 `tests/vibe3/commands/test_review_gate.py`

**实施步骤**:
1. 补充单元测试：
   - `test_build_review_scope_section`
   - `test_build_ast_analysis_section`
   - `test_build_review_task_section`
   - `test_build_output_contract_section`

2. 补充命令测试：
   - `test_review_base_scope_wiring`
   - `test_review_pr_scope_wiring`

3. 补充 shell 集成测试：
   - `test_pre_push_calls_correct_command`
   - `test_pre_push_no_stale_params`
   - `test_pre_push_blocks_on_verdict`
   - `test_pre_push_syncs_on_field_rename`

**验收标准**:
- [ ] 测试覆盖率 > 80%
- [ ] 所有回归点有明确测试用例
- [ ] CI 中运行 shell 集成测试

### Phase 6: 清理配置漂移

**目标**: 明确配置真源与运行时生成的边界

**改动文件**:
- `config/settings.yaml`
- `src/vibe3/services/context_builder.py`

**实施步骤**:
1. 审查 `settings.yaml` 中的 review 相关配置：
   - 识别哪些是静态 policy（保留在 config）
   - 识别哪些是动态注入（移到代码层）

2. 更新 `context_builder`：
   - 明确从 config 读取的内容
   - 明确从 runtime 注入的内容

3. 更新文档：
   - 在代码注释中标明数据来源
   - 更新 `docs/standards/` 中相关说明

**验收标准**:
- [ ] 配置项有清晰的职责边界
- [ ] 代码注释标明数据来源
- [ ] 文档与实现一致

## 涉及文件清单

**核心文件**:
- `src/vibe3/models/review.py` (新建)
- `src/vibe3/services/context_builder.py` (重构)
- `src/vibe3/commands/review.py` (重构)
- `src/vibe3/services/review_runner.py` (重构)
- `src/vibe3/commands/review_gate.py` (新建)
- `scripts/hooks/pre-push.sh` (简化)

**测试文件**:
- `tests/vibe3/services/test_context_builder.py` (扩展)
- `tests/vibe3/commands/test_review.py` (扩展)
- `tests/vibe3/commands/test_review_gate.py` (新建)
- `tests/vibe3/hooks/test_pre_push_review_gate.py` (扩展)

**配置文件**:
- `config/settings.yaml` (清理)

## 风险与缓解

**风险 1**: 重构影响现有 review 功能
- **缓解**: 保持外部 API 兼容，增加测试覆盖

**风险 2**: Hook 行为变更导致 push 失败
- **缓解**: Phase 5 先补测试，再重构 hook

**风险 3**: 配置迁移导致用户配置失效
- **缓解**: 保留向后兼容的配置读取逻辑

## 非目标

- 本 issue 不处理 `inspect` / `commands` 业务逻辑下沉（#206）
- 不引入云端 review 能力
- 不修改 review prompt 的具体内容（只重组结构）

## 验收标准

- [ ] 所有 phase 的验收标准通过
- [ ] `uv run pytest` 全部通过
- [ ] `uv run mypy src/vibe3` 类型检查通过
- [ ] 代码行数符合规范（< 800 行/文件）
- [ ] 文档更新完成

## 预期收益

- review 管道修改点更集中，降低契约漂移概率
- hook / CLI / config 边界更清晰
- prompt 结构更稳定，易于演进
- 为本地/云端 review 分离奠定基础