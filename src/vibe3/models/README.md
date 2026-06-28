# Models

`models/` 保存跨 commands、services、analysis 和 runtime 流转的 Pydantic/领域模型。
公共导出由 `models/__init__.py` 维护，调用方不应依赖未导出的内部细节。

主要模型域：

- flow、state machine、domain events、orchestration；
- audit observation/suggestion/decision；
- PR、review、verdict、coverage；
- execution request/handle、job、runtime session；
- handoff、coordination truth、task bridge；
- `inspect_evidence.py` 的 versioned evidence schema。

Inspect schema 只表达可回指 Git object、当前文件或有效 source range 的证据。
`ReviewObservation` 的 Kernel impact 是核心文件命中，不是运行时影响或风险分数。
