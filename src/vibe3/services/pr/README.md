# PR Services

`services/pr/` 提供 PR 查询、创建、ready、base resolution、review briefing 与 verdict policy。

## 主要边界

- `service.py`：PRService 主入口。
- `create.py`：PRCreateUsecase 与 PR body 构建。
- `ready.py`：PR ready 用例和现有质量门禁编排。
- `base_resolution.py`、`resolver.py`：branch/base 解析。
- `review.py`：review briefing；仅在本地能验证精确 Git refs 时附加 `ReviewObservation`。
- `verdict_service.py`、`verdict_policy.py`：review verdict 规则。
- `loc_comment.py`、`utils.py`：薄辅助能力。

PR 服务不计算或重导出 risk score、impacted modules、symbol DAG 或 snapshot diff。
需要代码审查证据时复用 versioned `ReviewObservation`，证据不可验证时明确省略。
