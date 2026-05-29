# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 跑单条用例
pytest Note_Automation/Test_local_notes/test_create_notes.py::Test_create_notes::test_1_create_handwritten_note

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
NOTE_DESELECT_NODEIDS="test_batch_management.py::test_92*" pytest
# 或
pytest --note-deselect="test_batch_management.py::test_92*"
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
Test_local_notes/Public_method.py (业务流公共方法，继承 Operation_method)
    ↓
Test_local_notes/test_*.py (测试用例，依赖 Public_method + conftest fixture)
```

**关键设计决策：**

- **DriverProxy 代理模式** (`config.py`): 全项目通过 `from config import driver` 共享同一个 `DriverProxy` 实例。底层 real driver 断连后可热切换，避免 import 绑定失效。`driver` 变量是全局单例，`__getattr__` 转发所有属性访问到真实 WebDriver。
- **智能重试装饰器** (`Note_class.py:retry_and_handle_exceptions`): 仅对 `TimeoutException / StaleElement / NoSuchElement / ElementNotInteractable` 重试。`InvalidSessionIdException` 等会话级异常直接抛出。另外通过关键字匹配兜底不同 Appium/Selenium 版本的 session 异常类名差异。
- **元素中文目录** (`element_catalog.py`): 维护 locator → 中文用途映射。`Operation_method` 失败时自动查找元素描述附加到错误日志和 Allure 截图标题，无需测试用例显式传参。
- **产物集中管理** (`framework/paths.py` + `cleanup.py`): 所有运行时产物（Allure 结果/报告、截图、临时文件）统一落到 `Note_Automation/artifacts/`。session 结束自动按修改时间倒序只保留最近 `NOTE_ARTIFACTS_KEEP_LATEST`（默认 5）轮。
- **无设备时干净退出** (`conftest.py:pytest_sessionstart`): 未检测到已连接设备时打印一行简短提示后 `pytest.exit()`，PyCharm 测试树不出现红色 "test setup failed" 节点。

**子包职责：**

| 目录 | 职责 |
|---|---|
| `Note_class/` | UI 操作引擎。`Note_class.py` = 定位/点击/滑动/输入封装；`element_catalog.py` = locator 中文描述；`Logcat.py` = 线程安全 Android 日志捕获 |
| `Devices_list/` | ADB 设备信息采集（版本/指纹/分辨率/内存）+ 多型号映射表 |
| `framework/` | `health.py` = Appium/ADB 健康检查；`paths.py` = 集中路径常量；`cleanup.py` = 产物轮换清理 |
| `Test_local_notes/` | 主测试套件 + `Public_method.py` 业务流 + `run_test_report.py` 入口 |
| `scripts/tools/` | 独立辅助脚本（电池/CPU/内存监控、反复重启） |
| `scripts/Note_page_contrast/` | OpenCV UI 截图对比（可选模块） |

## 环境变量

| 变量 | 作用 |
|---|---|
| `APPIUM_HOST` / `APPIUM_PORT` | Appium 服务地址（默认 `127.0.0.1:4723`） |
| `APPIUM_START_CMD` | 自动拉起 Appium 的命令 |
| `NOTE_DEVICE_ID` | 多设备时显式指定目标设备 |
| `NOTE_DESELECT_NODEIDS` | 跳过指定用例（逗号/分号/换行分隔，支持 fnmatch） |
| `NOTE_ARTIFACTS_ROOT` | 产物根目录（默认 `Note_Automation/artifacts`） |
| `NOTE_ARTIFACTS_KEEP_LATEST` | 每类产物保留多少轮（默认 5） |
| `RUN_INCREMENTAL` | 入口脚本默认 `1` = 增量回归；`0` = 全量 |

## 开发约定

- 新增测试用例放在 `Test_local_notes/`，用 `@note_mark_china` / `@note_mark_abroad` / `@note_mark_increment` / `@note_mark_full_amount` 装饰器贴标签
- 新增业务流方法加在 `Public_method.py`，只通过 `Operation_method` 暴露的 API 操作 UI
- 新增/修改 locator 时同步在 `element_catalog.py` 补一行中文描述，方便失败排错
- 产物路径使用 `framework.paths` 提供的工厂方法（`safe_screenshot_path` / `tmp_path` / `new_allure_results_dir` 等），不要硬编码路径
