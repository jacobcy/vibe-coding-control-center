# Copilot Onboarding — Vibe Center 2.0

## 快速认知
- 仓库是 AI 协作编排工具，存在 **V2 Shell**（`bin/`, `lib/`, `tests/vibe2/`）与 **V3 Python**（`src/vibe3/`, `tests/vibe3/`）双实现。配置与规则集中在 `.agent/`（规则）、`skills/`（技能）、`.git/vibe/`（共享状态真源，勿直接改）。
- AI 工作入口与硬规则：先读 `AGENTS.md` → `CLAUDE.md` → `.agent/rules/*`。文档职责见 `SOUL.md`/`STRUCTURE.md`，术语以 `docs/standards/glossary.md` 为准。
- CI（`.github/workflows/ci.yml`）在 PR 上运行：Shell LOC 上限检查、Python LOC 上限、Shell 双层 lint、bats `tests/vibe2/`、`uv run ruff check src`、`uv run black --check src tests/vibe3`、`uv run mypy src`、`uv run pytest tests/vibe3 -v`。

## 环境与依赖（必备）
- 系统依赖：`zsh`、`bats`、`shellcheck`。在全新 runner 上 `zsh`/`bats` 缺失会导致 `scripts/hooks/lint.sh` 或 bats 直接报 127，需先执行 `sudo apt-get install -y zsh bats shellcheck`。
- Python 工具链：**必须用 uv**。若官方安装脚本（`curl https://astral.sh/uv/install.sh | sh`）因 DNS 失败（遇到 “Could not resolve host: astral.sh”），可用 `pip install uv` 作为替代。同步依赖：`uv sync --dev`（使用 Python 3.12，创建 `.venv`）。
- 运行 CLI：Shell 用 `bin/vibe ...`；Python 用 `uv run python src/vibe3/cli.py ...`。禁止直接用 `python`/`pip` 触达 V3。

## 推荐构建 / 验证顺序
1) **Shell 双层 lint**：`bash scripts/hooks/lint.sh`（需 zsh、shellcheck）。当前仅有若干 shellcheck warning，0 error。
2) **Shell 测试（bats）**：`bats --recursive tests/vibe2`。在未安装全局 `vibe` / 未准备模拟资产时会大量失败（127），尤其安装类用例把 `VIBE_ROOT` 解析到 `tests/` 下缺少 `bin/`/`scripts/`。若需运行，请确保：
   - PATH 中可找到 `bin/vibe`（可 `export PATH="$PWD/bin:$PATH"` 或先 `scripts/install.sh` 完成全局安装）；
   - 相关脚本依赖的工具（如 `npx`、`openspec`）已可执行或被 stub。
3) **Python 质量栈**（在 `uv sync --dev` 后）：
   - `uv run ruff check src`
   - `uv run black --check src tests/vibe3`
   - `uv run mypy src`
   - `uv run pytest tests/vibe3 -q`（~52s，当前通过；有 PytestReturnNotNone 与 fork Deprecation 警告但不阻塞）

## 目录速览
- `bin/vibe`：Shell CLI 入口；`lib/`：核心逻辑；`config/`：别名与密钥模板；`scripts/`：lint/metrics/install 等工具。
- `src/vibe3/`：Python V3 代码；`tests/vibe3/`：pytest 套件；`tests/vibe2/`：bats 套件。
- `.agent/`：规则、workflow、记忆；`skills/`：项目自有技能；`.github/workflows/`：CI；`docs/`：规范与计划。

## 常见陷阱与绕过
- 缺少 `zsh` / `bats` 会让 lint、bats 直接失败；先安装系统包再跑脚本。
- uv 安装脚本若因网络受阻，改用 `pip install uv`；随后再 `uv sync --dev`。
- bats 集成测试默认将 `VIBE_ROOT` 设为 `tests/`，若未准备对应资源会出现 `Command not found` 或找不到 `bin/`/`scripts/` 的错误；在需要验证时先把仓库 `bin/` 加入 PATH 或跑 `scripts/install.sh` 以提供这些资产。
- Python 侧所有命令都走 `uv run ...`；不要用裸 `python`/`pip`，否则不符合项目标准与 CI 行为。

## 行为指引
- 先信任本说明与项目文档；仅当信息缺失或与现场不符时再额外搜索。
- 回答/文档默认中文，避免非 ASCII 符号（禁止框线字符）。最小改动、保持既有格式；涉及共享状态时通过正式命令（`vibe flow/task/...`），不要直接改 `.git/vibe/`。
