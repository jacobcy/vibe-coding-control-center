# Vibe Center 2.0 最终重建计划

> **日期**: 2026-02-25
> **状态**: 已批准
> **前置**: [架构审计报告](../audits/2026-02-25-architecture-audit.md)
> **取代**: [Rebuild Plan](2026-02-25-vibe-rebuild-v2.md) + [Governance Design](2026-02-25-vibe-skills-governance-design.md)

---

## 1. 重建目标

一句话：**用 ≤1,200 行 Zsh 代码重建 Vibe Center 的全部核心功能，治理规则内嵌于 CLAUDE.md 而非 shell 技能。**

### 1.1 核心功能清单（完整枚举）

| # | 功能 | 命令 | 验收标准 | 行数预算 |
|---|------|------|----------|---------|
| 1 | CLI 入口 | `vibe <cmd>` | 分发到子命令，未知命令显示帮助 | 50 |
| 2 | 环境检测 | `vibe check` | 检测 claude/opencode/codex/git/gh/tmux/jq 是否安装，报告版本 | 80 |
| 3 | 工具安装 | `vibe tool` | 安装/更新 claude, opencode, codex | 120 |
| 4 | 密钥管理 | `vibe keys` | 从 keys.env 读写 API key，模板生成 | 60 |
| 5 | Alias 加载 | `vibe alias` | 加载 worktree/tmux/claude/git/openspec alias | 30 |
| 6 | 工作流 | `vibe flow start/review/pr/done` | worktree 创建→checklist→PR 生成→清理 | 180 |
| 7 | 共享库 | (内部) | log, validate_path, confirm_action | 60 |
| 8 | 配置加载 | (内部) | VIBE_ROOT 检测, keys.env 加载 | 40 |
| **合计** | | | | **620** |

剩余预算（~580 行）留给 alias 定义文件（从 V1 直接迁移精简版）和未预见需求。

### 1.2 不做清单（硬边界）

从 V1 删除且 V2 不重建：
- ❌ NLP 意图路由 / 聊天路由
- ❌ 断路器 / 指数退避重试
- ❌ TTL 缓存系统
- ❌ i18n 多语支持
- ❌ 自定义测试框架（用 bats-core 或简单 assert）
- ❌ 邮箱验证
- ❌ 配置迁移系统
- ❌ 流状态机（JSON state 管理）
- ❌ Shell 级别注入防护（我们不是 Web 服务器）
- ❌ 独立的治理 shell 技能系统（governance.yaml, scope-gate 等作为 shell 工具）

### 1.3 治理规则（内嵌于文档，不建 shell 工具）

治理设计的**认知洞察**值得保留，但实现方式从 "shell 技能" 降级为 "CLAUDE.md 指令"：

| 治理概念 | 原计划实现 | 最终实现 |
|---------|-----------|---------|
| Scope Gate | shell 技能 + 硬挡 | CLAUDE.md "不做清单" + Agent 自检指令 |
| LOC Ceiling | governance.yaml 配置 | CLAUDE.md 写明 "lib/+bin/ ≤1,200 行" |
| Boundary Check | shell 扫描工具 | `wc -l` 一行命令 + PR 时人工确认 |
| Rules Enforcer | shell 检查器 | ShellCheck + CLAUDE.md 编码标准 |
| Drift Detector | shell 扫描工具 | 月度人工 review（5 分钟看一遍） |
| PR 合规门 | 合规标签系统 | PR description 模板里列 checklist |

**原则**：治理的目的是约束 scope creep。10 行 Markdown 规则比 500 行 shell 治理工具更有效——因为 Agent 读 CLAUDE.md，不跑 shell 脚本来自检。

---

## 2. 从 V1 提取的资产

### 2.1 直接复用（复制到 V2 后精简）

| 文件 | V1 行数 | V2 目标行数 | 操作 |
|------|---------|------------|------|
| `config/aliases/worktree.sh` | 375 | ~200 | 删除死函数，保留 wtnew/wtrm/vup |
| `config/aliases/tmux.sh` | 175 | ~100 | 保留核心 tmux session 管理 |
| `config/aliases/claude.sh` | 53 | ~40 | 原样迁移 |
| `config/aliases/git.sh` | 24 | ~24 | 原样迁移 |
| `config/aliases/openspec.sh` | 23 | ~23 | 原样迁移 |
| `config/aliases/opencode.sh` | 20 | ~20 | 原样迁移 |
| `config/aliases/vibe.sh` | 68 | ~40 | 精简后迁移 |
| `SOUL.md` | 201 (v2) | 原样 | 已在 V2 |

### 2.2 提取核心逻辑

| 来源 | 提取内容 | 目标行数 |
|------|---------|---------|
| `lib/utils.sh:L1-80` | log_info/warn/error/step/success + 颜色常量 | ~30 |
| `lib/utils.sh:L108-145` | validate_path()（精简版，删除过度检查） | ~15 |
| `lib/flow.sh:L22-32` | detect_current_feature() | ~10 |
| `lib/keys_manager.sh` | 密钥读写核心逻辑 | ~50 |
| `install/install-claude.sh` | Claude 安装逻辑 | ~40 |
| `install/install-opencode.sh` | OpenCode 安装逻辑 | ~40 |

### 2.3 设计决策复用

- ✅ Worktree 隔离模式 (`wt-<agent>-<feature>`)
- ✅ `vibe_main_guard` 防护主分支
- ✅ `keys.env` + `.gitignore` 密钥管理
- ✅ `vibe flow` 生命周期概念 (start→review→pr→done)
- ✅ bin/ dispatcher + lib/ 模块分离模式

### 2.4 必须丢弃

| 模块 | 行数 | 原因 |
|------|------|------|
| `lib/error_handling.sh` | 185 | 断路器模式，不适用 |
| `lib/cache.sh` | 197 | 不需要缓存 |
| `lib/email_validation.sh` | 57 | 不需要邮箱验证 |
| `lib/i18n.sh` | 171 | 不需要多语支持 |
| `lib/chat_router.sh` | 278 | NLP 路由，CLI 用 subcommand |
| `lib/testing.sh` | 290 | 用 bats-core 替代 |
| `lib/config_loader.sh` | 226 | 与 config.sh 重复 |
| `lib/config_migration.sh` | 32 | 无人调用 |
| `lib/flow_state.sh` | 260 | JSON 状态机，不需要 |
| `lib/config_init.sh` | 155 | 合并入 config.sh |
| `lib/vibe_dir_template.sh` | 178 | 简化为 mkdir -p |
| `lib/agents.sh` | 101 | 大部分死代码 |
| `lib/skill_manager.sh` | 245 | 过度建设 |
| `lib/mcp_manager.sh` | 234 | 可简化到 20 行 |
| `lib/tool_manager.sh` | 315 | 合并入 tool |
| **合计丢弃** | **~2,924** | |

---

## 3. V2 目标文件结构

```
v2/
├── SOUL.md                      # 宪法（已有）
├── CLAUDE.md                    # 项目上下文 + 内嵌治理规则（重写）
├── AGENTS.md                    # Agent 入口（新建）
├── VERSION                      # 版本号
├── bin/
│   └── vibe                     # CLI 入口 dispatcher (~50 行)
├── lib/
│   ├── utils.sh                 # 日志 + validate_path (~60 行)
│   ├── config.sh                # VIBE_ROOT + keys.env 加载 (~40 行)
│   ├── check.sh                 # 环境检测 (~80 行)
│   ├── tool.sh                 # 工具安装 (~120 行)
│   ├── keys.sh                  # 密钥管理 (~60 行)
│   └── flow.sh                  # 工作流核心 (~180 行)
├── config/
│   ├── aliases.sh               # Alias 加载入口 (~30 行)
│   ├── keys.template.env        # API key 模板
│   └── aliases/
│       ├── worktree.sh          # wtnew/wtrm/vup (~200 行)
│       ├── tmux.sh              # tmux session (~100 行)
│       ├── claude.sh            # Claude 快捷键 (~40 行)
│       ├── git.sh               # Git alias (~24 行)
│       ├── openspec.sh          # OpenSpec alias (~23 行)
│       └── opencode.sh          # OpenCode alias (~20 行)
├── .agent/
│   ├── README.md                # Agent 工作空间（已有）
│   ├── skills/
│   │   ├── save/SKILL.md        # 上下文保存技能
│   │   ├── continue/SKILL.md    # 上下文恢复技能
│   │   ├── check/SKILL.md       # 健康检查技能
│   │   └── architecture-audit/SKILL.md  # 架构审计技能
│   ├── workflows/               # 核心工作流（已有 opsx-*）
│   ├── context/
│   │   ├── memory.md            # 长期记忆
│   │   └── task.md              # 任务追踪
│   └── rules/
│       ├── coding-standards.md  # 编码标准
│       └── architecture.md      # 架构规则
└── docs/
    ├── CHEATSHEET.md            # 快速参考
    └── audits/                  # 审计历史
```

**预估总量**：
- `lib/` + `bin/`: ~620 行（核心代码）
- `config/aliases/`: ~437 行（alias 定义）
- **总计**: ~1,057 行 （在 1,200 行预算内）

---

## 4. 实施任务（按依赖顺序）

### Phase 1: 基础骨架（预计 30 分钟）

> 目标：V2 能跑起来，`vibe help` / `vibe check` 能工作

**Task 1.1**: 重写 `v2/lib/utils.sh`
- 从 V1 提取 log 函数 + validate_path（精简版）
- 目标：~60 行
- 验证：`source v2/lib/utils.sh && log_info "test" && log_error "test"`

**Task 1.2**: 重写 `v2/lib/config.sh`
- VIBE_ROOT 检测（简化：只用脚本位置推导，不要 5 级 fallback）
- keys.env 加载
- 目标：~40 行
- 验证：`source v2/lib/config.sh && echo $VIBE_ROOT`

**Task 1.3**: 重写 `v2/bin/vibe` dispatcher
- 分发到 check/tool/keys/flow/alias/help
- 目标：~50 行
- 验证：`v2/bin/vibe help` 输出命令列表

**Task 1.4**: 实现 `v2/lib/check.sh`
- 检测 claude/opencode/codex/git/gh/tmux/jq
- 报告版本号
- 目标：~80 行
- 验证：`v2/bin/vibe check` 输出环境状态

### Phase 2: 核心功能（预计 1 小时）

> 目标：密钥管理 + 工具安装能工作

**Task 2.1**: 实现 `v2/lib/keys.sh`
- 从 V1 keys_manager.sh 提取核心：读/写/列出 API key
- 目标：~60 行
- 验证：`v2/bin/vibe keys list` 显示当前配置的 key

**Task 2.2**: 实现 `v2/lib/tool.sh`
- 从 V1 install 脚本提取：安装 claude, opencode, codex
- 合并三个脚本的共同逻辑
- 目标：~120 行
- 验证：`v2/bin/vibe tool` 显示可安装工具列表

**Task 2.3**: 创建 `v2/config/keys.template.env`
- 从 V1 复制模板
- 验证：文件存在且含占位符

### Phase 3: 工作流（预计 1 小时）

> 目标：`vibe flow` 全生命周期能工作

**Task 3.1**: 重写 `v2/lib/flow.sh`
- `flow start <feature>`: 创建 worktree（调用 wtnew 或内联实现）
- `flow review`: 输出 checklist + 可选 lazygit
- `flow pr`: 生成 PR description 模板 + 调用 `gh pr create`
- `flow done`: 清理 worktree + 保存上下文
- 目标：~180 行
- 验证：`v2/bin/vibe flow start test-feature` 创建 worktree

### Phase 4: Alias 迁移（预计 30 分钟）

> 目标：所有核心 alias 可用

**Task 4.1**: 迁移 `config/aliases/` 到 V2
- 从 V1 复制，删除死代码和冗余函数
- worktree.sh 从 375→~200 行
- tmux.sh 从 175→~100 行
- 其余基本原样迁移
- 验证：`source v2/config/aliases.sh && type wtnew`

**Task 4.2**: 创建 `v2/config/aliases.sh` 加载入口
- 加载所有子模块
- 目标：~30 行
- 验证：`source v2/config/aliases.sh` 无报错

### Phase 5: 文档和 Agent 资产（预计 30 分钟）

> 目标：CLAUDE.md 含内嵌治理规则，.agent/ 可用

**Task 5.1**: 重写 `v2/CLAUDE.md`
- 包含内嵌治理规则（替代 governance.yaml）：
  - LOC Ceiling: lib/+bin/ ≤1,200 行
  - 不做清单（Scope Gate 替代）
  - PR Checklist 模板（PR 合规门替代）
  - 单文件 ≤200 行规则
- 验证：CLAUDE.md 含 "LOC Ceiling" 和 "不做清单" 段落

**Task 5.2**: 迁移 `.agent/` 核心内容
- skills: save, continue, check, architecture-audit（已有）
- rules: coding-standards.md, architecture.md
- context: memory.md, task.md
- 验证：目录结构完整

**Task 5.3**: 创建 `v2/AGENTS.md`
- Agent 入口文件
- 验证：链接到 CLAUDE.md 和 .agent/README.md

---

## 5. 验收标准

### 功能验收（全部必须通过）

```bash
# 1. CLI 入口
v2/bin/vibe help              # 显示命令列表
v2/bin/vibe check             # 显示环境状态

# 2. 密钥管理
v2/bin/vibe keys list         # 列出 API key 状态

# 3. 工具安装
v2/bin/vibe tool             # 显示工具状态

# 4. 工作流（核心验收）
v2/bin/vibe flow start test   # 创建 worktree
v2/bin/vibe flow review       # 输出 checklist
v2/bin/vibe flow pr           # 生成 PR 模板
v2/bin/vibe flow done         # 清理

# 5. Alias
source v2/config/aliases.sh   # 加载无报错
type wtnew                    # wtnew 函数可用
type vup                      # vup 函数可用
```

### 质量验收

```bash
# LOC 检查
find v2/lib/ v2/bin/ -name '*.sh' -o -name 'vibe' | xargs wc -l
# 预期: total ≤ 1,200 行

# Alias 检查
find v2/config/ -name '*.sh' | xargs wc -l
# 预期: total ≤ 500 行

# 无文件超 200 行
find v2/lib/ v2/bin/ -name '*.sh' | xargs wc -l | awk '$1 > 200 {print "OVER:", $0}'
# 预期: 无输出

# 死函数检查
grep -hE '^[a-z_]+\(\)' v2/lib/*.sh | sed 's/().*//' | sort -u | while read fn; do
  count=$(grep -rl "$fn" v2/lib/*.sh v2/bin/* v2/config/*.sh v2/config/aliases/*.sh 2>/dev/null | wc -l)
  [ "$count" -le 1 ] && echo "DEAD: $fn"
done
# 预期: 0 个死函数（alias 文件内的函数除外）

# ShellCheck
shellcheck v2/lib/*.sh v2/bin/vibe
# 预期: 无 error
```

---

## 6. 防止复发的约束（写入 CLAUDE.md）

以下规则在 V2 CLAUDE.md 中以 **HARD RULES** 标注，Agent 必须遵守：

1. **LOC Ceiling**: `lib/` + `bin/` 总行数 ≤ 1,200。超出即触发审计。
2. **单文件上限**: 任何 `.sh` 文件 ≤ 200 行。超出必须拆分。
3. **零死代码**: 每个函数必须有 ≥1 个调用者。定义即死亡的函数禁止提交。
4. **不做清单**: 不实现 NLP、缓存、i18n、断路器、自定义测试框架、JSON 状态机、配置迁移。
5. **工具优先**: 需要测试用 bats-core，需要 JSON 用 jq 命令行，需要 HTTP 用 curl。不造轮子。
6. **新功能验证**: 增加任何功能前问 "SOUL.md 说这该不该做"。如果答案不是明确的 YES，不做。
7. **PR 必带 LOC 差异**: 每个 PR description 必须包含 `wc -l` 前后对比。

---

## 7. V1→V2 过渡策略

1. **V2 在 `v2/` 子目录内开发**（已在进行）
2. **V2 功能验收全部通过后**：
   - V1 代码移入 `v1-archive/`（保留 git 历史参考）
   - V2 内容提升到根目录
   - 更新 PATH 和 alias source 路径
3. **过渡期**：V1 和 V2 可并存，bin/vibe 指向 V2

---

## 8. 关于治理设计的处置

[Skills 治理体系设计](2026-02-25-vibe-skills-governance-design.md) 中的认知洞察已被吸收到本计划：

| 原计划内容 | 吸收方式 | 位置 |
|-----------|---------|------|
| Scope Gate 概念 | "不做清单" 写入 CLAUDE.md | §6 规则 4+6 |
| LOC 预算概念 | "LOC Ceiling" 写入 CLAUDE.md | §6 规则 1 |
| Boundary Check 扫描 | 验收标准的一部分 | §5 质量验收 |
| PR 合规门 | PR description checklist | §6 规则 7 |
| 技能分类体系 | 保留现有 4 技能，不新增 | §3 .agent/skills/ |

**不实施的部分**：
- governance.yaml 配置文件
- scope-gate / boundary-check / rules-enforcer / drift-detector 作为 shell 技能
- PR 合规标签系统
- Claude Code hooks 集成
- 4 周技能开发路线图

**原因**：治理的目的是防 scope creep。用 500 行 shell 工具来防 scope creep 本身就是 scope creep。

---

## 9. 时间预估

| Phase | 内容 | 预估时间 |
|-------|------|---------|
| 1 | 基础骨架 | 30 分钟 |
| 2 | 核心功能 | 1 小时 |
| 3 | 工作流 | 1 小时 |
| 4 | Alias 迁移 | 30 分钟 |
| 5 | 文档 + Agent | 30 分钟 |
| **总计** | | **~3.5 小时** |

---

*此计划整合了架构审计的诊断、重建计划的方向、治理设计的认知洞察，删除了一切过度建设。执行时从 Phase 1 开始，每完成一个 Phase 验证一次，不跳步。*
