# Claude Code Hooks

本项目提供 Claude Code hooks，用于增强安全性，阻止真正危险的系统级命令。

## 配置

Hooks 自动通过项目级 `.claude/settings.json` 启用，无需手动安装。

如需禁用特定 hook，编辑 `.claude/settings.json`，移除对应的 hook 配置。

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

### block-destructive.sh

**作用**：阻止破坏性系统命令和绕过质量检查的操作

**阻止范围**：
- `rm -rf /` 或 `rm -rf ~`
- `rm -rf ... /` 或 `rm -rf ... ~`
- `git commit --no-verify`（禁止绕过 pre-commit hooks）
- `DROP TABLE` 或 `TRUNCATE TABLE`

**行为**：阻塞操作（exit 2）
