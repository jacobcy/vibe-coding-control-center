---
document_type: artifact
title: Main-Preferred Conflict Rerun List
status: active
author: Codex GPT-5
created: 2026-03-10
last_updated: 2026-03-10
---

# Main-Preferred Conflict Rerun List

## Goal

本清单记录本次与 `origin/main` 合并时，曾发生冲突、但最终统一接受 `main` 版本的文件。

这些文件里，本分支原本的语义修正内容已经被放弃，后续如需继续推进 GitHub Project / execution record 语义纠正，应重新在新基线上逐项补回。

## Accepted Main Version

### Highest Priority: Standards And Workflow Semantics

- `.agent/workflows/vibe-new.md`
- `docs/standards/command-standard.md`
- `docs/standards/data-model-standard.md`
- `docs/standards/git-workflow-standard.md`
- `docs/standards/shell-skill-boundary-audit.md`
- `docs/standards/skill-standard.md`

### Medium Priority: Skill Semantics

- `skills/vibe-check/SKILL.md`
- `skills/vibe-roadmap/SKILL.md`
- `skills/vibe-save/SKILL.md`
- `skills/vibe-task/SKILL.md`

### Low Priority: Runtime / Release Files

- `CHANGELOG.md`
- `VERSION`
- `lib/flow.sh`
- `lib/flow_help.sh`

## Why These Need Rerun

### Standards And Workflow Semantics

这些文件是本轮“语义纠正”最核心的载体。本分支原本想补的重点包括：

- `repo issue -> roadmap item -> task -> flow -> PR` 对象链
- `task` 作为 execution record 的定义
- `roadmap item` 作为 mirrored GitHub Project item 的定义
- `flow` 不回退为规划入口
- `spec_standard` / `execution_record_id` / `spec_ref` 的扩展字段位置

由于这次冲突统一接受了 `main`，上述修正需要重新基于最新主干语义再做一遍，而不是假设已经保留。

### Skill Semantics

这些文件里，本分支原本补的是“入口文案和技能描述不要重新发明对象模型”的约束。现在接受 `main` 后，需要重新检查：

- skill 是否仍把 `task` 和 roadmap item `type=task` 混用
- workflow 是否仍把 `flow` 说成规划入口
- 是否仍缺少 GitHub Project / milestone / execution record 的明确分层

### Runtime / Release Files

这几项不是下一轮语义纠正的核心，不建议优先处理：

- `CHANGELOG.md`
- `VERSION`
- `lib/flow.sh`
- `lib/flow_help.sh`

它们这次接受 `main` 是为了快速消除冲突，不代表你本分支原来的语义目标应该继续在这些文件里补。

## Suggested Rerun Order

1. `docs/standards/command-standard.md`
2. `docs/standards/data-model-standard.md`
3. `docs/standards/git-workflow-standard.md`
4. `docs/standards/skill-standard.md`
5. `docs/standards/shell-skill-boundary-audit.md`
6. `.agent/workflows/vibe-new.md`
7. `skills/vibe-roadmap/SKILL.md`
8. `skills/vibe-task/SKILL.md`
9. `skills/vibe-save/SKILL.md`
10. `skills/vibe-check/SKILL.md`

## Notes

- 本清单只覆盖“发生过冲突并接受 `main`”的文件。
- 没有冲突、且本分支改动已直接保留的文件，不在本清单中。
- 本清单适合作为下一轮“语义纠正任务”的输入范围，而不是完整 PR 变更清单。
