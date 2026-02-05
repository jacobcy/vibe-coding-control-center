# 更新日志

## [2.0.0] - 2026-02-05

### ✨ 新增功能

#### 版本管理系统
- **版本检测**: 自动检测 Claude Code 和 OpenCode 的已安装版本
- **版本比较**: 新增版本比较工具函数 (`version_equal`, `version_greater_than`, `version_less_than`)
- **版本显示**: 在状态检查和菜单中显示当前安装的版本号

#### 智能更新功能
- **Claude Code 更新**: 
  - 检测已安装版本并显示
  - 询问用户是否更新到最新版本
  - 支持 macOS (Homebrew) 和 Linux (npm) 更新
  - 更新后显示新旧版本对比
  
- **OpenCode 更新**:
  - 检测已安装版本并显示
  - 询问用户是否更新到最新版本
  - 支持 macOS (Homebrew) 和 Linux (curl) 更新
  - 更新后显示新旧版本对比

- **oh-my-opencode 管理**:
  - 自动检测是否已安装
  - 支持更新已安装的 oh-my-opencode
  - 自动运行安装脚本

#### 配置智能合并
- **MCP 配置合并**:
  - 检测现有 MCP 配置文件
  - 询问用户选择合并或替换
  - 使用 `jq` 进行智能 JSON 深度合并(如果可用)
  - 自动创建带时间戳的配置备份
  - 合并失败时自动回退到备份+替换模式

#### 增强的用户界面
- **状态显示增强**:
  - 显示 Claude Code 版本号
  - 显示 OpenCode 版本号
  - 显示 oh-my-opencode 安装状态
  - 显示 MCP 服务器数量
  
- **Equip 菜单增强**:
  - 显示当前已安装工具的版本号
  - 明确标识未安装的工具
  - 更清晰的菜单选项说明

### 🔧 改进

#### lib/utils.sh
- 新增 `get_command_version()` - 获取命令版本号
- 新增 `version_equal()` - 版本相等比较
- 新增 `version_greater_than()` - 版本大于比较
- 新增 `version_less_than()` - 版本小于比较
- 新增 `update_via_brew()` - Homebrew 更新包装函数
- 新增 `update_via_npm()` - npm 更新包装函数
- 新增 `merge_json_configs()` - JSON 配置合并函数
- 新增 `BOLD` 颜色常量

#### install/install-claude.sh
- 重构 Claude CLI 安装逻辑,支持版本检测和更新
- 添加 MCP 配置合并逻辑
- 改进用户交互提示
- 步骤从 "2/6 Check Claude CLI" 改为 "2/6 Check & Update Claude CLI"
- 步骤从 "6/6 Configure MCP" 改为 "6/6 Configure MCP" (保持不变,但逻辑增强)

#### install/install-opencode.sh
- 重构 OpenCode CLI 安装逻辑,支持版本检测和更新
- 改进 oh-my-opencode 安装和更新逻辑
- 添加更详细的错误处理
- 步骤从 3 步增加到 4 步
- 新增 "4/4 Create OpenCode Config Directory" 步骤

#### scripts/vibecoding.sh
- 增强 `check_status()` 函数,显示版本信息
- 增强 `do_equip()` 菜单,显示当前版本
- 改进状态显示格式

### 📝 文档更新
- 新增 `UPGRADE_FEATURES.md` - 详细的升级功能说明文档
- 更新 `README.md` - 添加新功能说明和使用指南
- 新增 `CHANGELOG.md` - 版本更新日志

### 🧪 测试
- 新增 `test_new_features.sh` - 测试版本检测和比较功能
- 新增 `test_status_display.sh` - 测试状态显示功能
- 所有语法检查通过
- 所有功能测试通过

### 🔒 安全性
- 所有新增函数都包含输入验证
- 配置文件操作前自动创建备份
- 使用安全的文件操作函数
- 遵循现有的安全编码规范

### 📋 兼容性
- 向后兼容现有安装
- 首次安装流程保持不变
- 已安装用户重新运行安装脚本即可获得更新功能
- 支持 macOS 和 Linux 系统

### 🎯 使用示例

#### 更新已安装工具
```bash
# 使用控制中心
./scripts/vibecoding.sh
# 选择 "2) EQUIP"
# 选择要更新的工具

# 或直接运行
./install/install-claude.sh
./install/install-opencode.sh
```

#### 查看版本信息
```bash
./scripts/vibecoding.sh
# 主界面会显示所有工具的版本信息
```

### 🐛 已知问题
- 无

### 📌 注意事项
1. 建议安装 `jq` 以获得更好的 JSON 合并体验: `brew install jq`
2. 所有更新操作都需要用户确认,不会自动执行
3. MCP 配置更新时会自动创建备份文件,位于 `~/.claude.json.backup.*`
4. 如果版本检测失败,会显示 "version unknown",但不影响功能使用

### 🔜 后续计划
- [ ] 添加自动检查更新功能
- [ ] 支持静默更新模式
- [ ] 添加版本回退功能
- [ ] 支持更多包管理器
- [ ] 添加更新日志显示

