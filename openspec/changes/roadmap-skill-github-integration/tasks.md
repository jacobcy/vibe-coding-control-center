## 1. Roadmap Skill Setup

- [x] 1.1 Create skills/vibe-roadmap/SKILL.md
- [x] 1.2 Register skill in skills/vibe-skills/registry.json
- [x] 1.3 Verify skill loads: `bin/vibe check`

## 2. Scheduler Core Logic

- [x] 2.1 Implement version goal storage (registry.json)
- [x] 2.2 Implement scheduler check: has version goal?
- [x] 2.3 Scheduler prompts when no goal (via status command)
- [x] 2.4 Priority task assignment (via classify + version next)

## 3. Issue Classification State Machine

- [x] 3.1 Implement 5 states: P0, current, next, deferred, rejected
- [x] 3.2 State transition logic (classify command)
- [x] 3.3 Version cycle management (version bump/next/complete)

## 4. vibe-new Integration

- [x] 4.1 Modify .agent/workflows/vibe-new.md to call scheduler first
- [ ] 4.2 Implement: user specifies task -> direct to orchestrator
- [ ] 4.3 Implement: user doesn't specify -> call scheduler to assign

## 5. GitHub Sync (Wish Pool)

- [x] 5.1 Extend lib/roadmap.sh: new roadmap command
- [x] 5.2 Implement GitHub issue sync for wish pool (vibe roadmap sync --provider github)
- [ ] 5.3 Extend lib/task_actions.sh for task sync --provider github
- [ ] 5.4 Create tests/test_task_sync_github.bats

## 6. Changelog Generation

- [x] 6.1 Version number increment logic (vibe roadmap version bump)
- [ ] 6.2 Changelog generation from completed tasks
- [ ] 6.3 Test changelog output format

## 7. Integration Testing

- [ ] 7.1 Test full flow: vibe-new -> scheduler -> assign task
- [ ] 7.2 Test version cycle: end -> confirm next goal -> re-evaluate
- [ ] 7.3 Run existing test suite: `bats tests/`
- [ ] 7.4 Update CHANGELOG.md
