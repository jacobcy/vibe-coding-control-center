# Vibe Center 质量检查标准

> **文档定位**：定义代码质量检查的多层次防御体系
> **适用范围**：所有代码提交、推送和合并流程
> **权威性**：本标准为质量检查的权威依据，详见 [SOUL.md](../../SOUL.md) §0

---

## 概述

Vibe Center 采用**多层次质量防御**策略，在不同阶段执行不同严格度的检查，平衡开发效率与代码质量。

**核心原则**：
- **快速反馈**：本地检查快速响应，减少等待时间
- **渐进严格**：从commit到merge，检查逐步严格
- **软硬结合**：质量红线硬性阻断，架构建议软性提醒
- **风险驱动**：高风险变更触发更严格检查

---

## 一、检查阶段与职责

### 1.1 Pre-commit（本地提交）

**目标**：保证基本代码质量，快速反馈

**执行时机**：`git commit` 触发

**必须通过（硬性阻断）**：
- ✅ **Lint检查**（Ruff）：代码风格和常见错误
- ✅ **Format检查**（Black）：代码格式统一
- ✅ **Type检查**（MyPY）：类型安全

**不检查项**：
- ❌ 测试（由pre-push负责，保持commit快速）
- ❌ 总LOC限制（开发过程允许超标）
- ❌ Review gate（本地提交不需要review）
- ❌ Coverage gate（本地不强制覆盖率）

**时间预算**：< 10秒

**配置位置**：`.pre-commit-config.yaml`

**绕过方式**：紧急情况可用 `git commit --no-verify`（需事后补救）

---

### 1.2 Pre-push（推送前）

**目标**：拦截高风险代码，保护远程仓库质量

**执行时机**：`git push` 触发

**必须通过（硬性阻断）**：
- ✅ **Compile检查**：Python语法正确性
- ✅ **Type检查**（MyPy）：类型安全（再次确认）
- ✅ **测试套件**（Pytest + Bats）：全量测试通过
- ✅ **Review gate**（高风险触发）：
  - 基于风险评分自动决定
  - 高风险（score ≥ block_threshold）必须review通过
  - Review结果为BLOCK则push失败

**警告提示（不阻断）**：
- ⚠️ **总LOC超标**：Python/Shell总行数超限
- ⚠️ **单文件LOC超标**：部分文件过大
- ⚠️ **高风险建议**：风险接近阈值时建议review

**时间预算**：~1-2分钟

**配置位置**：`.pre-commit-config.yaml` (stages: [pre-push])

**绕过方式**：无（保护远程仓库质量）

---

### 1.3 CI（持续集成）

**目标**：确保最终代码质量，拦截所有违规

**执行时机**：PR创建、更新，或push到main

**必须通过（硬性阻断）**：
- ✅ **所有测试**：完整测试套件（pytest + bats）
- ✅ **Lint + Format + Type**：代码质量三要素
- ✅ **LOC限制**（ENFORCE_LOC_LIMITS=true）：
  - Python总LOC ≤ 20,000（config可调）
  - Shell总LOC ≤ 7,000
  - 单文件LOC ≤ 400（max限制）
- ✅ **Coverage gate**（如配置）：测试覆盖率要求

**警告提示**：
- ⚠️ 单文件LOC > 300（default限制）
- ⚠️ 代码复杂度警告

**配置位置**：`.github/workflows/ci.yml`

**失败处理**：PR不可merge，需修复后重新提交

---

### 1.4 Merge前（最终防线）

**目标**：确保合并代码经过充分审核

**必须通过（硬性阻断）**：
- ✅ **所有CI检查通过**
- ✅ **Review要求**（GitHub Branch Protection）：
  - 至少1个approved review（个人项目可调整为0）
  - 无requesting changes
  - 所有conversation resolved

**实现方式**：GitHub Branch Protection Rules

**配置位置**：GitHub仓库设置 → Branches → Branch protection rules

**配置建议**：
```yaml
# 推荐配置（团队项目）
Require pull request reviews before merging:
  - Required approving reviews: 1
  - Dismiss stale pull request approvals when new commits are pushed
  - Require review from Code Owners (if applicable)

# 个人项目配置
Required approving reviews: 0  # 允许self-merge，但需CI通过
```

**无法通过CI实现**：
- ❌ CI只能检查代码质量，无法强制review流程
- ✅ GitHub Branch Protection是唯一可靠方式

---

## 二、检查项详细说明

### 2.1 Lint检查（Ruff）

**目的**：捕获代码风格问题和潜在bug

**工具**：Ruff（替代Flake8、isort等）

**检查内容**：
- 未使用的import/变量
- 代码风格问题
- 潜在bug（如未定义变量）
- import顺序

**配置**：`pyproject.toml` → `[tool.ruff]`

**阻断性**：Pre-commit ✅ 阻断 | CI ✅ 阻断

---

### 2.2 Format检查（Black）

**目的**：统一代码格式，减少review噪音

**工具**：Black

**检查内容**：
- 代码格式（缩进、空格、换行等）
- 行长度限制（默认88字符）

**配置**：`pyproject.toml` → `[tool.black]`

**阻断性**：Pre-commit ✅ 阻断 | CI ✅ 阻断

---

### 2.3 Type检查（MyPy）

**目的**：确保类型安全，减少运行时错误

**工具**：MyPy

**检查内容**：
- 类型注解正确性
- 类型推断错误
- Optional类型处理

**配置**：`pyproject.toml` → `[tool.mypy]`

**阻断性**：Pre-commit ✅ 阻断 | Pre-push ✅ 阻断 | CI ✅ 阻断

---

### 2.4 测试（Pytest + Bats）

**目的**：验证功能正确性

**工具**：
- Python: Pytest
- Shell: Bats

**检查内容**：
- 单元测试通过
- 集成测试通过
- 测试覆盖率（可选）

**配置**：`pytest.ini`, `tests/`

**阻断性**：
- Pre-commit: ❌ 不运行（保持commit快速）
- Pre-push: ✅ 阻断（全量测试）
- CI: ✅ 阻断（全量测试）

---

### 2.5 LOC检查（代码量控制）

**目的**：防止代码膨胀，鼓励模块化

**核心原则（治理哲学）**：
1. **LOC 上限 = 代码膨胀预警器**：命中上限时触发一次质量回收审计，而不是硬性阻塞开发
2. **各层有各层的合理密度**：
   - `commands` 越薄越好（业务下沉到 services）
   - `services` 容忍核心聚合（登记例外即可）
   - `clients` 允许少量样板换取类型安全
3. **承认沉没成本**：既有的拆分/聚合都有其上下文，只在对齐收益明显时才重构

**检查维度**：
1. **总LOC**：Python ≤ 32,000 | Shell ≤ 7,000（治理触发器）
2. **单文件LOC**：Default ≤ 300 | Max ≤ 400（例外需登记）

**例外登记机制**：
```yaml
# config/settings.yaml
code_limits:
  single_file_loc:
    exceptions:
      - path: "src/vibe3/services/flow_service.py"
        limit: 600
        reason: "核心状态机聚合"
```

**阻断性**：
- Pre-commit: - 不检查（保持commit快速）
- Pre-push: ⚠️ Warning only（允许draft PR）
- CI: ✅ 阻断（最终合并前强制，但可通过例外登记豁免）

**实现方式**：
```bash
# 本地开发：warning only
bash scripts/hooks/check-python-loc.sh  # exits 0

# CI：enforce limits
ENFORCE_LOC_LIMITS=true bash scripts/hooks/check-python-loc.sh  # exits 1 if over
```

**配置**：`config/loc_limits.yaml` → `code_limits`

---

### 2.6 Review Gate（风险驱动审查）

**目的**：高风险代码必须经过review

**触发条件**：
- 风险评分 ≥ block_threshold（默认12）
- 评分因素：
  - 改动文件数量
  - 改动行数
  - 影响的模块数
  - 是否触及核心模块

**执行流程**：
1. Pre-push计算风险评分
2. 如果 score ≥ threshold → 触发本地review
3. Review结果：
   - **PASS** → 允许push
   - **MAJOR** → 允许push（提醒关注）
   - **BLOCK** → 禁止push（需修复）

**工具**：`vibe3 inspect base` + `vibe3 review base`

**配置**：`src/vibe3/services/risk_score_service.py`

**阻断性**：Pre-push ✅ 阻断（高风险代码）

---

### 2.7 Coverage Gate（覆盖率门槛）

**目的**：保证测试充分性

**检查内容**：
- 代码覆盖率 ≥ 阈值（如80%）

**阻断性**：
- Pre-commit/Pre-push: 不检查
- **CI**: ✅ 阻断（最终合并前强制）
- **pr ready**: ❌ 不再作为硬性门禁。`pr ready` 仅作为人类发起评审的信号，并自动生成 Reviewer Briefing 提供上下文。

**配置**：`config/settings.yaml` → `coverage.threshold`

**实现**：由 CI 执行或通过 `vibe3 review` 手动验证。

---

## 三、特殊场景处理

### 3.1 紧急修复（Hotfix）

**允许绕过**：Pre-commit 可用 `--no-verify`

**要求**：
1. 创建issue记录绕过原因
2. 修复后立即补充测试和review
3. 24小时内完成补救

**禁止绕过**：Pre-push和CI不可绕过

---

### 3.2 Draft PR（草稿PR）

**宽松检查**：
- Pre-push允许LOC超标
- 允许测试失败（标记为draft）

**严格要求**：
- 标记为"Ready for review"时必须通过所有检查

---

### 3.3 大型重构

**挑战**：代码量必然超标，如何渐进提交？

**解决方案**：
1. **Pre-commit**：不检查总LOC，允许超标提交
2. **Pre-push**：Warning only，允许超标推送
3. **Draft PR**：持续推送草稿，CI warning但不阻断
4. **Final PR**：重构完成后，拆分多个PR逐步降低代码量
5. **Merge前**：必须符合LOC限制，或申请临时豁免

**LOC豁免申请**：
- 在PR中说明理由
- 创建技术债务issue跟踪
- 设置改进deadline

---

## 四、配置与维护

### 4.1 配置文件索引

| 检查项 | Pre-commit | Pre-push | CI | 配置文件 |
|--------|------------|----------|-----|----------|
| Lint | ✅ | - | ✅ | `.pre-commit-config.yaml` |
| Format | ✅ | - | ✅ | `.pre-commit-config.yaml` |
| Type | ✅ | ✅ | ✅ | `.pre-commit-config.yaml` |
| Test | - | ✅ | ✅ | `.pre-commit-config.yaml` |
| LOC | - | ⚠️ | ✅ | `config/loc_limits.yaml` |
| Review | - | ✅ | - | `scripts/hooks/pre-push.sh` |
| Coverage | - | - | ✅ | `CI / Manual` |

### 4.2 阈值调整

**LOC限制调整**：
```yaml
# config/loc_limits.yaml
code_limits:
  total_file_loc:
    v3_python: 32000  # 可根据项目规模调整（治理触发器）
    v2_shell: 7000
  single_file_loc:
    default: 300
    max: 400
    # 例外登记见上文"例外登记机制"
```

**Review gate阈值调整**：
```python
# src/vibe3/services/risk_score_service.py
BLOCK_THRESHOLD = 12  # 可调整风险敏感度
```

**Coverage阈值调整**：
```yaml
# config/settings.yaml
coverage:
  threshold: 80  # 覆盖率要求
```

### 4.3 临时豁免文件

**单文件LOC豁免**：
```bash
# scripts/hooks/check-per-file-loc.sh
IGNORE_FILES=(
  "src/vibe3/clients/git_client.py"  # TODO: Split into git_branch.py
)
```

**要求**：
- 必须有TODO注释说明拆分计划
- 必须创建issue跟踪
- 必须设置deadline

---

## 五、最佳实践

### 5.1 开发流程建议

**小步提交**：
- ✅ 频繁commit，每次小改动
- ✅ Pre-commit快速反馈
- ✅ 失败立即修复，不累积问题

**风险控制**：
- ✅ 大改动先评估风险评分：`vibe3 inspect base origin/main`
- ✅ 高风险提前review，不等到push
- ✅ 拆分大型PR为多个小型PR

**代码质量**：
- ✅ 保持单文件 < 200行
- ✅ 写测试，保持覆盖率 > 80%
- ✅ 类型注解完整，MyPy严格模式

---

### 5.2 常见问题排查

**问题1：Pre-commit太慢**
- 检查是否运行了完整测试（应该只运行相关测试）
- 优化测试速度：使用pytest-xdist并行
- 考虑拆分pre-commit和pre-push测试

**问题2：LOC总是超标**
- 分析是否需要拆分模块
- 检查是否有未清理的dead code
- 申请临时豁免并制定改进计划

**问题3：Review gate误报**
- 调整风险评分阈值
- 检查是否误判核心模块
- 更新review配置

---

## 六、术语表

| 术语 | 定义 |
|------|------|
| **硬性阻断** | 检查失败时阻止操作继续，必须修复才能推进 |
| **软性提醒** | 检查失败时显示警告，但不阻止操作继续 |
| **LOC** | Lines of Code，代码行数 |
| **Review gate** | 风险驱动的代码审查门禁，高风险变更必须review |
| **Coverage gate** | 测试覆盖率门禁，覆盖率不足时阻止合并 |
| **Draft PR** | 草稿PR，表示工作未完成，不要求通过所有检查 |
| **Branch Protection** | GitHub分支保护规则，强制merge前要求 |

---

## 七、参考文档

- [SOUL.md](../../SOUL.md) - 项目宪法
- [error-handling.md](./error-handling.md) - 错误处理规范
- [github-code-review-standard.md](./github-code-review-standard.md) - 代码审查标准
- [vibe3-command-standard.md](./vibe3-command-standard.md) - 命令设计标准

---

**文档版本**：v1.0
**最后更新**：2026-03-25
**维护者**：Vibe Center Team