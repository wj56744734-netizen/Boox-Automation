# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 跑 Excel 驱动用例（主入口，默认云端加载）
pytest boox_automation/tests/test_excel_runner.py -s

# 本地 Excel 离线模式
USE_LOCAL_EXCEL=1 pytest boox_automation/tests/test_excel_runner.py -s

# 子模块筛选（只跑指定模块的 P0 用例）
NOTE_TEST_MODULES=笔记首页,手写笔记 pytest boox_automation/tests/test_excel_runner.py -s

# 按标签跑（china / abroad / increment / full_amount）
pytest -m "china and increment"

# 带 Allure 报告
python boox_automation/scripts/run_report.py

# 仅生成报告不运行测试
pytest --alluredir=boox_automation/artifacts/allure_results/test_$(date +%Y%m%d%H%M%S)
allure generate -o boox_automation/artifacts/allure_html/report_$(date +%Y%m%d%H%M%S) <allure_results_dir>

# 提取当前页面的精简 XML（直接运行 → 自动保存到 artifacts/page_xml/当前时间.xml）
python boox_automation/scripts/extract_page_xml.py

# 打印到终端
python boox_automation/scripts/extract_page_xml.py --stdout

# 离线处理 Inspector 导出的文件
python boox_automation/scripts/extract_page_xml.py --from-file ~/Desktop/page.xml

# 手动清理产物（保留最近 N 轮）
python -m boox_automation.core.cleanup

# 跳过指定用例
NOTE_DESELECT_NODEIDS="test_excel_runner.py::test_case[跳过]*" pytest
```

## 环境配置

```bash
# 安装依赖（macOS / Windows 通用）
pip install -r requirements.txt
```

**跨平台兼容**：飞书 API 调用使用 Python `requests` 库，无需安装 `curl`。Windows/Linux/macOS 开箱即用。

飞书凭证（app_id/secret/token）已内置在 `config.yaml` 中，无需额外配置。仅离线模式需设置 `USE_LOCAL_EXCEL=1`。

## 项目结构

项目根目录还包含 `pytest.ini`、`config.yaml` 等配置文件。

```
boox_automation/
├── driver.py                DriverProxy — WebDriver 代理，支持热切换
├── conftest.py              pytest lifecycle、fixture、marker 注册
│
├── engine/                  测试引擎（纯代码）
│   ├── parser.py            步骤解析 + 前置条件检查
│   ├── elements.py          元素加载 + 元素匹配 + 预期结果加载
│   ├── reporter.py          结果统计
│   └── xml_checker.py       XML 签名提取 + 对比引擎
│
├── core/                    基础设施
│   ├── config.py            配置读取（config.yaml → 便捷函数）
│   ├── feishu.py            飞书 API 客户端
│   ├── health.py            Appium/ADB 健康检查
│   ├── paths.py             产物路径管理
│   └── cleanup.py           产物轮换清理
│
├── data/                    数据文件（和代码分离）
│   ├── elements.xlsx        元素定义
│   └── test_cases.xlsx      测试用例
│
├── ui_ops/                  UI 操作层
│   ├── operations.py        14+ 种 Appium UI 操作，带超时重试
│   ├── element_catalog.py   locator → 中文描述
│   └── logcat.py            线程安全 Android 日志捕获
│
├── devices/                 设备管理
│   ├── info.py              ADB 设备信息采集
│   ├── registry.py          设备型号注册表
│   └── models/              设备型号 YAML 库
│
├── tests/                   测试用例
│   ├── test_excel_runner.py pytest 主入口
│   ├── helpers.py           笔记业务流公共方法
│   ├── test_file_import.py  文件导入测试
│   └── performance/         性能测试
│
└── scripts/                 独立运行入口
    └── run_report.py        Allure 报告入口
```

## 架构概览

**依赖方向（自上而下）：**

```
config.yaml              ← 所有可调参数集中管理
    ↓
core/config.py           ← 配置加载器，提供便捷函数
    ↓
core/feishu.py           ← 飞书 API（依赖 config.py）
    ↓
engine/elements.py       ← 元素加载 + 匹配（云端优先）
    ↓
engine/parser.py         ← 步骤解析（无内部依赖）
    ↓
tests/test_excel_runner  ← pytest 入口
```
**关键设计决策：**

- **缓存优先加载**：元素和用例默认先尝试飞书云端，成功后自动缓存到 `data/.cache/`；下次启动优先用缓存（24h 有效），后台检查连通性决定是否刷新。`USE_LOCAL_EXCEL=1` 回退到本地 `data/` 下的 xlsx 文件。三级回退链：云端 → 缓存 → 本地 Excel。
- **用例和元素分离**：两个独立飞书表格 token（`feishu.test_case_token` / `feishu.elements_token`），支持用例多 sheet 列表加载。
- **用例运行时完整性校验** (`validate_case()`)：每条用例执行前检查步骤号是否重复、`【】` 标记的元素是否都能匹配到。有问题则跳过并打印 WARNING 日志，不再静默执行不完整的用例。
- **操作加固机制** (`Base_note_class`)：所有点击/长按/输入后统一 `_settle_ui()` 沉降等待；dismiss 弹窗后 `wait_popup_gone()` 轮询验证消失（3s × 2次重试）；输入后回读验证文本正确性。
- **配置集中**：所有可调参数统一在 `config.yaml`，通过 `core/config.py` 的便捷函数读取。环境变量自动覆盖配置文件。
- **数据代码分离**：Excel 数据文件放在 `data/`，不和代码混放。
- **DriverProxy 代理模式** (`driver.py`)：全项目通过 `from boox_automation.driver import driver` 共享同一实例。底层 real driver 断连后可热切换。
- **智能重试装饰器** (`operations.py:retry_and_handle_exceptions`)：仅对 `TimeoutException / StaleElement / NoSuchElement / ElementNotInteractable` 重试，会话级异常直接抛出。重试次数从 config.yaml 读取。
- **元素中文目录** (`element_catalog.py`)：locator → 中文用途映射。失败时自动附加到错误日志和 Allure 截图标题。
- **产物集中管理** (`core/paths.py` + `cleanup.py`)：运行时产物统一落到 `artifacts/`，session 结束自动保留最近 N 轮。
- **无设备时干净退出** (`conftest.py`)：未检测到设备时打印提示后 `pytest.exit()`，PyCharm 测试树不出现红色节点。
- **用例级重试** (`pytest.ini`)：集成 `pytest-rerunfailures`，失败用例自动重试 2 次。
- **前置条件运行时检查**：条件检查在 `test_case` 执行时进行，使用当前真实设备信息。

## 配置体系

所有配置集中在项目根目录 `config.yaml`，通过 `boox_automation.core.config` 读取：

```python
from boox_automation.core.config import get_int, get_str, get_bool
# 或直接使用预定义的便捷函数
from boox_automation.core.config import timeout_default, retry_max_attempts
```

**配置优先级**：环境变量 > config.yaml > 代码默认值

| 分组 | 主要配置项 |
|---|---|
| `timeout` | default, xml_element_wait, app_launch |
| `retry` | max_attempts, delay, element_click, stale_element_delay |
| `appium` | host, port, startup_timeout, capabilities |
| `adb` | device_ready_retries, command_retries 及对应 delay |
| `excel` | test_case_sheet, priority_filter, test_case_file, elements_file, columns（列索引） |
| `feishu` | app_id/secret, test_case_token, elements_token, test_case_sheets, element_sheet_prefix, curl_timeout |
| `logcat` | capture_timeout |
| `screenshot` | dir, prefix, enabled |
| `toast` | timeout, retry, retry_delay |
| `cleanup` | keep_latest |
| `cache` | max_age_seconds（缓存有效期，默认86400=24h）, dir（缓存目录） |
| `driver` | failure_threshold |
| `project` | name, driver_import_path |

## 环境变量

| 变量 | 作用 |
|---|---|
| `APPIUM_HOST` / `APPIUM_PORT` | Appium 服务地址（默认 `127.0.0.1:4723`） |
| `APPIUM_SERVER_URL` | 完全自定义 Appium URL |
| `APPIUM_START_CMD` | 自动拉起 Appium 的命令 |
| `NOTE_DEVICE_ID` | 多设备时显式指定目标设备 |
| `NOTE_DESELECT_NODEIDS` | 跳过指定用例 |
| `NOTE_TEST_MODULES` | 逗号分隔，筛选 C 列模块 |
| `NOTE_ARTIFACTS_ROOT` | 产物根目录 |
| `NOTE_ARTIFACTS_KEEP_LATEST` | 每类产物保留轮数 |
| `USE_LOCAL_EXCEL` | `1`=使用本地 xlsx，默认从飞书加载 |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 覆盖飞书应用凭证 |
| `FEISHU_TEST_CASE_TOKEN` / `FEISHU_ELEMENTS_TOKEN` | 覆盖表格 token |
| `NOTE_TEST_CASE_SHEETS` | 覆盖用例 sheet 列表（逗号分隔） |
| `FEISHU_ELEMENT_SHEET_PREFIX` | 覆盖元素 sheet 前缀筛选 |

## 开发约定

- **写测试用例**：编辑飞书表格（云端）或 `data/test_cases.xlsx`（本地）
- **定义元素**：编辑飞书表格（云端）或 `data/elements.xlsx`（本地），每个 Sheet 对应一个页面
- **新增业务流方法**：加在 `tests/helpers.py`，只通过 `Operation_method` 暴露的 API 操作 UI
- **新增/修改 locator**：同步在 `ui_ops/element_catalog.py` 补中文描述
- **产物路径**：使用 `core/paths.py` 工厂方法，不硬编码
- **新增 Python 测试用例**：放在 `tests/`，用 `@note_mark_china` / `@note_mark_increment` 等装饰器贴标签
- **新增配置项**：加在 `config.yaml` + `core/config.py` 便捷函数
- **新增用例模块**：在飞书用例表中新建 sheet，`config.yaml` 的 `feishu.test_case_sheets` 列表加一行

## 元素表规范

元素定义在飞书表格（云端）或 `data/elements.xlsx`（本地），每个 Sheet 对应一个页面。第 1 行为注释行（含完整使用说明），第 2 行为表头（支持中英文），第 3 行起为数据。

**6 列结构（原 overrides / dismiss_with / checks 列已移除）：**

| 中文表头 | 英文兼容 | 必填 | 说明 |
|---|---|---|---|
| 元素标识 | key | ✓ | 格式 `页面名.元素名`，全局唯一 |
| 匹配文本 | match | | 测试步骤中 `【】` 内的文字 |
| 定位方式 | locator | ✓ | XPath 或纯文本，支持多设备「键：」分块 |
| 操作类型 | action | | 中文值，不填自动推断 |
| 用途说明 | operation | | 日志/截图中的元素描述 |
| 序号 | index | | 同 match 多元素时区分 |

**操作类型（中文）：**

| 值 | 说明 | locator 格式 |
|---|---|---|
| `点击` | 点击元素（**默认值**） | XPath |
| `输入` | 输入文本 | `XPath,输入文本` 逗号分隔，逗号前为输入框定位，逗号后为要输入的文本 |
| `长按` | 长按元素 | XPath |
| `校验toast` | 校验 Toast 提示 | XPath |
| `点击坐标` | 按屏幕比例坐标点击 | `x,y` 如 `0.5,0.3` |
| `长按坐标` | 按屏幕比例坐标长按 | `x,y` 如 `0.5,0.3` |
| `滑动` | 按屏幕比例坐标滑动 | `x1,y1,x2,y2` 如 `0.7,0.5,0.3,0.5` |

`assert`/`assert_not`/`assert_text`/`dismiss` — **已废弃**，页面/弹窗验证统一由 I 列预期结果完成。

**步骤关键词 → 动作映射（用例 H 列）：**

| 步骤关键词 | 动作 | 需 `【】` 元素匹配 |
|---|---|---|
| 点击/打开/进入/选择/双击/退出/返回/清空/确认/关闭 | `点击` | 是 |
| 输入 | `输入` | 是，locator 为 `XPath,输入文本` |
| 长按 | `长按` | 是 |
| 点击坐标 | `点击坐标` | 是，locator 为 `x,y` |
| 长按坐标 | `长按坐标` | 是，locator 为 `x,y` |
| 滑动 | `滑动` | 是，locator 为 `x1,y1,x2,y2` |
| 上滑/向上滑动/下滑/向下滑动/左滑/向左滑动/右滑/向右滑动 | 方向滑动 | **否**，纯关键词触发 |
| 按返回键/返回键 | 系统返回键 | **否**，纯关键词触发 |
| 检查/查看/校验（步骤开头） | 跳过 | —，I 列预期结果接管 |

方向滑动和返回键是设备级硬编码操作，直接写关键词即可，**不要加 `【】`**。例如 `向下滑动`、`按返回键`。

**多设备格式（locator 列内联，和预期结果 C 列统一）：**

```
默认 XPath（所有设备兜底，必填，放在最前面）

阅读器：
//阅读器专用 XPath

海外：
//海外专用 XPath
```

- 不带前缀的块 = 默认，**必填**，放在最前面
- `键：` 开头 = 设备专属，覆盖默认
- 支持的键：`国内` `海外` `全球` `平板` `阅读器` `6` `7.8` `10.3` `13.3` 及版本号。组合键逗号分隔：`平板, 国内`
- 匹配逻辑：条件匹配最多的优先，无匹配回退默认
- 仅有条件块无默认块 → 加载 WARNING

## 预期结果规范

H/I 列职责分离：**H 列只做操作，I 列只做断言**。页面/弹窗验证统一在 I 列通过预期结果完成。

用例 I 列格式：包含 `【预期结果匹配文本】` 即可，位置不限。不含 `【】` 的行视为文档描述跳过，I 列为空不检查（兼容老用例）。

关联方式：执行时 H 列 `检查【X】` 自动去 I 列找包含 `【X】` 的行，按出现顺序一一对应。
H 列 `检查【X】` 在 I 列找不到匹配 → 报错终止该条用例。
I 列的 `【X】` 在 H 列没有对应 `检查` → WARNING 提示，不阻断。

**五种模式（行尾后缀区分）：**

| I 列格式 | check_mode | 执行逻辑 | 需预期结果 sheet |
|---|---|---|---|
| `【{key}】` | visible | C列XML对比 或 D列XPath检查（预期存在） | 是 |
| `【{key}】不可见` | not_visible | C列XML对比 或 D列XPath检查（预期不存在） | 是 |
| `【{key}】不存在` | not_visible | 同上 | 是 |
| `【{text}】toast提示` | toast | `wait_check_toast(toast_true=)` | 否 |
| `【{text}】toast不出现` | toast_not | `wait_check_toast(toast_false=)` | 否 |

### 预期结果 Sheet（飞书元素表中 `预期结果` sheet，5 列 A-E）

| 列 | 中文名 | 说明 | 必填 |
|---|---|---|---|
| A | 元素标识 | 唯一 key，格式 `页面.页面状态` | ✓ |
| B | 匹配文本 | I 列 `【】` 通过此列关联 | ✓ |
| C | 页面XML | 从 Appium Inspector 导出，支持多设备「键：」分块 | C/D 二选一 |
| D | 检查元素 | XPath 选择器，每行一个，支持多设备「键：」分块 | C/D 二选一 |
| E | 用途说明 | 人类可读描述（不影响执行） | |

### 校验优先级

```
1. toast 模式 → wait_check_toast
2. D列 (检查元素) 非空 → 元素级 XPath 逐条检查
3. C列 (页面XML) 非空 → 全页面 XML 签名对比（现有逻辑）
4. C/D 都空 → 查找本地文件 data/expected_pages/{key}.xml
   ├─ 文件存在 → 读取内容 → XML 签名对比
   └─ 文件不存在 → WARNING 跳过
```

### C 列 — 页面XML

从 Appium Inspector 导出（使用 `scripts/extract_page_xml.py` 精简后粘贴）。

**填写方式（两种任选）：**

1. **内联文本**：将 `<hierarchy>` XML 文本直接粘贴到单元格
   ```bash
   python boox_automation/scripts/extract_page_xml.py --stdout | pbcopy
   ```

2. **本地文件引用**（C 列为空时自动回退）：将 XML 保存到 `data/expected_pages/{key}.xml`
   ```bash
   python boox_automation/scripts/extract_page_xml.py --stdout > \
     boox_automation/data/expected_pages/手写笔记.创建页.xml
   ```

**多设备格式（和元素 C 列统一）：**

```
默认 XML（所有设备兜底，必填，放最前面）
<hierarchy>...</hierarchy>

国内：
<hierarchy>...</hierarchy>

海外：
<hierarchy>...</hierarchy>
```

对比只看 `(class_name, resource_id)`，text 差异 INFO 报告不影响结果。

### D 列 — 检查元素

**格式**：每行一个 XPath 选择器，可选附加期望文本 `,期望文本`，支持多设备「键：」分块。

```
// 仅检查元素存在
//android.widget.TextView[@resource-id="com.onyx:id/title" and @text="手写笔记"]

// 检查元素存在 + 文本对比（逗号后为期望文本）
//android.widget.TextView[@resource-id="com.onyx.android.note:id/tv_title"],请在录音或转写文字完成后，再使用导出功能

国内：
//android.widget.TextView[@resource-id="com.onyx:id/title" and @text="手写笔记"]

海外：
//android.widget.TextView[@resource-id="com.onyx:id/title" and @text="Handwriting"]
```

**执行逻辑**：

| I 列模式 | D 列检查逻辑 |
|---|---|
| `visible`（默认） | 所有 XPath 都能找到 → pass；未找到或文本不匹配 → fail |
| `not_visible` / `不存在` / `不可见` | 所有 XPath 都找不到 → pass，任一找到 → fail |

检查步骤：1) `find_element` 找元素 → 2) 如有「,期望文本」则对比 `element.text`。

### 弹窗验证方式

```
H 列: click【关闭按钮】              → 普通点击关闭
I 列: 【弹窗内容】                   → XML 对比或 XPath 检查（弹窗存在时）
     【关闭后页面状态】               → XML 对比或 XPath 检查（弹窗消失后）
```

关闭按钮作为普通元素定义在元素表中（action=click），弹窗存在/消失状态各对应一条预期结果。

## Python 版本

项目运行在 Python 3.9。`list | None` 等新语法需配合 `from __future__ import annotations`。

## 飞书 API

- **富文本单元格**：带格式文本 API 返回 segment 数组。`read_sheet_by_name()` 已加 `?valueRenderOption=ToString` + segment 展平兜底。
- **写 API**：`write_sheet_values()` / `get_sheet_id()` 已实现，需 app 编辑权限。
- **缓存**：`data/.cache/` 下自动缓存，`check_feishu_reachable()` 快速连通检查（3s）。

## BUG 排查规范

### 错误日志格式

每次操作失败都会产生结构化错误日志：

```
ERROR  function_name(params) 在 N 次重试后仍失败
  ↳ 定位:   当前操作的定位器（xpath / id 等）
  ↳ 元素键: 飞书元素表中的 key（格式：页面.元素名）
  ↳ YAML:   元素来源文件 + 行号
  ↳ 调用链: 从用例入口到失败点的完整函数调用链
  ↳ 触发位置: 代码文件和行号
  ↳ 截图: 失败时刻的屏幕截图路径
```

`↳ 定位` 展示的是**元素本身的 locator**（来自元素表），不一定是 check_multi_elements 中每条 check 的定位器。两者不同时需分别检查。

**核心原则：时间最早的 ERROR 是根因，后面的通常是级联失败。**

### 排查流程

**第 1 步：读元素定义（关键，最先做）**

```bash
python3 -c "
import json
with open('boox_automation/data/.cache/elements.json') as f:
    data = json.load(f)
sheets = data['data']['sheets']
# 用元素键中的页面名和元素名查找
k = '页面名.元素名'
for s_name, sheet in sheets.items():
    if k in sheet:
        print(json.dumps(sheet[k], ensure_ascii=False, indent=2))
"
```

拿到实际配置后，重点关注：
- **locator**：定位器是否合法（XPath 必须以 `//`、`/` 或 `(` 开头）
- **_locator_blocks**：多设备块中当前设备匹配了哪个键

**第 2 步：读失败函数的源码**

根据 `↳ 触发位置` 找到调用方代码，再用函数名在 `ui_ops/operations.py` 中定位实际实现。重点关注：
- 用的是 `check_timeout`（要求 clickable）还是 `check_display_timeout`（仅要求可见）——纯展示文本不可点击
- `_xpath_text()` 生成的 XPath 是 `normalize-space(@text)='...'` 精确匹配 + `contains()` 兜底

**第 3 步：查看截图**

打开 `↳ 截图:` 指向的 PNG，确认失败时刻屏幕实际状态。截图路径格式：
`boox_automation/artifacts/screenshots/YYYY-MM-DD/HHmmss_<函数名>_<定位信息>.png`

**第 4 步：对比报错定位器 vs 元素表配置**

错误日志中的 `↳ 定位` 是实际传给函数的定位器值。把它和元素表中的 locator 逐条对比，确认**脚本实际在用哪个定位器**。

**第 5 步：判断根因类别**

| 类别 | 典型信号 | 排查方向 |
|---|---|---|
| XPath 语法错误 | 报错信息含 `InvalidSelectorException` 或 `XPath` 相关错误 | 检查元素表 locator 中每个 XPath 是否以 `//` 开头 |
| 元素不可点击 | `check_timeout` / `xpath_element_is_clickable` 失败，Inspector 可见 | `check_timeout` 用 `EC.element_to_be_clickable`，纯展示文本（TextView label）可能只可见不可点击 |
| 元素确实不存在 | 截图 + Inspector 都找不到该元素 | UI 变更，更新元素表 locator 或多设备块 |
| 弹窗/引导已关闭 | 非首次进入，引导不再弹出 | 用前置条件跳过或用 I 列 not_visible 模式验证 |
| 级联失败 | 调用链中有多个不同函数，后有 quit/back 不可点击 | 往前找第一个 ERROR，修复后级联自动消失 |

### 常见根因速查

| 现象 | 常见根因 | 优先动作 |
|---|---|---|
| 国内 pass、海外 fail | 缺少海外版多设备块 | locator 列加 `海外：` 块 |
| 某设备型号专属 | 缺少设备适配块 | locator 列加对应键的块 |
| XML 对比失败 | 预期 XML 过期或页面变更 | 重新用 extract_page_xml.py 提取 |
| I 列 toast 不生效 | 忘记加 `toast提示` 后缀 | 检查 I 列格式 |
| Driver/Appium 报错 | session 断开 | 重启 Appium，检查设备连接 |

### 改后验证

- 飞书元素表修改 → 重跑对应失败用例，确认从 FAILED 变 PASSED
- locator 多设备块修改 → 同时跑该 sheet 下其他用例确保无回归
- 测试步骤修改 → 先跑增量（`-m increment`），再跑全量回归
- 任何代码修改后 → `python -m py_compile <文件>` 检查语法

## 协作规则

- **风险操作先确认**：以下操作必须先说明风险、给方案，等用户确认后再执行：
  - 写入外部系统（飞书表格、数据库、API）
  - 删除或移动文件/数据
  - 修改共享配置（config.yaml、pytest.ini、.gitignore 等）
  - 大范围重构或跨多个文件的结构性改动
  - 执行不可逆命令（git push、rm、数据库变更）
  - 不确定是否有风险时，按有风险处理，主动提问确认
- **先给方案再动手**：任何代码修改先出方案等确认，用户明确同意后再执行。**涉及以下变更时，方案必须写明具体的格式/语法/字段名，不能只写大方向：**
  - 元素表格式（locator 列多设备块格式等）
  - 测试用例格式（操作步骤、预期结果等列的语法）
  - 配置文件结构（config.yaml 键名和值格式）
  - 飞书表格结构（sheet 名、列名、列顺序）
  - API 接口（参数名、返回值格式）
- **规范修改必须同步所有数据源**：修改任何格式规范后，必须同步更新以下**所有**位置，缺一不可：
  - `CLAUDE.md` 中的对应规范说明
  - **飞书元素表**：各 sheet 的第 1 行注释行（使用说明），以及所有受影响的元素定义
  - **飞书用例表**：各 sheet 的第 1 行注释行（使用说明），以及受影响的用例行（操作步骤、预期结果等列）
  - `scripts/update_feishu_sheets.py` 中的飞书注释行（如涉及元素表列）
  - 未同步飞书表格本身（注释行 + 数据行）的视为未完成，必须补上
- **不确定必须确认，禁止盲写**：对需求场景、使用方式、设计选择有任何不确定时，必须先停下来和用户确认。**格式选型（如分隔符用逗号还是竖线）本身就是设计决定，不管自己觉得多"显然"，都要抛出来让用户选。**
- **改完必须验证**：每次代码修改后跑语法检查，确认无报错再答复
- **截图无法查看时用数值分析**：大尺寸 RGBA PNG 用 PIL+numpy 分析像素值来判断画面内容
