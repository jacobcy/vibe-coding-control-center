# Subagent 推荐使用指南

## 概述

为了节省主会话的 token 并提高执行效率，某些 skills 强烈建议使用 subagent 执行。

## 推荐使用 Subagent 的 Skills

### ⭐⭐⭐ 强烈推荐

**1. vibe-review-code**
- **Token 成本**: 非常高（读取大量代码文件）
- **执行时间**: 长（几分钟）
- **优化策略**:
  - **优先**: 使用 `vibe flow review --local` (codex 本地审查)
  - **次选**: 使用 subagent + AI 审查
  - **Fallback**: copilot 本地审查（如果 codex 不可用）

**2. vibe-review-docs**
- **Token 成本**: 高（读取大量文档文件）
- **执行时间**: 中
- **优化策略**: 使用 subagent 隔离文档审查

### ⭐⭐ 推荐

**3. vibe-roadmap**
- **Token 成本**: 高（扫描项目文件）
- **执行时间**: 中长
- **优化策略**: 使用 subagent 扫描项目结构

**4. vibe-skills-manager**
- **Token 成本**: 中（扫描 skills 目录）
- **执行时间**: 中
- **优化策略**: 使用 subagent 独立分析

## 不推荐使用 Subagent 的 Skills

以下 skills 需要**在主会话中执行**：

- **vibe-continue**: 快速读取小文件，立即反馈
- **vibe-commit**: 需要用户交互确认
- **vibe-save**: 需要用户确认
- **vibe-done**: 需要用户确认
- **vibe-check**: 快速读取，立即反馈
- **vibe-task**: 需要交互选择

## Token 节省效果

| Skill | 原始成本 | 优化后成本 | 节省 |
|-------|---------|-----------|------|
| vibe-review-code | ~10K tokens | ~500 tokens (codex) | **95%** |
| vibe-review-code | ~10K tokens | ~2K tokens (subagent) | **80%** |
| vibe-review-docs | ~5K tokens | ~1K tokens (subagent) | **80%** |
| vibe-roadmap | ~5K tokens | ~1K tokens (subagent) | **80%** |
| vibe-skills-manager | ~3K tokens | ~800 tokens (subagent) | **73%** |

## 如何使用

### 方式 1: AI 自动判断
AI 会根据 skill description 中的 `**RECOMMENDED: Run as subagent to save tokens.**` 自动决定是否使用 subagent。

### 方式 2: 手动指定
用户可以明确要求：
```
使用 subagent 运行 vibe-review-code
```

## 最佳实践

1. **代码审查**: 优先使用 `vibe flow review --local` (codex)
2. **大型扫描**: 使用 subagent 隔离执行
3. **交互任务**: 主会话执行
4. **快速查询**: 主会话执行

## 更新日志

- 2026-03-07: 初始版本，标记 vibe-review-code, vibe-review-docs, vibe-roadmap, vibe-skills-manager
- 2026-03-07: 增强 `vibe flow review --local` 支持 codex/copilot fallback

