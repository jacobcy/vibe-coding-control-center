# LOC优化计划：从20,107降至19,000

> **目标**：减少1,107行代码，为后续开发留出余量
> **原则**：不通过简单拆分增加LOC，而是真正删除/简化代码
> **当前LOC**：20,107
> **目标LOC**：19,000

---

## 一、优化策略

### ❌ 错误策略（会增加LOC）
- 简单拆分大文件 → 增加import、class定义等重复代码
- 过度抽象 → 增加中间层代码
- 提取helper函数 → 如果只调用一次反而增加代码

### ✅ 正确策略（真正减少LOC）
1. **删除Dead Code**
   - 未使用的函数/类
   - 已废弃的功能
   - 过时的测试用例

2. **合并重复逻辑**
   - 相似的函数合并
   - 重复的验证逻辑提取
   - 共享的工具函数

3. **简化实现**
   - 重写复杂逻辑
   - 使用更简洁的语法
   - 利用标准库功能

4. **优化测试代码**
   - 合并相似测试
   - 使用参数化测试
   - 删除冗余断言

---

## 二、目标分解

**总目标**：减少1,107行

| 模块 | 当前行数 | 目标减少 | 优化方式 |
|------|---------|---------|---------|
| services | 6,632 | -400 | 删除未使用服务、合并重复逻辑 |
| commands | 5,669 | -350 | 简化命令实现、删除废弃命令 |
| clients | 3,197 | -200 | 合并相似client、简化API |
| tests | ~4000 | -157 | 合并测试、使用参数化 |
| **合计** | **19,698** | **-1,107** | **达到19,000目标** |

---

## 三、Phase 1: 删除Dead Code（目标-300行）

### 3.1 未使用的命令和服务

**注意**：LOC空间是留给orchestra开发的，orchestra相关代码保留

**检查方法**：
```bash
# 查找未使用的函数
vibe3 inspect symbols <file>
# 查看引用计数为0的函数
```

**候选删除项**：
1. 已废弃的迁移代码 - 如果已迁移完成
2. 未使用的UI组件
3. 重复的工具函数

### 3.2 测试中的dead code

**检查方法**：
- 查找被`@pytest.mark.skip`标记且长时间未修复的测试
- 查找被注释掉的测试代码

---

## 四、Phase 2: 合并重复逻辑（目标-400行）

### 4.1 重复的验证逻辑

**问题**：多个命令中有相似的参数验证

**解决方案**：提取到`validation_utils.py`

**示例**：
```python
# Before: 重复代码
def flow_new(branch: str):
    if not branch:
        raise ValueError("branch required")
    if not re.match(r'^[\w-]+$', branch):
        raise ValueError("invalid branch name")

def task_new(task: str):
    if not task:
        raise ValueError("task required")
    if not re.match(r'^[\w-]+$', task):
        raise ValueError("invalid task name")

# After: 合并
def validate_name(name: str, name_type: str) -> str:
    if not name:
        raise ValueError(f"{name_type} required")
    if not re.match(r'^[\w-]+$', name):
        raise ValueError(f"invalid {name_type} name")
    return name
```

**预计减少**：-50行

### 4.2 相似的client方法

**问题**：`git_client.py`和`github_client.py`有相似的方法

**解决方案**：提取共享逻辑到base client

**预计减少**：-100行

### 4.3 重复的handoff记录逻辑

**问题**：`handoff.py`中多个命令有相似的记录逻辑

**解决方案**：提取到`handoff_recorder.py`

**预计减少**：-50行

---

## 五、Phase 3: 简化实现（目标-300行）

### 5.1 使用更简洁的语法

**示例**：
```python
# Before: 8行
def get_status(self):
    if self.active:
        if self.paused:
            return "paused"
        else:
            return "running"
    else:
        return "stopped"

# After: 3行
def get_status(self):
    return ("paused" if self.paused else "running") if self.active else "stopped"
```

**预计减少**：-50行

### 5.2 利用标准库功能

**示例**：
```python
# Before: 15行手动实现
def parse_config(content: str) -> dict:
    result = {}
    for line in content.split('\n'):
        if '=' in line:
            key, value = line.split('=', 1)
            result[key.strip()] = value.strip()
    return result

# After: 3行使用标准库
import configparser

def parse_config(content: str) -> dict:
    parser = configparser.ConfigParser()
    parser.read_string(f"[default]\n{content}")
    return dict(parser['default'])
```

**预计减少**：-100行

### 5.3 简化复杂函数

**目标文件**：
- `task_bridge_mixin.py` (373行) - 简化自动链接逻辑
- `handoff.py` (421行) - 简化展示逻辑
- `run.py` (395行) - 简化执行流程

**方法**：重写最长的5个函数

**预计减少**：-150行

---

## 六、Phase 4: 优化测试代码（目标-107行）

### 6.1 使用参数化测试

**Before**：
```python
def test_flow_new_with_issue():
    # test with issue

def test_flow_new_without_issue():
    # test without issue

def test_flow_new_with_invalid_issue():
    # test with invalid issue
```

**After**：
```python
@pytest.mark.parametrize("issue,expected", [
    (123, "success"),
    (None, "no_issue"),
    ("invalid", "error"),
])
def test_flow_new(issue, expected):
    # single test with parameters
```

**预计减少**：-50行

### 6.2 删除冗余测试

**检查方法**：
- 相同逻辑的重复测试
- 过度防御的测试（测试不会失败的逻辑）

**预计减少**：-57行

---

## 七、执行计划

### Week 1: Dead Code清理
- Day 1-2: 使用`vibe3 inspect`找到未使用的符号
- Day 3-4: 删除未使用的函数/类
- Day 5: 验证测试通过

### Week 2: 合并重复逻辑
- Day 1-2: 提取验证逻辑到utils
- Day 3-4: 合并client方法
- Day 5: 重构handoff记录

### Week 3: 简化实现
- Day 1-2: 简化最长函数
- Day 3-4: 使用标准库替换手工实现
- Day 5: 代码审查

### Week 4: 测试优化
- Day 1-3: 参数化测试
- Day 4-5: 删除冗余测试

---

## 八、验证指标

**成功标准**：
- [ ] 总LOC ≤ 19,000
- [ ] 所有测试通过
- [ ] 覆盖率不降低
- [ ] 类型检查通过
- [ ] 最大单文件LOC ≤ 350

**验收测试**：
```bash
# 1. LOC检查
PYTHONPATH=src uv run python -c "
from vibe3.services.metrics_service import collect_python_metrics
m = collect_python_metrics()
assert m.total_loc <= 19000, f'LOC {m.total_loc} > 19000'
print(f'✅ Total LOC: {m.total_loc}')
"

# 2. 测试通过
uv run pytest tests/vibe3

# 3. 类型检查
uv run mypy src/vibe3
```

---

## 九、风险与缓解

### 风险1: 过度删除导致功能缺失
**缓解**: 每次删除前检查引用，运行测试验证

### 风险2: 重构引入新bug
**缓解**: 小步提交，每次只改一个模块

### 风险3: 测试覆盖率下降
**缓解**: 监控coverage，确保不降低

---

## 十、回滚计划

如果优化后发现重大问题：
1. 创建issue跟踪问题
2. 回退相关commit
3. 保留优化计划，下次迭代再优化

---

**文档版本**：v1.0
**创建日期**：2026-03-25
**维护者**：Vibe Center Team