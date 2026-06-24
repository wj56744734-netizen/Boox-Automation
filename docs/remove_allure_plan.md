# 清理 Allure 执行方案

## 背景

Allure HTML 报告已不再使用，测试结束后实际通过飞书推送卡片 + 自定义 HTML 文件完成报告。但 Allure 数据采集层仍在运行：

- `allure.step()` 在 `operations.py` 中有 24 处，产生大量 JSON 结果文件
- `allure.attach()` 附加截图（截图已独立保存到文件，不依赖 Allure）
- `@allure.feature()` 仅在两个测试文件中做分类标记
- `conftest.py` 每轮动态设置 `allure_report_dir`，生成 `artifacts/allure_results/Test_*` 目录
- `cleanup.py` 定期清理这些无下游消费的文件

**清理收益**：移除无用依赖、减少磁盘 IO、简化代码。

---

## 改动清单（7 个文件 + 1 个可选文档）

### 1. `boox_automation/ui_ops/operations.py` — 26 处改动

#### 1.1 删除 import（第 17 行）

```python
# 删除
import allure
```

#### 1.2 删除 `allure.attach()` 截图附件（第 311-315 行）

```python
# 删除以下 5 行：
                allure.attach(
                    screenshot,
                    name=attach_name,
                    attachment_type=allure.attachment_type.PNG,
                )
```

> 注：`screenshot` 变量（`driver.get_screenshot_as_png()`）仅用于此 attach，也一并删除（第 309 行）。`attach_name` 变量（第 310 行）也一并删除。

#### 1.3 删除 24 处 `with allure.step(...):`

每处的改动模式相同：删除 `with allure.step(...):` 行，内部代码块减少一级缩进（4 空格）。

| 行号 | 当前代码 | 改动 |
|------|---------|------|
| 746 | `with allure.step(step_msg):` | 删除，内部 747-752 行减缩进 |
| 771 | `with allure.step(f"多元素检查「{display}」"):` | 删除，内部 772+ 行减缩进 |
| 852 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 892 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 949 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1004 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1053 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1084 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1126 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1167 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1235 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1309 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1362 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1397 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1420 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1453 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1479 | `with allure.step(f"滑动({start_screen_width:.2f},{start_screen_height:.2f})→({end_screen_width:.2f},{end_screen_height:.2f})"):` | 删除，内部减缩进 |
| 1527 | `with allure.step(f"点击坐标 ({x_ratio:.2f},{y_ratio:.2f})"...):` | 删除，内部减缩进 |
| 1651 | `with allure.step(f"长按坐标 ({x_ratio:.2f},{y_ratio:.2f}) {duration}ms"):` | 删除，内部减缩进 |
| 1673 | `with allure.step(f"滑动 ({x1:.2f},{y1:.2f})→({x2:.2f},{y2:.2f})"):` | 删除，内部减缩进 |
| 1715 | `with allure.step(f"ADB命令「{cmd_name}」"):` | 删除，内部减缩进 |
| 1754 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1790 | `with allure.step(step_msg):` | 删除，内部减缩进 |
| 1813 | `with allure.step(step_msg):` | 删除，内部减缩进 |

---

### 2. `boox_automation/tests/test_excel_runner.py` — 3 处改动

#### 2.1 删除 import（第 19 行）

```python
# 删除
import allure
```

#### 2.2 删除 `@allure.feature` 装饰器（第 324 行）

```python
# 改前
@allure.feature("Excel驱动测试")
class TestExcelRunner:

# 改后
class TestExcelRunner:
```

#### 2.3 删除 `with allure.step(case_id):`（第 387 行）

```python
# 改前（第 386-394 行）
        try:
            with allure.step(case_id):
                for step in steps:
                    ...
                    _dispatch_step(...)
                    ...

# 改后
        try:
            for step in steps:
                ...
                _dispatch_step(...)
                ...
```

> 内部代码块（第 388-411 行）整体减少一级缩进。

---

### 3. `boox_automation/tests/test_performance/test_file_import.py` — 2 处改动

#### 3.1 删除 import（第 16 行）

```python
# 删除
import allure
```

#### 3.2 删除 `@allure.feature` 装饰器（第 20 行）

```python
# 改前
@allure.feature("笔记导入、导出文件相关测试类")

# 改后：直接删除该行
```

---

### 4. `boox_automation/conftest.py` — 1 处改动

#### 4.1 删除 `allure_report_dir` 设置（第 100-105 行）

```python
# 删除以下 6 行：
    # 动态设置 allure 结果目录
    try:
        from boox_automation.core.paths import new_allure_results_dir
        config.option.allure_report_dir = str(new_allure_results_dir())
    except Exception:
        pass
```

---

### 5. `boox_automation/core/paths.py` — 6 处改动

#### 5.1 删除文档注释中的 Allure 行（第 8-9 行）

```python
# 删除
- artifacts/allure_results/<timestamp>/   pytest --alluredir 写入
- artifacts/allure_html/<timestamp>/      allure generate 输出
```

#### 5.2 删除路径常量（第 32-33 行）

```python
# 删除
ALLURE_RESULTS_ROOT = ARTIFACTS_ROOT / "allure_results"
ALLURE_HTML_ROOT = ARTIFACTS_ROOT / "allure_html"
```

#### 5.3 删除工厂函数（第 49-56 行）

```python
# 删除以下 8 行：
def new_allure_results_dir(timestamp: str | None = None) -> Path:
    ts = timestamp or datetime.now().strftime("%Y%m%d%H%M%S")
    return ensure_dir(ALLURE_RESULTS_ROOT / f"Test_{ts}")


def new_allure_html_dir(timestamp: str | None = None) -> Path:
    ts = timestamp or datetime.now().strftime("%Y%m%d%H%M%S")
    return ensure_dir(ALLURE_HTML_ROOT / f"Test_html_{ts}")
```

#### 5.4 清理 `__all__` 导出列表（第 76-77, 83-84 行）

```python
# 删除 __all__ 中以下 4 项：
    "ALLURE_RESULTS_ROOT",
    "ALLURE_HTML_ROOT",
    "new_allure_results_dir",
    "new_allure_html_dir",
```

---

### 6. `boox_automation/core/cleanup.py` — 3 处改动

#### 6.1 更新模块文档注释（第 2 行）

```python
# 改前
集中清理项目运行期产物：保留最近 N 轮 allure / html / screenshots。

# 改后
集中清理项目运行期产物：保留最近 N 轮 screenshots / logs。
```

#### 6.2 清理 import（第 16-17 行）

```python
# 改前
from boox_automation.core.paths import (
    ALLURE_HTML_ROOT,
    ALLURE_RESULTS_ROOT,
    DEFAULT_KEEP_LATEST,
    LOGS_ROOT,
    SCREENSHOTS_ROOT,
    TMP_ROOT,
)

# 改后
from boox_automation.core.paths import (
    DEFAULT_KEEP_LATEST,
    LOGS_ROOT,
    SCREENSHOTS_ROOT,
    TMP_ROOT,
)
```

#### 6.3 删除清理目标中的 Allure 条目（第 86-87 行）

```python
# 改前
    targets = {
        "allure_results": ALLURE_RESULTS_ROOT,
        "allure_html": ALLURE_HTML_ROOT,
        "screenshots": SCREENSHOTS_ROOT,
        "logs": LOGS_ROOT,
    }

# 改后
    targets = {
        "screenshots": SCREENSHOTS_ROOT,
        "logs": LOGS_ROOT,
    }
```

---

### 7. `requirements.txt` — 1 处改动

#### 7.1 删除 `allure-pytest` 依赖（第 1 行）

```python
# 删除
allure-pytest>=2.13,<3
```

---

### 8. `docs/feature_file_check_adb_command.md`（可选）

第 276 行文档示例代码中的 `allure.step` 替换为普通注释，或直接删除该示例行。此改动不影响运行，可单独处理。

---

## 执行顺序

```
1. requirements.txt      → 删依赖声明
2. core/paths.py         → 删路径常量 + 工厂函数
3. core/cleanup.py       → 删 import + 清理目标
4. conftest.py           → 删 allure_report_dir 设置
5. ui_ops/operations.py  → 删 import + attach + 24 个 step
6. tests/test_excel_runner.py      → 删 import + feature + step
7. tests/test_performance/test_file_import.py → 删 import + feature
```

实际可按文件顺序自上而下执行，无相互阻塞。

---

## 验证步骤

```bash
# 1. 语法检查（每个修改过的文件）
python -m py_compile boox_automation/core/paths.py
python -m py_compile boox_automation/core/cleanup.py
python -m py_compile boox_automation/conftest.py
python -m py_compile boox_automation/ui_ops/operations.py
python -m py_compile boox_automation/tests/test_excel_runner.py
python -m py_compile boox_automation/tests/test_performance/test_file_import.py

# 2. 确认无残留引用
grep -rn "allure" boox_automation/ --include="*.py" | grep -v __pycache__ | grep -v ".pyc"

# 3. 跑一条冒烟用例确认框架正常
pytest boox_automation/tests/test_excel_runner.py -s -k "冒烟" --co 2>&1 | head -20

# 4. 卸载不再需要的包（可选）
pip uninstall allure-pytest
```

---

## 风险

- **零功能风险**：Allure 数据采集层只写文件，删除后不影响测试执行、飞书报告、截图、日志
- `artifacts/allure_results/` 和 `artifacts/allure_html/` 历史目录不会自动删除，需手动清理或等 cleanup 自然淘汰
