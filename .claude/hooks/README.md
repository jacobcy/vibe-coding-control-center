# Claude/Codex Hooks

本项目提供一套共享 hook 脚本，供 Claude Code 与 Codex 使用，用于增强安全性和防止误操作。

## 安装

`scripts/install.sh` 会同步以下内容：

- hook 脚本到 `~/.claude/hooks/`（Claude 使用）
- hook 脚本到 `~/.codex/hooks/`（Codex 使用）
- 仓库模板 `.claude/hooks/codex-hooks.json` 同步到 `~/.codex/hooks.json`

如果需要手动更新 hooks：

```bash
# Claude
cp -R .claude/hooks/. ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh

# Codex
cp -R .claude/hooks/. ~/.codex/hooks/
chmod +x ~/.codex/hooks/*.sh
cp .claude/hooks/codex-hooks.json ~/.codex/hooks.json
```

## Hooks 说明

### protect-files.sh

**作用**：防止编辑敏感文件（密钥、证书等）

**保护范围**：
- `.env` 系列文件（`.env.local`, `.env.production`, `.env.staging`）
- `secrets/` 目录
- `credentials` 相关文件
- `.ssh/` 目录下的私钥文件（`id_rsa`, `id_ed25519`）

**例外**：
- ✅ 允许编辑模板文件（`*.template.*`, `*.example*`）
- ✅ 允许编辑包含 `template` 字样的文件

**示例**：
- ❌ 阻止：编辑 `config/.env`（真实密钥文件）
- ✅ 允许：编辑 `config/keys.template.env`（模板文件）

### detect-secrets.sh

**作用**：检测硬编码的密钥（警告但不阻塞）

**检测模式**：
- `API_KEY="..."`（16+ 字符）
- `SECRET=...`
- `TOKEN="..."`
- `PASSWORD='...'`
- `PRIVATE_KEY=...`

**例外**：
- ✅ 跳过测试文件（`*.test.*`, `*.spec.*`）
- ✅ 跳过示例文件（`*.example*`）

**行为**：发出警告，但不阻塞操作（exit 0）

**当前状态**：Codex 默认已接入 `Write|Edit` hook 链。

### block-destructive.sh

**作用**：阻止破坏性命令执行

**阻止范围**：
- `rm -rf /` 或 `rm -rf ~`
- `rm -rf ... /` 或 `rm -rf ... ~`
- `git push -f` 或 `git push --force`
- `DROP TABLE` 或 `TRUNCATE TABLE`

**行为**：阻塞操作（exit 2）

### rtk-rewrite.sh

**作用**：在执行 Bash 工具前，尝试将命令重写为 `rtk` 等价命令以节省 token。

**依赖**：
- `jq`
- `rtk >= 0.23.0`

**行为**：
- 找到可重写命令时，返回更新后的命令
- 未找到等价命令时直接放行
- 依赖缺失时仅警告，不阻塞操作

### SessionStart hook

**作用**：在 `compact` 事件后打印当前项目的分支和最近一次提交，帮助恢复上下文。

**行为**：只输出提示信息，不阻塞操作。

## 自定义配置

### 添加新的保护模式

编辑 `protect-files.sh`，修改 `PROTECTED` 数组：

```bash
PROTECTED=(".env" "secrets/" "credentials")
# 添加新的保护模式
PROTECTED+=("my-sensitive-dir/")
```

### 调整检测规则

编辑 `detect-secrets.sh`，修改 grep 正则：

```bash
if echo "$NEW_TEXT" | grep -qiE '(API_KEY|SECRET|TOKEN)...\s*[=:]\s*["\x27]?[A-Za-z0-9_\-]{16,}'; then
```

### 禁用特定 hook

Claude:

```bash
rm ~/.claude/hooks/protect-files.sh
```

Codex:

推荐直接编辑 `~/.codex/hooks.json`，移除对应条目；仅删除 `.sh` 文件会留下失效配置。

```bash
$EDITOR ~/.codex/hooks.json
```

## 开发新 Hook

### Hook 规范

1. **输入**：通过 stdin 接收 JSON 格式的工具调用信息
2. **输出**：
   - `exit 0`：允许操作
   - `exit 2`：阻塞操作（打印错误信息到 stderr）
3. **格式**：使用 `jq` 解析 JSON 输入

### 示例 Hook 结构

```bash
#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE" ]; then
  exit 0
fi

# 你的检查逻辑
if [[ "$FILE" == *sensitive* ]]; then
  echo "[security] BLOCKED: $FILE" >&2
  exit 2
fi

exit 0
```

### 测试 Hook

手动测试 hook 是否正常工作：

```bash
# 测试 protect-files.sh
echo '{"tool_input":{"file_path":"config/.env"}}' | ~/.claude/hooks/protect-files.sh
# 应返回 exit 2 并打印错误信息

echo '{"tool_input":{"file_path":"config/keys.template.env"}}' | ~/.claude/hooks/protect-files.sh
# 应返回 exit 0（允许）
```

```bash
# 测试 Codex protect-files.sh
echo '{"tool_input":{"file_path":"config/.env"}}' | ~/.codex/hooks/protect-files.sh
# 应返回 exit 2 并打印错误信息
```

## 相关文档

- [Claude Code Hooks 官方文档](https://docs.anthropic.com/claude-code/hooks)
- Codex hook 模板：`.claude/hooks/codex-hooks.json`
- 项目配置文件：`../config/settings.yaml`
- 密钥模板：`../config/keys.template.env`
