# Note Automation

文石（BOOX）笔记应用的端到端自动化测试框架，基于 **pytest + Appium + Allure**，**Excel 驱动用例编写**。

> **核心理念：测试人员只需要编辑 Excel，不需要写代码。**

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 Appium（或设置 APPIUM_START_CMD 自动拉起）
appium --address 127.0.0.1 -p 4723

# 3. 连接设备
adb devices

# 4. 运行测试
pytest boox_automation/tests/test_excel_runner.py -s
```

## 怎么用

### 写测试用例

编辑 `boox_automation/engine/test_cases.xlsx`，在"操作步骤"列中写：

```
1.点击【笔记】
2.检查【笔记首页引导UI】
3.点击【创建笔记】
4.点击【手写笔记】
5.点击【退出手写笔记】
```

程序会自动找到 `【】` 对应的页面元素并执行操作。

详细规则 → `boox_automation/engine/使用指南.md`

### 定义页面元素

编辑 `boox_automation/engine/elements.xlsx`，告诉程序每个按钮/文字怎么找。

### 设置前置条件

在"前置条件"列中写 `【海外设备执行】`、`【平板设备执行】` 等，不符合条件的设备自动跳过。

## 项目结构

```
boox_automation/
├── engine/         # Excel 驱动测试框架（核心）
│   ├── test_cases.xlsx      # ✏️ 测试用例
│   ├── elements.xlsx        # ✏️ 元素定义
│   ├── 使用指南.md           # 📖 使用文档
│   ├── parser.py            # 步骤解析
│   ├── matcher.py           # 元素匹配
│   ├── conditions.py        # 前置条件检查
│   ├── executor.py          # 用例执行
│   ├── reporter.py          # 结果统计
│   └── run.py               # 独立运行入口
│
├── ui_ops/              # 底层操作引擎
│   ├── operations.py        # 14+ 种 UI 操作（点击/输入/长按/滑动）
│   ├── element_catalog.py   # 元素中文描述
│   └── Logcat.py            # 设备日志捕获
│
├── devices/            # 设备管理
│   ├── info.py
│   └── models/             # 70+ 设备型号 YAML 库
│
├── core/               # 基础设施
│   ├── health.py            # ADB/Appium 健康检查
│   ├── paths.py             # 产物路径管理
│   └── cleanup.py           # 产物清理
│
├── tests/        # 测试套件
│   ├── test_excel_runner.py # Excel 用例 pytest 入口
│   ├── helpers.py     # 公共业务方法
│   ├── run_report.py        # Allure 报告生成
│   └── performance/              # 性能测试
│
├── driver.py                # Appium Driver 管理
├── conftest.py              # pytest fixture + 前置检查
└── pytest.ini               # pytest 配置
```

## 测试标签

| Marker | 含义 |
|---|---|
| `china` | 国内设备 |
| `abroad` | 海外设备 |
| `increment` | 增量回归 |
| `full_amount` | 全量回归 |

## 环境变量

| 变量 | 默认 | 作用 |
|---|---|---|
| `APPIUM_HOST` | `127.0.0.1` | Appium 地址 |
| `APPIUM_PORT` | `4723` | Appium 端口 |
| `NOTE_DEVICE_ID` | 自动 | 多设备时指定目标 |
| `NOTE_ARTIFACTS_KEEP_LATEST` | `5` | 产物保留轮数 |

## 环境要求

- Python 3.10+
- Appium Server 2.x
- Android 设备（USB 调试已开启）
- 目标应用：文石笔记 `com.onyx.android.note`

## License

内部项目，未公开授权。
