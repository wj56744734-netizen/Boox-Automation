# onyx自动化测试

Android 端到端自动化测试框架。**pytest + Appium + Allure，Excel 驱动**——测试人员只需编辑 Excel，无需写代码。

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

每步前面加数字编号，换行分隔。操作类型由元素表 D 列唯一决定，H 列只需写 `【元素名】`：

```
1. 【进入笔记首页】
2. 【创建笔记按钮】
3. 检查【创建菜单弹窗】内菜单显示正常
4. 【推送测试文件】
```

**解析规则**：
- 含 `【】` 的步骤 → 操作类型由元素表 D 列决定（点击/输入/长按/滑动/adb命令等）
- `检查【X】` / `查看【X】` / `校验【X】` 开头 → 跳过 UI 操作，去 I 列找 `【X】` 执行预期结果断言
- 不含 `【】` 的行 → 视为描述性文字，跳过

### 前置条件（G 列）

可换行组合多种类型：

**设备条件**（不满足则 skip）：

| 写法 | 含义 |
|---|---|
| `【国内设备执行】` / `【海外设备执行】` | 按地区 |
| `【平板设备执行】` / `【阅读器设备执行】` | 按设备类型 |
| `【黑白设备执行】` / `【彩色设备执行】` | 按屏幕 |
| `【4.2.0-版本执行】` | 固件 ≥ 指定版本。dev/非标版本视为最高 |

**环境清理**（fixture setup 阶段执行，不可逆）：

| 写法 | 操作 |
|---|---|
| `【清理应用数据】` | `adb shell pm clear`（config.yaml 配置包名） |
| `【清理存储文件】` | `adb shell rm -rf`（config.yaml 配置路径） |

**文件检查**（新增，不满足则 skip）：

| 写法 | 操作 |
|---|---|
| `【PNG文件】` | 去「前置条件」sheet 找对应行 → `adb shell "test -f <路径>"` 检查 |

### 预期结果（I 列）

每行写一个 `【X】`，与 H 列的 `检查【X】` 按出现顺序一一对应。断言类型由预期结果 Sheet E 列决定（`断言存在` / `断言不存在` / `断言toast` / `断言toast不出现`），I 列不再需要后缀：

```
【创建菜单弹窗】           → 预期结果 Sheet E 列 = 断言存在
【异常提示弹窗】           → 预期结果 Sheet E 列 = 断言不存在
【保存成功】              → 预期结果 Sheet E 列 = 断言toast
```

H 列 `检查【X】` 在 I 列找不到匹配 → 报错终止（含步骤号 + I 列已有标记）。同名 tag 按出现顺序一一对应。

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

| 列 | 名称 | 必填 | 说明 |
|---|---|---|---|
| A | 模块 | ✓ | 页面/功能区域名，与 B 列拼接为 key。旧格式已含 `.` 时视为完整 key，不再拼接 |
| B | 匹配文本 | | H 列 `【】` 内的文字，用于反向索引。不填时自动取 key 末段（`.` 后）加入索引 |
| C | 定位元素 | ✓ | XPath 或纯文本/坐标，支持多设备块 |
| D | 操作 | | 中文值，不填默认"点击" |
| E | 用途说明 | | 日志/截图中的元素描述 |
| F | 序号 | | 同 match 多元素时区分，默认 0 |

**A 列示例**：模块=`笔记首页`，B=`创建笔记` → key=`笔记首页.创建笔记按钮`。全局唯一不重复。

**B 列示例**：H 列写 `【退出笔记】` → 系统去元素表找 B 列=`退出笔记` 的行。key 末段兜底：key=`桌面进入.书库首页` → 自动索引 `书库首页`。

**C 列格式按操作类型不同**：

| D 列值 | C 列格式 | 示例 |
|---|---|---|
| `点击`（默认） | XPath | `//*[@resource-id="com.onyx:id/title"]` |
| `输入` | `XPath,输入文本` | `//*[@resource-id=".../edit"],测试名称` |
| `长按` | XPath | `//*[@text="笔记条目"]` |
| `校验toast` | XPath | `//android.widget.Toast` |
| `点击坐标` | `x,y` 或 `x,y,【验证tag】` | `0.5,0.3` 或 `0.5,0.3,【弹窗已消失】` |
| `长按坐标` | `x,y` | `0.5,0.3` |
| `滑动` | `x1,y1,x2,y2` | `0.7,0.5,0.3,0.5` |
| `adb命令` | 完整命令（不含 `adb` 前缀） | `push /tmp/a.pdf /sdcard/` |

**E 列示例**：出现在失败日志（`元素用途: xxx`）、Allure 截图标题、步骤日志（`点击「xxx」`）。

**F 列示例**：同一页面有多个"创建按钮"时，用序号 `1`、`2` 区分。

#### locator 多设备分块

第一个 `键：` 之前的内容自动作为默认（不需要写 `默认：` 前缀）：

```
//所有设备兜底的 XPath（第一个块自动=默认，必填）

阅读器：
//阅读器专用

海外：
//海外专用
```

前缀键：`国内` `海外` `全球` `平板` `阅读器` `黑白` `彩色` 及版本号（如 `4.2.0`），逗号组合多条件。条件匹配最多的优先，无匹配回退默认。

#### action 可选值

| 值 | locator 格式 | 场景 |
|---|---|---|
| `点击`（默认） | XPath | 按钮/菜单/图标 |
| `输入` | XPath | 输入框 |
| `长按` | XPath | 触发菜单 |
| `校验toast` | XPath | 验证 Toast |
| `点击坐标` | `x,y` 或 `x,y,【验证tag】` | 无固定 XPath 的位置，带验证 tag 时点击后自动校验预期结果 |
| `长按坐标` | `x,y` | 同上，长按 |
| `滑动` | `x1,y1,x2,y2` | 自定义滑动 |
| `adb命令` | 完整命令（不含 `adb` 前缀），如 `push /tmp/a.pdf /sdcard/` | **新增** — 执行 adb 命令，成功记 INFO，失败记 ERROR，不重试 |

### 新增 Sheet：前置条件（4 列）

位于元素表下，Sheet 名固定 `前置条件`，用例表 G 列 `【PNG文件】` 通过 A 列匹配：

| 列 | 名称 | 必填 | 说明 |
|---|---|---|---|
| A | 条件名称 | ✓ | G 列 `【】` 引用 |
| B | 检查类型 | ✓ | `文件存在` 或 `文件不存在` |
| C | 文件路径 | ✓ | 设备路径，如 `/sdcard/Documents/test.png`，支持多设备块 |
| D | 用途说明 | | 描述 |

系统自动拼接 `adb shell "test -f <C列路径>"` 执行，不满足则 skip 用例。

### 新增 Sheet：ADB命令（3 列）

位于元素表下，Sheet 名固定 `ADB命令`，H 列 `【推送测试文件】` 通过 A 列匹配：

| 列 | 名称 | 必填 | 说明 |
|---|---|---|---|
| A | 命令名称 | ✓ | H 列 `【】` 引用 |
| B | adb命令 | ✓ | 完整命令（不含 `adb` 前缀），支持多设备块 |
| C | 用途说明 | | 描述 |

系统自动拼接 `adb -s <device_id>` 执行，成功记 INFO（含命令名称），失败记 ERROR（含命令名称 + exit code + stderr），不重试、不中断用例。

---

## 预期结果 Sheet

元素表中格式为 `预期结果【模块名】` 的 sheet（如 `预期结果【笔记】`），存放页面断言数据。

### 6 列结构

| 列 | 名称 | 必填 | 说明 |
|---|---|---|---|
| A | 模块 | ✓ | key 前缀，与 B 列拼接 |
| B | 匹配文本 | ✓ | I 列 `【】` 通过此列关联；toast 模式下为期望 toast 文本 |
| C | 定位元素 | C/D 二选一 | XPath 选择器，每行一个，可选 `,期望文本` |
| D | xml页面 | C/D 二选一 | Appium Inspector 导出 XML，支持多设备块 |
| E | 操作 | ✓ | `断言存在` / `断言不存在` / `断言toast` / `断言toast不出现` |
| F | 用途说明 | | 描述 |

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

**C 列多设备分块格式（同元素 locator，第一个块自动=默认）：**

```
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
