# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 

### Changed
- 

### Deprecated
- 

### Removed
- 

### Fixed
- 

### Security
- 

## [2.0.1] - 2026-02-14

### ✨ New Features
- **Version Management**: Added `VERSION` file as single source of truth.
- **Release Workflow**: Added GitHub Action `.github/workflows/release.yml` for automated releases.
- **Bump Script**: Added `.agent/lib/bump_version.sh` for easy version management.
- **Utils Update**: Updated `lib/utils.sh` to read project version from `VERSION` file.

## [2.0.0] - 2026-02-05

### ✨ 新增功能
- **配置加载**: 新增 `lib/config_loader.sh` 模块化配置管理
- **配置验证**: 新增 `validate_and_load_config` 函数强化输入验证
- **安全路径验证**: 实现 `validate_path` 防止路径遍历
- **文件验证**: 实现 `secure_copy` / `secure_write_file` / `secure_append_file`
- **输入验证**: 实现 `validate_input` / `validate_filename` / `validate_command`
- **日志系统**: 实现彩色日志系统 `log_*` 函数
- **错误处理**: 实现 `handle_error` 错误陷阱机制
- **用户交互**: 实现 `prompt_user` / `confirm_action` 安全交互函数
- **路径解析**: 实现 `normalize_path` / `is_subpath` 安全路径函数
- **安全操作**: 实现 `secure_temp_file` 安全临时文件函数
- **命令验证**: 实现 `validate_command` 防止命令注入
- **文件名验证**: 实现 `sanitize_filename` 防止路径遍历
- **类型定义**: 实现 `declare -g` 全局类型定义

### 🚀 性能改进
- **错误处理**: 配置加载器错误处理策略更改为不中断执行
- **安全验证**: 路径/输入验证性能优化

### 🐛 Bug 修复
- **错误恢复**: 配置加载器在错误时现在会发出警告而非中断脚本
- **安全性**: 修复潜在路径遍历漏洞

### 🛡️ 安全性
- **配置安全**: 安全配置加载（防命令注入/路径遍历）
- **路径安全**: 路径验证与规范化
- **文件操作**: 安全文件操作函数
- **输入过滤**: 输入验证与过滤

### 📝 文档
- **API 文档**: 配置管理模块完整文档
- **安全指南**: 安全开发最佳实践文档
- **CLI 手册**: 命令行界面用户手册
- **安装指南**: 安装与配置文档

### 💥 破坏性变更
- **错误处理**: 配置加载失败时不再中断脚本执行

### 🧪 测试
- **单元测试**: 配置加载器单元测试
- **集成测试**: 安全函数集成测试
- **合规测试**: 安全标准合规测试

