# Agent Policies 目录

本目录包含按执行 mode 注入的策略材料。

## 目录职责

- `common.md`：`plan/run/review` 共享的工具与现场约束
- `plan.md`：`vibe3 plan` 的执行策略
- `run.md`：`vibe3 run` 的执行策略
- `review.md`：`vibe3 review` 的执行策略

## 与 rules 的区别

- `.agent/rules/`：仓库长期规则、硬约束、实现标准
- `.agent/policies/`：按 mode 加载的运行时策略材料

不要把仓库级规则继续写进 policy，也不要把 mode-specific 策略塞回 rules。
