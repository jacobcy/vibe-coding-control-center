# unified-dispatcher Tasks

## 1. 扩展 task.md 格式

- [x] 1.1 定义 task.md framework 字段格式
- [x] 1.2 更新 task.md 示例，添加 framework 字段

## 2. 智能调度器逻辑（内联到 SKILL.md）

- [x] 2.1 在 vibe-orchestrator SKILL.md 添加 Gate 0: Intent Gate
- [x] 2.2 实现需求分析逻辑（复杂度、类型、范围、不确定性）
- [x] 2.3 实现历史 Pattern 匹配逻辑（读取 task.md，找相似特征）
- [x] 2.4 实现框架决策逻辑（高/中/低/极低置信度 → 不同决策）
- [x] 2.5 实现无感自动选择（高置信度场景）
- [x] 2.6 实现推荐确认（中置信度场景）
- [x] 2.7 实现主动询问（低置信度场景）
- [x] 2.8 实现记忆更新逻辑（写入 task.md）

## 3. 测试与验证

- [ ] 3.1 测试高置信度场景：简单 bug 修复 → 应无感选择 Superpower
- [ ] 3.2 测试中置信度场景：相似功能但新需求 → 应推荐确认
- [ ] 3.3 测试低置信度场景：全新复杂需求 → 应主动询问
- [ ] 3.4 验证 framework 字段正确写入 task.md
