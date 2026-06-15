# 笔记自动化测试

文石 BOOX 笔记应用的端到端自动化框架。**pytest + Appium + Allure，Excel 驱动**——测试人员只需编辑 Excel，无需写代码。

## 快速开始

```bash
pip install -r requirements.txt
appium --address 127.0.0.1 -p 4723            # 或设 APPIUM_START_CMD 自动拉起
pytest boox_automation/tests/test_excel_runner.py -s
```

默认从飞书云端加载最新用例和元素定义。离线模式：`USE_LOCAL_EXCEL=1 pytest ...`。

---

## 两种数据加载模式

程序通过 `USE_LOCAL_EXCEL` 环境变量切换数据源，列结构完全一致：

| | 云端模式（默认） | 本地模式 |
|---|---|---|
| 用例 | 飞书电子表格，多人协同编辑，在线实时更新 | `data/test_cases.xlsx`，本地 Excel 编辑 |
| 元素 | 飞书电子表格，多 sheet 对应不同页面 | `data/elements.xlsx`，多 sheet 对应不同页面 |
| 预期结果 | 元素表的 `预期结果` sheet | 元素表的 `预期结果` sheet |
| 编辑方式 | 飞书网页/客户端编辑 | 本地 Excel 编辑 |
| 缓存 | `data/.cache/` 自动缓存（24h 有效） | 不缓存 |

数据源在 `config.yaml` 中配置：

```yaml
# 用例配置（云端/本地共用）
excel:
  test_case_sheets: ["笔记"]        # 加载哪些 sheet
  test_case_file: "test_cases.xlsx" # 本地文件（本地模式）

# 飞书表格 token（云端模式）
feishu:
  test_case_token: "https://..."   # 用例表格 URL / token
  elements_token: "https://..."    # 元素表格 URL / token
  elements_file: "elements.xlsx"
```

---

## 测试用例怎么写

### 示例

```
优先级：P0
标题：未登录-创建手写笔记
所属模块：笔记首页
前置条件：
    【海外设备执行】

操作步骤：
    1.点击【笔记】应用
    2.检查【笔记首页引导页】是否显示
    3.点击【创建笔记】
    4.检查【创建菜单弹窗】内菜单显示正常
    5.点击【手写笔记】
    6.检查【手写笔记创建页】内容正常
    7.点击【创建】按钮
    8.点击【退出手写笔记】
    9.检查【笔记列表页】显示笔记已创建

预期结果：
    【笔记首页引导页】引导页是否正常
    【创建菜单弹窗】弹窗内容完整
    【手写笔记创建页】页面布局正常
    【笔记列表页】笔记列表中显示新建的笔记
```

### 列说明

程序只读以下列，其他列自由填写：

| 列 | 配置键 | 说明 | 必填 |
|---|---|---|---|
| C | module | 所属模块（用于 NOTE_TEST_MODULES 筛选） | 建议 |
| E | title | 用例标题 | **必填** |
| F | priority | P0/P1/P2/test | 建议 |
| G | precondition | 前置条件 | 可选 |
| H | steps | 操作步骤，`【】` 标记元素 | **必填** |
| I | expected | 预期结果 | 建议 |
| J | result | 程序写入，无需手动填 | — |
| L | remark | 备注 | 可选 |

### 操作步骤（H 列）

每步前面加数字编号，换行分隔。`【】` 内的文字对应元素表的 match 列。

| 关键词 | 动作 | 需 `【】` | 示例 |
|---|---|---|---|
| `点击` `打开` `进入` `选择` `双击` `退出` `返回` `清空` `确认` `关闭` | 点击 | 是 | `点击【创建笔记】` |
| `输入` | 输入文本 | 是 | `输入【标题】测试名称` |
| `长按` | 长按 | 是 | `长按【笔记条目】` |
| `点击坐标` `长按坐标` `滑动` | 坐标操作 | 是 | `点击坐标【屏幕中央】` |
| `上滑` `下滑` `左滑` `右滑`（及"向XX滑动"） | 方向滑动 | **否** | `向下滑动` |
| `按返回键` `返回键` | 系统返回 | **否** | `按返回键` |
| `检查` `查看` `校验`（步骤开头） | 跳过，I 列断言接管 | — | — |

无动作词但有 `【】` → 默认点击。方向滑动和返回键**不要加 `【】`**。

### 前置条件（G 列）

可换行组合：

| 写法 | 含义 |
|---|---|
| `【国内设备执行】` / `【海外设备执行】` | 按地区 |
| `【平板设备执行】` / `【阅读器设备执行】` | 按设备类型 |
| `【黑白设备执行】` / `【彩色设备执行】` | 按屏幕 |
| `【4.2.0-版本执行】` | 固件 ≥ 指定版本。dev/非标版本视为最高 |

### 预期结果（I 列）

格式：包含 `【预期结果匹配文本】` 即可，位置不限。`步骤{N}：` 前缀不再需要。

关联方式：H 列的 `检查【X】` 自动去 I 列找包含 `【X】` 的行。没找到会报错（含步骤号），不再出现步骤号错位导致的静默跳过。同名 tag 按出现顺序一一对应。

不含 `【】` 的行视为文档描述跳过，I 列为空 DEBUG 提示但不阻塞。

| 后缀 | 模式 | 说明 | 示例 |
|---|---|---|---|
| （无） | visible | 预期元素可见 | `【笔记列表页】` |
| `不可见` / `不存在` | not_visible | 预期元素不可见 | `【引导弹窗】不可见` |
| `toast提示` | toast | 等待 Toast 弹出 | `【保存成功】toast提示` |
| `toast不出现` | toast_not | 等待期内 Toast 不弹出 | `【网络错误】toast不出现` |

### 筛选

```bash
NOTE_TEST_MODULES=笔记首页,手写笔记 pytest ...   # 模块筛选
NOTE_DESELECT_NODEIDS="...跳过*" pytest ...     # 跳过用例
```

优先级筛选：修改 `config.yaml priority_filter`（P0/P1/P2/test/空=全部）。

---

## 元素定义怎么写

### 云端模式（默认）

元素存储在**飞书电子表格**中。在飞书网页/客户端中编辑，多人实时协作。

每个 **sheet = 一个页面**，如 `笔记首页`、`手写笔记`、`系统`。程序根据 `config.yaml` 的 `element_sheet_prefix` 筛选加载哪些 sheet。

### 本地模式（USE_LOCAL_EXCEL=1）

使用 `data/elements.xlsx`，用本地 Excel 编辑。结构同云端，可离线工作。

### 两种模式共用同一套列结构

#### 元素 Sheet（6 列）

| 列 | 配置键 | 说明 | 必填 | 示例 |
|---|---|---|---|---|
| A | 元素标识 / key | `页面.元素名`，全局唯一 | **必填** | `笔记首页.创建笔记按钮` |
| B | 匹配文本 / match | 步骤 `【】` 通过此列关联 | **必填** | `创建笔记` |
| C | 定位方式 / locator | XPath / 纯文本，支持多设备分块 | **必填** | `//*[@resource-id="..."]` |
| D | 操作类型 / action | 中文值，不填自动推断 | 建议 | `点击` |
| E | 用途说明 / operation | 日志/截图描述 | 建议 | 首页的创建按钮 |
| F | 序号 / index | 同 match 多元素时区分，0 开始 | 选填 | `1` |

#### locator 多设备分块

```
默认 XPath（所有设备兜底，必填，放最前面）

阅读器：
//阅读器专用

海外：
//海外专用
```

前缀键：`国内` `海外` `全球` `平板` `阅读器` `6` `7.8` `10.3` `13.3` 及版本号，逗号组合多条件。匹配条件最多的优先，无匹配回退默认。

#### action 可选值

| 值 | locator 格式 | 场景 |
|---|---|---|
| `点击`（默认） | XPath | 按钮/菜单/图标 |
| `输入` | XPath | 输入框 |
| `长按` | XPath | 触发菜单 |
| `校验toast` | XPath | 验证 Toast |
| `点击坐标` | `x,y` | 无固定 XPath 的位置 |
| `长按坐标` | `x,y` | 同上，长按 |
| `滑动` | `x1,y1,x2,y2` | 自定义滑动 |

---

## 预期结果 Sheet

元素表中名为 `预期结果` 的专用 sheet，存放页面断言数据。

### 5 列结构

| 列 | 说明 | 必填 |
|---|---|---|
| A | 元素标识，如 `笔记首页.引导页` | ✓ |
| B | 匹配文本，I 列 `【】` 通过此列关联 | ✓ |
| C | 页面XML（Appium Inspector 导出后精简） | C/D 二选一 |
| D | 检查元素，每行一个 XPath，可选 `,期望文本` 对比文字 | C/D 二选一 |
| E | 用途说明 | |

### 校验优先级

```
toast 模式 → D 列 XPath 逐条检查 → C 列 XML 签名对比
→ data/expected_pages/{key}.xml 文件 → WARNING 跳过
```

### 获取 C 列 XML

```bash
python boox_automation/scripts/extract_page_xml.py          # 自动保存
python boox_automation/scripts/extract_page_xml.py --stdout  # 打印到终端
```

**C 列多设备分块格式（同元素 locator）：**

```
默认 XML
<hierarchy>...</hierarchy>

国内：
<hierarchy>...</hierarchy>

海外：
<hierarchy>...</hierarchy>
```

对比逻辑：只比较 `class` + `resource-id`，text 差异仅 INFO 不计入失败。

---

## 运行方式

```bash
# 默认运行（云端加载）
pytest boox_automation/tests/test_excel_runner.py -s

# 本地离线
USE_LOCAL_EXCEL=1 pytest boox_automation/tests/test_excel_runner.py -s

# Allure 报告
python boox_automation/scripts/run_report.py

# 提取页面 XML
python boox_automation/scripts/extract_page_xml.py
```

### 运行前提

- Android 设备 USB 连接，开启 USB 调试
- Appium Server 已启动
- 设备语言匹配用例前置条件

---

## 项目结构

```
boox_automation/
├── driver.py                 DriverProxy，支持热切换
├── conftest.py               pytest lifecycle + fixture + 前置检查
├── config.yaml               所有可调参数集中管理
├── pytest.ini                pytest 配置
│
├── engine/                   测试引擎
│   ├── parser.py             步骤解析 + 前置条件检查
│   ├── elements.py           元素加载 + 匹配 + 预期结果
│   ├── reporter.py           结果统计
│   └── xml_checker.py        XML 签名提取 + 对比
│
├── core/                     基础设施
│   ├── config.py             config.yaml 读取封装
│   ├── feishu.py             飞书 API 客户端（云端同步）
│   ├── health.py             Appium/ADB 健康检查
│   ├── paths.py              产物路径管理
│   └── cleanup.py            产物轮换清理
│
├── data/                     ✏️ 数据文件
│   ├── test_cases.xlsx       本地用例（本地模式）
│   ├── elements.xlsx         本地元素（本地模式）+ 预期结果 sheet
│   ├── .cache/               飞书缓存（云端模式，自动生成）
│   └── expected_pages/       本地预期 XML 文件
│
├── ui_ops/                   UI 操作层
│   ├── operations.py         14+ 种操作，超时重试
│   ├── element_catalog.py    locator → 中文描述
│   └── logcat.py             Android 日志捕获
│
├── devices/                  设备管理
│   ├── info.py               ADB 信息采集
│   ├── registry.py           型号注册表
│   └── models/               70+ 型号 YAML
│
├── tests/                    测试入口
│   ├── test_excel_runner.py  Excel 用例 pytest 主入口
│   ├── helpers.py            笔记业务流公共方法
│   └── ...
│
└── scripts/                  辅助工具
    ├── extract_page_xml.py   提取页面 XML
    └── run_report.py         Allure 报告入口
```

---

## 环境变量

| 变量 | 默认 | 作用 |
|---|---|---|
| `APPIUM_HOST` / `APPIUM_PORT` | `127.0.0.1:4723` | Appium 地址 |
| `APPIUM_SERVER_URL` | — | 完全自定义 URL |
| `APPIUM_START_CMD` | — | 自动拉起命令 |
| `NOTE_DEVICE_ID` | 自动 | 多设备时指定 |
| `NOTE_TEST_MODULES` | 全部 | 逗号分隔，按模块筛选 |
| `NOTE_TEST_CASE_SHEETS` | config.yaml | 逗号分隔，覆盖用例 sheet 列表 |
| `NOTE_DESELECT_NODEIDS` | — | 模糊匹配跳过用例 |
| `NOTE_ARTIFACTS_KEEP_LATEST` | `5` | 产物保留轮数 |
| `USE_LOCAL_EXCEL` | `0` | `1`=本地 xlsx 离线模式 |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | config.yaml | 覆盖飞书应用凭证 |
| `FEISHU_TEST_CASE_TOKEN` / `FEISHU_ELEMENTS_TOKEN` | config.yaml | 覆盖表格 token |

---

## FAQ

**`【xxx】` 报"未匹配到任何元素"？** 检查元素表 match 列是否完全一致。

**怎么只让平板跑？** G 列加 `【平板设备执行】`。

**跑完后 Excel 没被修改？** 结果只打日志，不写回文件，避免冲突。

**报错"元素在 N 次重试后仍失败"？** 查看自动截图 `artifacts/screenshots/`。

---

## 环境要求

- Python 3.9+
- Appium Server 2.x
- Android 设备（USB 调试）
- 目标应用：文石笔记 `com.onyx.android.note`
