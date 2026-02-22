# vibe-architecture

## Summary
Vibe Coding 环境架构从分散配置重构为工程化模块化架构，支持双轨交互（结构化命令 + 自然语言）。

## Key Decisions
1. **统一清单模式**: 采用 `vibe.yaml` 作为单一配置入口，支持嵌套结构和列表
2. **密钥组切换**: 使用符号链接 `keys/current` 指向当前激活的密钥组，支持多提供商
3. **目录结构**: `~/.vibe/` 下分 `keys/`, `tools/`, `mcp/`, `skills/`, `cache/`
4. **命令分发器**: Git-style 子命令模式 (`vibe keys`, `vibe tool`, `vibe mcp`, `vibe skill`)
5. **自然语言入口**: `vibe chat` 作为智能入口，先尝试意图路由再传递给 AI

## Problems & Solutions

### YAML 解析中数组键带引号问题
- **Issue**: 使用 `"${section}_${key}"` 格式存储时，键被添加引号导致无法正确访问
- **Solution**: 改用 `${current_section}_${key}` (不带引号) 的格式进行数组索引
- **Lesson**: zsh 数组索引不需要额外引号，引号会被当作键的一部分

### zsh 算术表达式返回值陷阱
- **Issue**: `(( key_count++ ))` 当值为 0 时返回非零退出码，触发 `set -e` 错误
- **Solution**: 使用 `((key_count += 1))` 或 `(( ++key_count ))` 替代
- **Lesson**: zsh 中 `((expr))` 在表达式求值为 0 时返回 false (退出码 1)

### macOS sed 兼容性问题
- **Issue**: macOS 的 sed 不支持 GNU sed 的 `-i` 不带备份后缀
- **Solution**: 使用 `sed -i '' ... 2>/dev/null || sed -i ...` 兼容两种版本
- **Lesson**: 便携性考虑：先尝试 macOS 语法，失败后尝试 GNU 语法

### readlink -f 在 macOS 不可用
- **Issue**: `readlink -f` 是 GNU 扩展，macOS 不支持
- **Solution**: 使用 `readlink` (不带 -f) 配合 `basename` 手动处理
- **Lesson**: macOS 兼容性需要避免 GNU 特有的扩展选项

## Related Tasks
- [x] [vibe-arch-20260221-001] 创建目录结构模板 (vibe_dir_template.sh)
- [x] [vibe-arch-20260221-002] 实现 vibe.yaml 解析器
- [x] [vibe-arch-20260221-003] 实现 vibe keys 子命令
- [x] [vibe-arch-20260221-004] 更新 bin/vibe 调度器
- [x] [vibe-arch-20260221-005] 实现 vibe tool 子命令
- [x] [vibe-arch-20260221-006] 实现 vibe mcp/skill 子命令
- [x] [vibe-arch-20260221-007] 实现 vibe init/export
- [x] [vibe-arch-20260221-008] 实现 vibe doctor 环境检查
- [x] [vibe-arch-20260221-009] 实现 vibe chat 意图识别
- [x] [vibe-arch-20260221-010] 端到端测试

## References
- `lib/vibe_dir_template.sh` - 目录结构生成器
- `lib/config.sh` - YAML 解析器扩展
- `lib/keys_manager.sh` - 密钥管理
- `lib/tool_manager.sh` - 工具管理
- `lib/mcp_manager.sh` - MCP 服务器管理
- `lib/skill_manager.sh` - 技能管理
- `lib/env_manager.sh` - 环境管理
- `lib/chat_router.sh` - 自然语言意图路由
- `bin/vibe-keys`, `bin/vibe-tool`, `bin/vibe-mcp`, `bin/vibe-skill` - 命令入口
- `tests/test_vibe_keys.sh`, `tests/test_vibe_chat_intent.sh` - 测试脚本

---
Created: 2026-02-22
Last Updated: 2026-02-22
Sessions: 2

