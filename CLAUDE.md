# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 跑 Excel 驱动用例（主入口）
pytest Note_Automation/Test_local_notes/test_excel_runner.py -s

# 按标签跑（china / abroad / increment / full_amount）
pytest -m "china and increment"

# 跑完整入口（带 Allure 报告生成 + 自动打开）
python Note_Automation/Test_local_notes/run_test_report.py

# 仅生成报告不运行测试
pytest --alluredir=Note_Automation/artifacts/allure_results/test_$(date +%Y%m%d%H%M%S)
allure generate -o Note_Automation/artifacts/allure_html/report_$(date +%Y%m%d%H%M%S) <allure_results_dir>

# 手动清理产物（保留最近 N 轮）
python -m Note_Automation.framework.cleanup

# 跳过指定用例
NOTE_DESELECT_NODEIDS="test_excel_runner.py::test_case[跳过]*" pytest
pytest --note-deselect="test_excel_runner.py::test_case[R5*"
```

## 架构概览

**依赖方向（自上而下）：**

```
conftest.py (pytest lifecycle, fixture, marker 注册)
    ↓
config.py (DriverProxy — WebDriver 代理，支持热切换)
    ↓
Note_class/Note_class.py (Operation_method — 14+ 种 Appium UI 操作，带超时重试)
    ↓
Test_local_notes/Public_method.py (业务流公共方法)
    ↓
Test_local_notes/test_excel_runner.py (Excel 驱动测试入口)
    ↓
excel_framework/ (parser → matcher → conditions → reporter)
```

**子包职责：**

| 目录 | 职责 |
|---|---|
| `excel_framework/` | Excel 驱动测试框架。`parser.py`=步骤解析；`matcher.py`=【】标签→元素匹配；`conditions.py`=前置条件检查；`executor.py`=用例执行；`reporter.py`=结果统计；`run.py`=独立运行入口；`elements.xlsx`=元素定义库；`test_cases.xlsx`=测试用例集 |
| `excel_runner/` | Excel runner 包标记，`test_excel_runner.py` 的归属包 |
| `Note_class/` | UI 操作引擎。`Note_class.py`=定位/点击/滑动/输入封装；`element_catalog.py`=locator 中文描述；`Logcat.py`=线程安全 Android 日志捕获；`Note_element/element_loader.py`=Excel 元素加载器（单例） |
| `Devices_list/` | ADB 设备信息采集（版本/指纹/分辨率/内存）+ 按平台拆分的设备型号 YAML 库 |
| `framework/` | `health.py`=Appium/ADB 健康检查；`paths.py`=集中路径常量；`cleanup.py`=产物轮换清理 |
| `Test_local_notes/` | 测试套件。`test_excel_runner.py`=主入口；`Public_method.py`=业务流公共方法；`run_test_report.py`=Allure 报告入口；`Test_performance_verify/`=性能测试 |

**关键设计决策：**

- **DriverProxy 代理模式** (`config.py`): 全项目通过 `from config import driver` 共享同一个 `DriverProxy` 实例。底层 real driver 断连后可热切换，避免 import 绑定失效。
- **智能重试装饰器** (`Note_class.py:retry_and_handle_exceptions`): 仅对 `TimeoutException / StaleElement / NoSuchElement / ElementNotInteractable` 重试。会话级异常直接抛出。
- **元素中文目录** (`element_catalog.py`): locator → 中文用途映射。`Operation_method` 失败时自动附加到错误日志和 Allure 截图标题。
- **产物集中管理** (`framework/paths.py` + `cleanup.py`): 所有运行时产物统一落到 `Note_Automation/artifacts/`。session 结束自动只保留最近 `NOTE_ARTIFACTS_KEEP_LATEST`（默认 5）轮。
- **无设备时干净退出** (`conftest.py:pytest_sessionstart`): 未检测到已连接设备时打印一行简短提示后 `pytest.exit()`，PyCharm 测试树不出现红色节点。
- **Excel 驱动测试** (`excel_framework/`): 测试用例和元素定义存储在 Excel 文件中，通过 `【】` 标记引用元素。支持优先级筛选、前置条件自动跳过、设备适配。
- **用例级重试** (`pytest.ini`): 集成 `pytest-rerunfailures`，失败用例自动重试 2 次。
- **前置条件运行时检查**: 条件检查在 `test_case` 执行时进行（非模块加载时），使用当前真实设备信息。

## 环境变量

| 变量 | 作用 |
|---|---|
| `APPIUM_HOST` / `APPIUM_PORT` | Appium 服务地址（默认 `127.0.0.1:4723`） |
| `APPIUM_START_CMD` | 自动拉起 Appium 的命令 |
| `NOTE_DEVICE_ID` | 多设备时显式指定目标设备 |
| `NOTE_DESELECT_NODEIDS` | 跳过指定用例（逗号/分号/换行分隔，支持 fnmatch） |
| `NOTE_ARTIFACTS_ROOT` | 产物根目录（默认 `Note_Automation/artifacts`） |
| `NOTE_ARTIFACTS_KEEP_LATEST` | 每类产物保留多少轮（默认 5） |
| `RUN_INCREMENTAL` | 入口脚本默认 `1`=增量回归；`0`=全量 |

## 开发约定

- **写 Excel 测试用例**：直接编辑 `excel_framework/test_cases.xlsx`，参考 `excel_framework/使用指南.md`
- **定义元素**：编辑 `excel_framework/elements.xlsx`，每个 Sheet 对应一个页面
- **新增业务流方法**：加在 `Public_method.py`，只通过 `Operation_method` 暴露的 API 操作 UI
- **新增/修改 locator**：同步在 `element_catalog.py` 补一行中文描述，方便失败排错
- **产物路径**：使用 `framework.paths` 提供的工厂方法，不要硬编码路径
- **新增 Python 测试用例**：放在 `Test_local_notes/`，用 `@note_mark_china` / `@note_mark_increment` 等装饰器贴标签

## 协作规则

- **先给方案再动手**：任何代码修改先出方案等确认，用户明确同意后再执行
- **不确定必须确认，禁止盲写**：对需求场景、使用方式、设计选择有任何不确定时，必须先停下来和用户确认
- **改完必须验证**：每次代码修改后跑语法检查，确认无报错再答复
- **截图无法查看时用数值分析**：大尺寸 RGBA PNG 用 PIL+numpy 分析像素值来判断画面内容
