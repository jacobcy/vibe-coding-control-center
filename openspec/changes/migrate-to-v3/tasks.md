# migrate-to-v3 Tasks

## 1. 核心层搭建

- [x] 1.1 创建 `lib/core/` 目录结构
- [x] 1.2 实现命令路由器 `lib/core/router.sh`
- [x] 1.3 实现生命周期管理器 `lib/core/lifecycle.sh`
- [x] 1.4 建立能力注册中心框架 `lib/core/capability_registry.sh`
- [x] 1.5 编写核心层单元测试

## 2. 能力注册中心实现

- [x] 2.1 设计能力注册接口（register_capability, discover_capability, invoke_capability）
- [x] 2.2 实现基于文件系统的能力发现机制
- [x] 2.3 创建能力模块模板 `lib/capabilities/template.sh`
- [x] 2.4 实现能力依赖解析
- [x] 2.5 编写能力注册中心测试

## 3. 生命周期钩子系统

- [x] 3.1 设计钩子注册接口（hook_before_*, hook_after_*）
- [x] 3.2 实现钩子执行引擎
- [x] 3.3 实现钩子失败处理和回滚
- [x] 3.4 实现钩子上下文传递
- [x] 3.5 编写钩子系统测试

## 4. 现有模块迁移 - 工具类

- [x] 4.1 迁移 `lib/utils.sh` 到 `lib/utils/` 工具层
- [x] 4.2 重构 utils 为纯函数工具（无副作用）
- [x] 4.3 添加工具函数文档和类型注释
- [x] 4.4 更新 utils 相关测试

## 5. 现有模块迁移 - 检查能力

- [ ] 5.1 创建 `lib/capabilities/check.sh` 能力模块
- [ ] 5.2 实现 check 能力的 register_hooks
- [ ] 5.3 迁移 `lib/check.sh` 和 `lib/check_json.sh` 逻辑到新模块
- [ ] 5.4 注册 check 能力到注册中心
- [ ] 5.5 更新 check 相关测试

## 6. 现有模块迁移 - 工作流能力

- [ ] 6.1 创建 `lib/capabilities/flow.sh` 能力模块
- [ ] 6.2 迁移 `lib/flow.sh` 逻辑到新模块
- [ ] 6.3 迁移 `lib/flow_help.sh` 作为帮助子系统
- [ ] 6.4 注册 flow 能力到注册中心
- [ ] 6.5 更新 flow 相关测试

## 7. 现有模块迁移 - 工具管理能力

- [ ] 7.1 创建 `lib/capabilities/tool.sh` 能力模块
- [ ] 7.2 迁移 `lib/tool.sh` 逻辑到新模块
- [ ] 7.3 注册 tool 能力到注册中心
- [ ] 7.4 更新 tool 相关测试

## 8. 现有模块迁移 - 密钥管理能力

- [ ] 8.1 创建 `lib/capabilities/keys.sh` 能力模块
- [ ] 8.2 迁移 `lib/keys.sh` 逻辑到新模块
- [ ] 8.3 注册 keys 能力到注册中心
- [ ] 8.4 更新 keys 相关测试

## 9. 现有模块迁移 - 任务管理能力

- [ ] 9.1 创建 `lib/capabilities/task.sh` 能力模块
- [ ] 9.2 迁移 `lib/task.sh` 和 `lib/task_help.sh` 逻辑到新模块
- [ ] 9.3 迁移 `lib/task_io.sh` 作为任务 I/O 子系统
- [ ] 9.4 注册 task 能力到注册中心
- [ ] 9.5 更新 task 相关测试

## 10. 现有模块迁移 - 技能管理能力

- [ ] 10.1 创建 `lib/capabilities/skills.sh` 能力模块
- [ ] 10.2 迁移 `lib/skills.sh` 和 `lib/skills_sync.sh` 逻辑到新模块
- [ ] 10.3 注册 skills 能力到注册中心
- [ ] 10.4 更新 skills 相关测试

## 11. 现有模块迁移 - 其他能力

- [ ] 11.1 创建 `lib/capabilities/doctor.sh` 能力模块
- [ ] 11.2 创建 `lib/capabilities/clean.sh` 能力模块
- [ ] 11.3 创建 `lib/capabilities/config.sh` 能力模块
- [ ] 11.4 迁移所有相关逻辑到新模块
- [ ] 11.5 注册所有能力到注册中心

## 12. 配置管理系统

- [ ] 12.1 创建 `config/environments/` 目录结构
- [ ] 12.2 创建 `config/default.yaml` 默认配置
- [ ] 12.3 创建 `config/environments/development.yaml`
- [ ] 12.4 创建 `config/environments/production.yaml`
- [ ] 12.5 实现 `lib/core/config_loader.sh` 配置加载器
- [ ] 12.6 添加 yq 依赖检查到 doctor
- [ ] 12.7 实现环境变量插值支持
- [ ] 12.8 编写配置系统测试

## 13. Framework Dispatcher 升级

- [ ] 13.1 更新 framework-dispatcher 集成 control plane
- [ ] 13.2 实现通过能力注册中心调用框架
- [ ] 13.3 添加框架选择的 before/after 钩子
- [ ] 13.4 更新 pattern 存储到能力注册中心
- [ ] 13.5 更新 framework-dispatcher 测试

## 14. Skill Optimizations 增强

- [ ] 14.1 实现上下文预算追踪系统
- [ ] 14.2 实现智能摘要策略（diff, log, config）
- [ ] 14.3 添加预算警告和强制执行
- [ ] 14.4 更新技能示例展示上下文高效用法
- [ ] 14.5 更新 skill-optimizations 测试

## 15. CLI 入口更新

- [ ] 15.1 重构 `bin/vibe` 使用核心层路由
- [ ] 15.2 实现命令生命周期管理
- [ ] 15.3 保持向后兼容的命令别名
- [ ] 15.4 更新 CLI 帮助文档
- [ ] 15.5 编写 CLI 集成测试

## 16. 集成测试

- [ ] 16.1 端到端测试：vibe check
- [ ] 16.2 端到端测试：vibe flow start/review/pr/done
- [ ] 16.3 端到端测试：vibe tool list/verify
- [ ] 16.4 端到端测试：vibe keys list/set/get
- [ ] 16.5 端到端测试：vibe task create/list/complete
- [ ] 16.6 端到端测试：vibe skills install/list/sync
- [ ] 16.7 端到端测试：vibe doctor
- [ ] 16.8 端到端测试：vibe clean

## 17. 性能测试

- [ ] 17.1 建立性能基准（v2 命令执行时间）
- [ ] 17.2 测试 v3 核心路由开销
- [ ] 17.3 测试能力加载性能
- [ ] 17.4 测试配置加载性能
- [ ] 17.5 对比 v2 和 v3 性能数据
- [ ] 17.6 优化性能瓶颈

## 18. 文档更新

- [ ] 18.1 更新 STRUCTURE.md 反映 v3 架构
- [ ] 18.2 更新 AGENTS.md 说明新的入口流程
- [ ] 18.3 更新 CLAUDE.md 硬规则（LOC 限制调整）
- [ ] 18.4 创建 `docs/architecture/v3-control-plane.md` 架构文档
- [ ] 18.5 创建 `docs/guides/creating-capabilities.md` 能力开发指南
- [ ] 18.6 更新 `.agent/rules/coding-standards.md` 反映新架构
- [ ] 18.7 更新 README.md 用户可见变更

## 19. 向后兼容性验证

- [ ] 19.1 验证所有现有命令别名可用
- [ ] 19.2 验证现有配置文件兼容
- [ ] 19.3 验证现有 worktree 工作流兼容
- [ ] 19.4 验证现有测试套件通过
- [ ] 19.5 创建迁移指南（v2 → v3）

## 20. 清理与优化

- [ ] 20.1 移除旧版 lib/ 中的冗余代码
- [ ] 20.2 统一代码风格和注释
- [ ] 20.3 检查并消除循环依赖
- [ ] 20.4 验证 LOC 限制（lib/ + bin/ ≤ 1800）
- [ ] 20.5 最终代码审查
