# Control Plane Integration

## 接口契约

### Control → Process

控制平面调用流程平面的接口：

```bash
# 1. 路由任务
provider_name=$(pp_route "$task")

# 2. 启动执行
provider_ref=$(pp_start "$task" "$context")

# 3. 查询状态
status=$(pp_status "$provider_ref")

# 4. 完成执行
result=$(pp_complete "$provider_ref")
```

### Process → Control

流程平面返回给控制平面的数据：

**状态响应格式**:
```json
{
  "state": "in_progress" | "done" | "failed",
  "metadata": {
    "provider": "openspec",
    "provider_ref": "openspec:task-123_1234567890",
    "started_at": "2026-03-03T10:00:00Z",
    "updated_at": "2026-03-03T10:05:00Z"
  }
}
```

**完成响应格式**:
```json
{
  "result": "success" | "failed",
  "artifacts": [
    "path/to/artifact1",
    "path/to/artifact2"
  ],
  "message": "Task completed successfully"
}
```

## 数据格式约定

### Task 格式
```json
{
  "id": "task-123",
  "type": "spec-driven" | "ad-hoc",
  "risk": "low" | "medium" | "high",
  "resources": {
    "ai": "sufficient" | "insufficient"
  }
}
```

### Context 格式
```json
{
  "user": "developer",
  "environment": "development",
  "metadata": {}
}
```

## 错误处理

流程平面返回错误时的格式：
```json
{
  "error": "Error description",
  "code": "ERROR_CODE",
  "details": {}
}
```

## 状态映射

控制平面状态机保持不变：
```
todo → in_progress → blocked → done → archived
```

流程平面内部状态聚合为：
- `in_progress`: 任务正在执行
- `done`: 任务完成
- `failed`: 任务失败

## 示例集成代码

```bash
#!/usr/bin/env zsh
# 控制平面集成示例

# 加载流程平面模块
source v3/process-plane/adapter-loader.sh
source v3/process-plane/strategy.sh
source v3/process-plane/fallback.sh
source v3/process-plane/router.sh

# 处理任务
process_task() {
  local task_id="$1"
  local task_type="$2"
  
  # 构造任务对象
  local task
  task=$(jq -n \
    --arg id "$task_id" \
    --arg type "$task_type" \
    '{id: $id, type: $type}')
  
  # 路由到合适的 provider
  local provider
  provider=$(pp_route "$task")
  
  echo "Task $task_id routed to: $provider"
  
  # 启动执行
  local provider_ref
  provider_ref=$(pp_start "$task" '{}')
  
  echo "Started: $provider_ref"
  
  # 查询状态
  local status
  status=$(pp_status "$provider_ref")
  
  echo "Status: $status"
  
  # 完成执行
  local result
  result=$(pp_complete "$provider_ref")
  
  echo "Result: $result"
}

# 使用示例
process_task "task-001" "spec-driven"
```
