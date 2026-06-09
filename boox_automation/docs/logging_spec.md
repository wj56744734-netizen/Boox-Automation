# 项目日志格式与规范

## 1. 日志基础设施

### 1.1 配置入口

| 入口 | 位置 | 说明 |
|---|---|---|
| pytest | `pytest.ini:6-9` | `log_cli=true`，实时输出到控制台 |
| 独立运行 | `scripts/run_cases.py:39-43` | `logging.basicConfig` 手动配置 |
| 清理工具 | `core/cleanup.py:102-107` | `logging.basicConfig` 独立配置 |
| 第三方静音 | `conftest.py:164-167` | selenium→WARNING, urllib3→ERROR, appium→WARNING |

### 1.2 时间格式

```
pytest:       %H:%M:%S        (10:06:38)
run_cases:    %H:%M:%S        (10:06:38)
```

统一使用 24 小时制，精确到秒。

### 1.3 日志级别

```
%(asctime)s  %(levelname)-5s  %(message)s
```

级别宽度固定 5 字符，右补空格对齐：

```
10:06:38  INFO    设备已连接: 3cd3f62e
10:06:38  DEBUG   当前模块安卓版本: 16
10:06:45  WARNING 预期结果【手写笔记.创建页】页面XML为空，跳过
10:07:13  ERROR   ⏐ FAILED  R2 [P0] 未登录-创建手写笔记
```

### 1.4 Logger 实例

全项目统一使用 `logging.getLogger(__name__)`：

```python
# 各模块
logger = logging.getLogger(__name__)
```

涉及模块：

| 模块 | Logger |
|---|---|
| `engine/elements.py` | `boox_automation.engine.elements` |
| `engine/executor.py` | `boox_automation.engine.executor` |
| `engine/reporter.py` | `boox_automation.engine.reporter` |
| `engine/xml_checker.py` | `boox_automation.engine.xml_checker` |
| `tests/test_excel_runner.py` | `boox_automation.tests.test_excel_runner` |
| `core/feishu.py` | `boox_automation.core.feishu` |
| `core/cleanup.py` | `boox_automation.core.cleanup` |
| `scripts/run_cases.py` | `boox_automation.scripts.run_cases` |
| `ui_ops/operations.py` | 直接使用 `logging.debug/error`（无模块级 logger） |
| `ui_ops/logcat.py` | 直接使用 `logging.debug/warning/error` |
| `devices/info.py` | 直接使用 `logging.info/debug/warning/error` |
| `core/health.py` | 直接使用 `logging.info/warning` |
| `conftest.py` | 直接使用 `logging.info/warning/critical/debug` |

---

## 2. 日志分类与规范

### 2.1 Session 级别（会话开始/结束）

#### 启动横幅

```python
# conftest.py:178-180
logging.info("=" * 60)
logging.info("  笔记自动化测试")
logging.info("=" * 60)
```

```python
# scripts/run_cases.py:77-79
logging.info("=" * 40)
logging.info("  笔记自动化测试 - Excel Runner")
logging.info("=" * 40)
```

#### 设备信息

```python
# devices/info.py:373-391
logging.info("-" * 40)
logging.info(
    f"设备: {device_name} | "
    f"{device_size}寸{driver_colour} | "
    f"{version_info} | "
    f"{device_region}"
)
logging.info(
    f"      分辨率 {filtered_size} | "
    f"平台 {device_platform} | "
    f"类型 {devices_reader} | "
    f"构建 {build_type}"
)
logging.info(f"      系统: {build_date_time}")
# 内存/存储
logging.info(f"  内存: 总 {mem_total}GB / 可用 {mem_available}GB")
logging.info(f"  存储: 总 {total} / 可用 {available} ({percent}已用)")
logging.info("-" * 40)
```

#### 用例汇总

```python
# test_excel_runner.py:353
logger.info(f"用例汇总: 通过={summary['pass']}, 不通过={summary['fail']}, 跳过={summary['skip']}")
```

---

### 2.2 数据加载级别

#### 飞书读取

```python
# 成功
logger.info(f"已从飞书读取 sheet '{sheet_name}': {len(rows)} 行")

# 无数据
logger.warning(f"飞书 sheet '{sheet}' 无数据")

# 失败回退
logger.warning("飞书云端加载元素失败，回退缓存", exc_info=True)
logger.warning("飞书云端加载预期结果失败，回退缓存", exc_info=True)
logger.warning("无可用缓存，回退本地 Excel")
```

#### 缓存

```python
# 更新
logger.debug(f"缓存已更新: {path}")

# 过期
logger.info(f"缓存 {cache_name} 已过期（{age_desc}）")

# 损坏
logger.warning(f"缓存 {cache_name} 损坏，忽略")

# 加载
logger.info(f"已从缓存加载 {count} 个元素定义")
logger.info(f"已从缓存加载 {count} 个预期结果定义")
```

#### 最终来源

```python
logger.info(f"元素来源: 飞书云端（已更新本地缓存）")
logger.info(f"预期结果来源: 飞书云端（已更新本地缓存）")
logger.info(f"用例来源: 飞书云端（已更新本地缓存）")
logger.warning(f"元素来源: 本地缓存")
logger.warning(f"预期结果来源: 本地缓存")
```

---

### 2.3 元素/预期结果加载

#### 元素加载汇总

```python
logger.info(f"已从飞书加载 {total} 个元素定义 ({len(sheets)} 个 Sheet)")
logger.info(f"已从 {xlsx_path} 加载 {count} 个元素定义 ({len(sheets)} 个 Sheet)")
logger.debug(f"元素索引构建完成: {count} 个元素, {index_count} 个索引词")
```

#### 预期结果加载

```python
# 跳过原因
logger.warning(f"预期结果【{key}】页面XML和检查元素均为空，跳过")
logger.warning("预期结果行缺少「元素标识」，跳过")

# 汇总
logger.info(f"已从飞书加载 {count} 个预期结果定义")
```

#### 元素匹配

```python
# 多候选
logger.debug(f"【{tag}】 [{ctx}] {candidates}个候选, 页面'{page}' → 选 {best} (alt: {alt})")

# 无匹配
logger.debug(f"【{tag}】 [{ctx}] 未匹配到任何元素")       # warn=False
logger.warning(f"【{tag}】{ctx} 未匹配到任何元素")        # warn=True

# 多设备块匹配
logger.debug(f"元素【{key}】locator 多设备匹配: {device_key}")
```

#### 多设备内容解析

```python
logger.warning(
    f"多设备内容缺少默认块，仅有条件块: {list(blocks.keys())}。"
    f"未匹配到条件的设备将跳过"
)
```

---

### 2.4 用例执行级别

#### 用例生命周期

```python
# 开始
logger.info(f"⏐ START  {case_id}")      # test_excel_runner
logger.info(f"⏐ START  {case_id}")      # executor

# 跳过（前置条件/校验）
logger.info(f"⏐ SKIPPED {case_id} — {reason}")
logger.info(f"⏐ SKIPPED {case_id} — {validation_skip}")

# 通过
logger.info(f"⏐ PASSED  {case_id}")

# 失败
logger.error(f"⏐ FAILED  {case_id}")
```

格式：`⏐` 前缀标记用例状态，后跟 `case_id` = `R{row_number} [{priority}] {title}`

#### 步骤执行

```python
# 跳过
logger.warning(f"步骤{seq}: 不支持的操作类型 '{action}'")
logger.warning(f"步骤{seq}: 【{tag}】未匹配到元素")

# 失败（executor）
logger.error(f"FAILED  步骤{seq}: 【{tag}】{action} — {e}")
```

#### 预期结果匹配

```python
# 未匹配
logger.warning(f"R{row_number} 预期结果【{tag}】未在预期结果 sheet 中匹配")

# 无预期结果
logger.warning(f"R{row_number} [{title}] 无预期结果，缺少断言")
```

---

### 2.5 预期结果检查

#### 执行结果

```python
# 通过/失败
logger.info(f"步骤{step_seq} 预期结果 [{expected_key}]:\n{result.summary()}")

# result.summary() 示例：
#   预期5个元素全部存在
#   预期5个元素，匹配4个，缺失1个
#     缺失: [TextView] resource-id=com.onyx:id/title text='笔记'
#   文本变更(INFO): [Button] resource-id=...
```

#### 跳过/错误

```python
# 无匹配设备内容
logger.warning(f"预期结果【{tag}】无匹配的设备内容，跳过")

# XML 解析失败
logger.error(
    f"预期结果【{tag}】XML 解析失败: {e}\n"
    f"XML 前200字符: {content[:200]}"
)

# page_source 获取失败
logger.error(f"预期结果【{tag}】获取 page_source 失败: {e}")

# 元素检查失败
logger.error(f"预期结果【{tag}】元素检查失败: {e}")
```

---

### 2.6 操作层（operations.py）错误日志

**结构化错误日志格式** — 项目最重要的错误输出：

```text
[{step_label}] 元素查找失败「{element_key}」（重试 {max_retries} 次）
  ↳ 定位方式: {locator_type}
  ↳ 定位值:   {locator_value}
  ↳ 元素键: {element_key}
  ↳ 数据来源: {file}::{sheet}
  ↳ 调用链: func1 → func2 → func3
  ↳ 元素用途: {catalog_description}
  ↳ 截图: artifacts/screenshots/YYYY-MM-DD/HHmmss_{func}_{locator}.png
```

**字段说明：**

| 字段 | 说明 | 示例 |
|---|---|---|
| `↳ 定位方式` | 元素表中的 locator 类型 | `xpath` |
| `↳ 定位值` | 元素表中的 locator 值 | `//android.widget.TextView[@text="笔记"]` |
| `↳ 元素键` | 飞书元素标识（key） | `笔记首页.创建菜单手写笔记` |
| `↳ 数据来源` | 元素来源 Excel 文件名 + Sheet 名 | `data/elements.xlsx::笔记首页` |
| `↳ 调用链` | 从入口到失败点的函数调用链（去重连续相同） | `test_case → _dispatch_step → xpath_text_click` |
| `↳ 元素用途` | `element_catalog.py` 中的 locator → 中文描述 | `笔记首页创建笔记按钮` |
| `↳ 截图` | 失败时刻屏幕截图路径 | `artifacts/screenshots/2026-06-09/100713__safe_click_xpath.png` |

**变体：直接调用（无 element_key）**

```text
{func_name}({params}) 在 {max_retries} 次重试后仍失败
  ↳ 定位方式: {locator_type}
  ↳ 定位值:   {locator_value}
  ↳ 调用链: {chain}
  ↳ 元素用途: {description}
  ↳ 截图: {path}
```

**操作成功日志（DEBUG）：**

```python
logging.debug(f"{call_label} 超时/未找到，重试 {attempt}/{max_retries}")
logging.debug(f"{call_label} WebDriver 异常，重试 {attempt}/{max_retries}: {exc_name}")
```

---

### 2.7 设备操作日志

#### ADB / 设备健康

```python
# 设备状态
logging.info(f"设备已连接: {device_id}")
logging.warning(f"设备 {device_id} 当前不可用（第 {attempt}/{retries} 次）：{state}")
logging.info(f"设备 {device_id} 恢复在线（第 {attempt} 次探测成功）")

# 多设备
logging.info(f"多设备连接，默认使用设备：{model}（ID: {device_id}）")
logging.info(f"使用环境变量指定设备ID: {device_id}")

# ADB 命令
logging.warning(f"ADB命令失败（第 {attempt}/{retries} 次）：{command} | 错误：{error}")

# Appium
logging.warning(f"检测到 Appium 未监听 {host}:{port}，尝试自动拉起：{cmd}")
logging.info(f"Appium 服务已就绪：{host}:{port}")
```

#### 设备信息采集

```python
logging.info(f"语言检查: {locale} ✓")
logging.info(f"Wi-Fi: {ssid} | {ip} | {rssi} dBm ({quality}) | {link_speed}")
logging.info(f"测试文件检查: {count} 个目录 ✓")
logging.debug(f"当前模块安卓版本: {version}")
logging.debug(f"使用命令 {cmd} 成功获取指纹")
logging.error(f"获取Android版本失败: {e}")
logging.error(f"所有指纹获取方法均失败，设备ID: {device_id}")
logging.error(f"设备型号 {name} 未在设备列表中找到")
```

#### 应用启动

```python
logging.debug("笔记应用启动成功")
logging.debug("测试完成，返回主页")
logging.info("正在加载应用...")
logging.warning(f"启动引导检查失败，跳过开始使用点击：{e}")
```

---

### 2.8 第三方日志静音

```python
# conftest.py + run_cases.py
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
logging.getLogger('appium').setLevel(logging.WARNING)
```

---

## 3. 特殊前缀约定

| 前缀 | 含义 | 使用位置 |
|---|---|---|
| `⏐ START` | 用例开始执行 | executor, test_excel_runner |
| `⏐ SKIPPED` | 用例被跳过 | executor |
| `⏐ PASSED` | 用例执行通过 | executor |
| `⏐ FAILED` | 用例执行失败 | test_excel_runner |
| `[DEBUG]` | 手动调试标记 | operations, helpers |
| `[IGNORE]` | 忽略跳过用例 | conftest |
| `[IMPORT_TIME_DEBUG]` | 导入耗时标记 | helpers |

---

## 4. Allure 集成

```python
# 步骤标记
with allure.step(case_id):           # 用例级步骤
with allure.step(f"点击「{display}」"):  # 操作级步骤
with allure.step(f"多元素检查「{display}」"):

# 失败截图附件
allure.attach(
    screenshot,
    name=f"{call_label} 失败截图｜{desc}",
    attachment_type=allure.attachment_type.PNG,
)
```

Allure 报告目录：
- 结果输入：`artifacts/allure_results/test_{timestamp}/`
- HTML 输出：`artifacts/allure_html/report_{timestamp}/`

---

## 5. 排查指南

### 5.1 按级别使用

| 级别 | 用途 | 示例 |
|---|---|---|
| `DEBUG` | 重试、索引构建、匹配细节、驱动内部状态 | 元素多设备匹配、locator 解析 |
| `INFO` | 正常流程节点：加载完成、用例状态、检查结果 | 飞书读取、用例 START/PASSED、预期结果对比摘要 |
| `WARNING` | 可恢复异常：无匹配、空数据、回退、跳过 | 元素未匹配、缓存损坏、预期结果为空 |
| `ERROR` | 不可恢复失败：操作失败、解析失败、设备异常 | KeyError、XML 解析失败、ADB 命令失败 |
| `CRITICAL` | 极少数场景 | 命令执行异常 |

### 5.2 日志中查找根因

1. 从最早出现的 `ERROR` 开始（后续的通常是级联失败）
2. `↳` 开头的结构化字段给出精确定位信息
3. 截图路径格式：`artifacts/screenshots/YYYY-MM-DD/HHmmss_{function}_{locator}.png`
4. `↳ 元素键` 直接对应飞书元素表中的 A 列 key
5. `↳ 数据来源` 指明元素定义所在的 Excel/Sheet
