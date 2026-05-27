# Claude Code Hooks

这个目录包含项目级 Claude Code hooks，用于增强安全性和防止误操作。

## Hooks 清单

### 1. block-destructive.sh

**触发器**: `PreToolUse → Bash`

**作用**: 阻止破坏性命令执行

**保护范围**:
- ✅ `rm -rf /`、`rm -rf ~`、`rm -rf $HOME`（系统级目录）
- ✅ `rm -rf .venv`、`rm -rf .node_modules`、`rm -rf .env`（虚拟环境）
- ✅ `rm -rf venv`、`rm -rf node_modules`（无点前缀版本）
- ✅ `rm -rf path/to/.venv`（路径中的虚拟环境）
- ✅ `git commit --no-verify`（绕过质量门禁）
- ✅ `DROP TABLE`、`TRUNCATE DATABASE`（数据库破坏）
- ✅ `vibe3 task resume -y`（无标签任务恢复）

**安全命令**:
- ✅ `rm -rf /tmp/*`（临时文件）
- ✅ `rm -rf build/*`（构建产物）
- ✅ 其他非保护目录

### 2. protect-files.sh

**触发器**: `PreToolUse → Edit|Write`

**作用**: 防止编辑敏感文件

**保护范围**:
- `.env`、`.env.local`、`.env.production`（环境变量）
- `secrets/`、`credentials/`（密钥目录）
- `.ssh/`、`id_rsa`、`id_ed25519`（SSH 密钥）

**例外**: 允许编辑 `*.template.*`、`*.example*` 模板文件

**行为**: 阻塞操作（exit 2）

### 3. detect-secrets.sh

**触发器**: `PreToolUse → Edit|Write`

**作用**: 检测硬编码密钥（只警告不阻塞）

**检测模式**:
- `API_KEY="..."`（16+ 字符）
- `SECRET=...`
- `TOKEN="..."`
- `PASSWORD='...'`
- `PRIVATE_KEY=...`

**例外**:
- ✅ 跳过测试文件（`*.test.*`、`*.spec.*`）
- ✅ 跳过示例文件（`*.example*`）

**行为**: 警告但不阻塞（exit 0）

## 测试

测试 hook 是否正常工作：

```bash
# 应该被阻止
echo '{"tool_input": {"command": "rm -rf .venv"}}' | bash ~/.claude/hooks/block-destructive.sh

# 应该被允许
echo '{"tool_input": {"command": "rm -rf /tmp/test"}}' | bash ~/.claude/hooks/block-destructive.sh
```

## 更新日志

### 2026-05-27
- ✅ 添加 `.venv`、`node_modules`、`env`、`virtualenv` 保护
- ✅ 添加无点前缀版本（`venv`、`node_modules`）保护
- ✅ 注册到全局 settings.json
- ✅ 测试通过所有保护场景

## 参考资料

- [Claude Code Hooks 官方文档](https://docs.anthropic.com/claude-code/hooks)
- [项目安全规范](../../docs/standards/security-standards.md)
