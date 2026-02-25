# Vibe Center 2.0 — 开发指南

## 1. 项目双重身份

本项目包含两个维度的工作（详见 [CLAUDE.md](CLAUDE.md)）：

| 维度 | 内容 | 位置 | 治理标准 |
|------|------|------|----------|
| **Zsh CLI** | Shell 脚本，环境编排 | `bin/`, `lib/` | LOC ≤ 1,200，单文件 ≤ 200 行 |
| **Vibe Coding Framework** | Agent 行为控制技能 | `skills/` | 清晰度、正确性、有效性 |

> Shell 代码严格控制体积；技能是 Markdown 提示词，评估标准不同。

## 2. 开发环境搭建

### 2.1 前置要求
- macOS / Linux
- zsh (默认 Shell)
- git

### 2.2 Setup（技能 symlink）

`.agent/skills/` 目录已 gitignore，开发者需要自行创建 symlinks：

```bash
# 1. 链接项目自有技能（skills/ → .agent/skills/）
cd .agent/skills
for skill in ../../skills/vibe-*/; do
  name=$(basename "$skill")
  ln -sf "$skill" "$name"
done

# 2. 链接 OpenSpec 技能（.github/skills/ → .agent/skills/）
for skill in ../../.github/skills/openspec-*/; do
  name=$(basename "$skill")
  ln -sf "$skill" "$name"
done

# 3. 链接 Superpowers（可选，需先安装 superpowers）
# 参见 https://github.com/jomifred/superpowers
for skill in ~/.agents/skills/*/; do
  name=$(basename "$skill")
  [ ! -e "$name" ] && ln -sf "$skill" "$name"
done
```

对于 Trae 用户，在 `.trae/skills/` 做同样操作。

### 2.3 验证
```bash
bin/vibe check    # 环境诊断
ls .agent/skills/ # 应看到 symlinks
```

## 3. 外部依赖

本项目使用以下社区技能（**不 vendor 到仓库中**）：

| 依赖 | 用途 | 安装方式 |
|------|------|----------|
| [Superpowers](https://github.com/jomifred/superpowers) | 通用 agent 技能（TDD、调试、头脑风暴等） | 按其文档安装到 `~/.agents/skills/` |
| [OpenSpec](https://github.com/OpenSpec) | 结构化变更管理工作流 | 按其文档安装，symlink 到 `.github/skills/` |
| [bats-core](https://github.com/bats-core/bats-core) | Shell 测试框架 | `brew install bats-core` |

## 4. 目录结构

```
bin/vibe               # CLI 入口（~60 行）
lib/                   # Shell 核心逻辑（受 LOC 上限约束）
config/                # 别名、密钥模板
skills/                # 🟢 Vibe 自有技能（tracked，规范源）
.agent/                # Agent 工作区
  governance.yaml      # 治理配置
  workflows/           # 工作流定义
  rules/               # 架构和编码规则
  context/             # Agent 记忆和任务状态
  skills/              # ⚠️ GITIGNORED — 纯 symlinks
.github/skills/        # ⚠️ GITIGNORED — OpenSpec 技能 symlinks
docs/                  # 文档、计划、审计
tests/                 # bats-core 测试
```

## 5. V1 → V2 迁移说明

V2 重构（2025-02）将 shell 代码从 14,293 行精简至 ~644 行。
以下 V1 功能尚未移植，列入后续计划：

- `vibe alias list` — 列出自定义 shell 命令
- `vibe doctor` — 更详细的环境诊断（当前用 `vibe check` 替代）
- 配置文件管理 (opencode.json, config.toml)

## 6. 常用命令

```bash
bin/vibe check                    # 环境诊断
bin/vibe flow start <branch>      # 开始新功能
bin/vibe flow review              # 触发代码审查
bin/vibe flow pr                  # 创建 PR
bin/vibe flow done                # 完成工作
bin/vibe keys list                # 列出 API 密钥
bin/vibe tool                    # 安装 AI 工具
source config/aliases.sh          # 加载别名
```

## 7. LOC 检查

每次 PR 前确认 shell 代码总量：
```bash
find lib/ bin/ -name '*.sh' -o -name 'vibe' | xargs wc -l  # ≤ 1,200
```
