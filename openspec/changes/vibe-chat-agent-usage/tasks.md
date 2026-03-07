# Implementation Tasks: Vibe Chat Agent Usage

## 1. 设计 Agent 配置格式

- [ ] 1.1 设计 `.agent/agents.yml` schema
- [ ] 1.2 确定需要记录的字段（name, install, commands, examples）
- [ ] 1.3 考虑扩展性（支持自定义 agent）

## 2. 创建 Agent 配置文件

- [ ] 2.1 创建 `.agent/agents.yml`
- [ ] 2.2 添加 codex 配置
- [ ] 2.3 添加 copilot 配置
- [ ] 2.4 添加其他常用 agent（如 cursor, continue）

## 3. 实现 Shell 层命令

- [ ] 3.1 创建 `lib/chat.sh`
- [ ] 3.2 实现 `vibe_chat()` 主函数
- [ ] 3.3 实现 `_chat_list_agents()` - 列出所有 agent
- [ ] 3.4 实现 `_chat_show_usage()` - 显示使用指南
- [ ] 3.5 实现 `_chat_check_installed()` - 检测是否安装
- [ ] 3.6 更新 `bin/vibe` 添加 `chat` 子命令

## 4. 增强 vibe flow review

- [ ] 4.1 更新 `--local` 参数支持 `--local=codex` 和 `--local=copilot`
- [ ] 4.2 在错误提示中引用 `vibe chat` 命令
- [ ] 4.3 添加安装指南链接

## 5. 交互式选择（可选）

- [ ] 5.1 实现 `_chat_select_agent()` - 交互式选择
- [ ] 5.2 提供 "直接启动" 选项
- [ ] 5.3 提供 "显示使用指南" 选项

## 6. 文档更新

- [ ] 6.1 更新 README 或 docs/ 说明新功能
- [ ] 6.2 创建 `.agent/agents.yml` 使用指南
- [ ] 6.3 更新 CHANGELOG.md

## 7. 测试

- [ ] 7.1 测试 `vibe chat` 显示所有 agent
- [ ] 7.2 测试 `vibe chat --agent=codex` 显示正确指南
- [ ] 7.3 测试 `vibe chat --agent=copilot` 显示正确指南
- [ ] 7.4 测试未安装 agent 的提示
- [ ] 7.5 测试 `vibe flow review --local=codex`
- [ ] 7.6 测试 `vibe flow review --local=copilot`
