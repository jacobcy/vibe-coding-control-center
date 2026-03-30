# Vibe3 代码质量与复用评估报告

> **状态**：初版扫描，部分条目已人工核实；未附工具原始输出，结论仅供重构参考。

代码库中存在可优化的**工具类混用**、**死代码 (Dead Code)** 以及部分**高圈复杂度 (High Cyclomatic Complexity)** 的实现。

## 1. 共用方法的 Utils 抽取评估（职责错置）

目前项目的目录分层存在一个明显问题：**纯静态工具函数混入了 `services` 层**。`services` 目录应当只包含持有状态、需要依赖注入（如 `store`, `git`）的业务服务类。

**建议移动到 `src/vibe3/utils/` 的模块：**
1. **`services/issue_ref_utils.py`**：完全是纯字符串和正则解析（如 `parse_issue_number`），不依赖任何客户端。
2. **`services/pr_utils.py`**：里面是提取 PR 编号等偏向字符串处理的无状态方法。
3. **`services/review_parser.py`**：纯文本转换、正则提取等 `Parser` 行动，本质可以归属为 `utils/parsers/`。
4. **`services/command_analyzer_helpers.py`** / **`review_pipeline_helpers.py`**：这些 `helpers` 多是纯函数，应放入 `utils/` 或者直接收拢到对应调用方的私有域中。

**总结**：将这些“无状态的静态方法”归拢到 `vibe3/utils` 中，能够使 `services` 目录的语义彻底纯净，不再是杂物箱。

---

## 2. 不被使用的代码（YAGNI 违背与 Dead Code）

通过 `vulture` 检测，系统内残留了大量的“过度前置设计（写了但根本没有业务在调用的代码）”：

1. **废弃的 Exception 定义泛滥**：
   在 `vibe3/exceptions/__init__.py` 中，存在大量未使用的异常类，如 `FlowNotFoundError`, `CommitAnalyzerError`, `HookManagerError`, `SQLiteError`, `BatchError` 等。说明设计时预想了很多错误场景但在真实逻辑中用的是基础报错或没有走到这些分支。
2. **闲置的 Client 方法**：
   - `GitClient.is_worktree_clean` / `remove_worktree` （目前可能直接用别的方式调用了）
   - `GitHubReviewOps.add_pr_comment`
   - `StoreClientProtocol` (未被实际用来走类型约束)
3. **沉寂的 Service 方法与模型方法**：
   - `pr_service.calculate_version_bump` (PR的版本计算未使用)
   - `models/flow.py` 内部的迁移函数 `migrate_flow_status`（仅定义未调用）
   - `handoff_service` 的单向记录方法（如 `record_plan`, `record_audit` 等目前未被消费）。

**建议**：删除上述确认未使用的代码。Git 已记录历史，未来需要时可按需恢复。

---

## 3. 低质量实现（高圈复杂度与 Lint）

通过 `radon cc` 圈复杂度检测，整个后端服务的平均复杂度在 **C级 (平均 15.5)**，处于偏高水平（合理的业务模型建议在 10 以下）。这表明有较多的长函数和深层嵌套。

**主要重灾区（复杂度达到 D 或高 C 的实现）：**
1. **UI 渲染层（大量的 IF-ELSE 堆砌）**：
   - `ui/flow_ui.py: render_flow_status` (复杂度 **D**)
   - `ui/task_ui.py: render_task_show` (复杂度 **D**)
   - `ui/flow_ui_timeline.py: render_flow_timeline` (复杂度 **D**)
   *原因*：UI 渲染逻辑里嵌了太多的 `if/else` 判空、颜色叠加和业务规则验证。
   *解法*：分离“视图数据构建”与“终端 Rich 渲染”，先把数据整理成平铺的 ViewModel ，渲染器只负责 `print`。
2. **核心检查与分析层（长函数与深嵌套）**：
   - `services/check_service.py: _check_branch` (复杂度 **D**)
   - `services/snapshot_diff_section.py: build_snapshot_diff_section` (复杂度 **D**)
   - `services/change_scope_service.py: classify_changed_files` (复杂度 **C**)
   *原因*：在一个函数体里混杂了“拉取状态”、“对比数据”、“分支条件处理”多种动作。
   *解法*：在接下来的 Service 聚合重构中，通过提取小型的、见名知意的内部私有方法 `_step1_check_xxx` 进行线性斩断。


