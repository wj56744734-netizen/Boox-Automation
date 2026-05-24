# Note Automation

文石（BOOX）笔记应用的端到端自动化测试框架，基于 **pytest + Appium + Allure**。
覆盖手写笔记、文本笔记、会议笔记、本地文件导入、批量管理、常规菜单（移动/复制/重命名/删除/收藏）、ksync 同步等核心场景，约 30 条用例。

## 主要特性

- **多平台标签**：用例按 `china` / `abroad` 区分国内外设备；按 `increment` / `full_amount` 区分增量回归 / 全量回归
- **集中的元素稳定层**：`Operation_method` 封装了 14+ 种定位/点击 / 长按 / 滑动方法，所有底层等待都带超时重试 + 智能异常分类（仅对 `TimeoutException / StaleElement` 等可重试异常重试，会话级异常直接抛）
- **失败可读**：失败时自动按 `Note_class/element_catalog.py` 查元素中文用途附到错误日志和 Allure 截图标题
- **产物集中管理**：所有运行时产物（Allure 结果、截图、临时文件）落到 `Note_Automation/artifacts/` 一处，会话结束自动只保留最近 N 轮
- **无设备时干净退出**：未连接设备直接以一行简短提示退出，PyCharm 测试树不出现红色"test setup failed"节点
- **支持用例忽略**：通过环境变量 `NOTE_DESELECT_NODEIDS` 或命令行 `--note-deselect` 灵活过滤

## 项目结构

```
Note_Automation/
├── Devices_list/          # adb 设备探测 + 设备型号映射
├── Note_class/            # 核心元素操作类（Operation_method + Logcat）
│   ├── Note_class.py
│   ├── Logcat.py
│   └── element_catalog.py # locator → 中文用途映射，失败时自动附加描述
├── Test_local_notes/      # 主测试套件
│   ├── Public_method.py   # 业务流公共方法
│   ├── run_test_report.py # 测试入口（生成 Allure 报告）
│   ├── test_create_notes.py
│   ├── test_import_the_file.py
│   ├── test_batch_management.py
│   ├── test_regular_menu.py
│   ├── test_ksync_note.py
│   └── test_note_omitted_issues.py
├── framework/             # 框架级基建
│   ├── health.py          # Appium / adb 健康检查
│   ├── paths.py           # 集中路径常量 + 工厂方法
│   └── cleanup.py         # 产物清理（保留最近 N 轮）
├── scripts/
│   ├── tools/             # 设备工具脚本（电池/CPU/内存/重启）
│   └── Note_page_contrast/# 页面比对（OpenCV，可选模块）
├── artifacts/             # 所有运行产物（gitignored）
│   ├── allure_results/
│   ├── allure_html/
│   ├── screenshots/
│   └── tmp/
├── config.py              # DriverProxy + Appium driver 初始化
├── conftest.py            # pytest 配置、fixture、设备前置检查
└── pytest.ini             # 日志格式 + marker 注册
```

## 环境要求

- **Python**：3.10 及以上
- **Appium Server**：2.x，默认端口 `127.0.0.1:4723`
- **Allure CLI**：用于生成 HTML 报告（`allure generate`）
- **Android 设备**：已开启 USB 调试，能在 `adb devices` 中识别
- **目标应用**：文石笔记 `com.onyx.android.note`

## 快速开始

### 1. 克隆并准备虚拟环境

```bash
git clone <your-repo-url> note_automation
cd note_automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 启动 Appium

```bash
appium --address 127.0.0.1 -p 4723 --session-override
```

> 也可设置环境变量 `APPIUM_START_CMD` 让框架自动拉起 Appium。

### 3. 连接设备并核对

```bash
adb devices              # 确保目标设备 device 状态
adb shell wm size        # 确认能与设备交互
```

### 4. 运行测试

```bash
# 跑单条用例
pytest Note_Automation/Test_local_notes/test_create_notes.py::Test_create_notes::test_1_create_handwritten_note

# 按标签跑（国内 + 增量）
pytest -m "china and increment"

# 跑完整入口（带 Allure 报告生成）
python Note_Automation/Test_local_notes/run_test_report.py
```

## 测试标签

| Marker | 含义 |
| --- | --- |
| `china` | 国内设备相关用例 |
| `abroad` | 海外设备相关用例 |
| `increment` | 增量回归集（每日跑） |
| `full_amount` | 全量回归集（发版前跑） |
| `test` | 通用标签 |

## 环境变量

| 变量 | 默认 | 作用 |
| --- | --- | --- |
| `APPIUM_HOST` | `127.0.0.1` | Appium 服务地址 |
| `APPIUM_PORT` | `4723` | Appium 端口 |
| `APPIUM_START_CMD` | `appium --address ... -p ... --session-override` | 自动拉起命令 |
| `NOTE_DEVICE_ID` | 自动选第一个 | 多设备场景显式指定 |
| `NOTE_DESELECT_NODEIDS` | `""` | 跳过指定用例（逗号分隔，支持 fnmatch） |
| `NOTE_ARTIFACTS_ROOT` | `Note_Automation/artifacts` | 产物根目录 |
| `NOTE_ARTIFACTS_KEEP_LATEST` | `5` | 每类产物保留多少轮 |
| `RUN_INCREMENTAL` | `1` | 入口默认增量；`0` 跑全量 |
| `AUTO_OPEN_REPORT` | `1` | 测试完是否自动打开 Allure 报告 |

## 产物管理

所有产物（Allure 结果、HTML 报告、失败截图、临时文件）统一落在 `Note_Automation/artifacts/` 下：

```
artifacts/
├── allure_results/Test_<timestamp>/    pytest --alluredir 写入
├── allure_html/Test_html_<timestamp>/  allure generate 输出
├── screenshots/<YYYY-MM-DD>/           失败截图（按日期分组）
└── tmp/                                临时文件（清理时全清）
```

每次 pytest 会话结束自动调用 `framework.cleanup.cleanup_artifacts()`，按修改时间倒序保留最近 N 轮。也可手动清理：

```bash
python -m Note_Automation.framework.cleanup
```

## 元素中文描述

`Note_class/element_catalog.py` 维护了项目中常用 locator 的中文用途字典：

```python
ELEMENT_DESCRIPTIONS = {
    "com.onyx.android.note:id/back_icon": "笔记画布：返回按钮",
    "com.onyx:id/button_positive": "通用对话框：确定按钮",
    # ...
}
```

当 `Operation_method` 重试失败时，日志和 Allure 截图标题会自动附上"元素用途"，例如：

```
ERROR xpath_check_timeout(back_icon) 在 3 次重试后仍失败，元素用途: 笔记画布：返回按钮
```

新增 UI 元素时按需补一行；未登记的 locator 不影响功能。

## 常见提示

| 现象 | 原因 |
| --- | --- |
| `Exit: 未检测到已连接设备（…），请连接设备后再运行测试` | adb 看不到任何设备。先 `adb devices` 排查 |
| `Appium 未连接或会话异常` | Appium 进程没起，或 Appium 4723 端口被占用 |
| 某 `test setup failed` | fixture 阶段失败（多半是 driver 探活或 HOME 按键失败）；日志里有具体原因 |
| 用例真业务断言失败 | 装饰器会保存失败截图到 `artifacts/screenshots/<日期>/` |

## 开发约定

- 新增测试用例：放在 `Test_local_notes/`，用 `@note_mark_china` / `@note_mark_increment` 等装饰器贴标签
- 新增业务流：在 `Public_method.py` 添加方法；只用 `Operation_method` 暴露的 API
- 新增/修改 locator：同步在 `element_catalog.py` 补描述，便于失败排错
- 产物路径：使用 `framework.paths` 提供的 `safe_screenshot_path / tmp_path / new_allure_results_dir` 等工厂方法，不要硬编码路径

## License

内部项目，未公开授权。
