# 日志上下文全量排查与修复方案

## 前因

上一轮修复后（KeyError 'locator' + `_detect_action` 去前导空格），5 个 P0 用例能跑起来了（4 passed, 1 skipped）。但日志输出暴露了大量上下文缺失问题，严重影响排查效率：

```text
14:29:51  WARNING  未知动作类型: skip              ← 不知道哪个用例哪个步骤
14:29:49  WARNING  多设备内容缺少默认块...             ← 不知道哪个预期结果 key
14:28:50  INFO   预期可见检查通过: 6个元素均存在        ← 不知道哪个用例哪个步骤
```

排查时只能靠时间戳和上下文猜测，无法精确定位问题。

## 排查范围

逐文件审查 `boox_automation/` 下所有 `logger.xxx()` 和 `logging.xxx()` 调用（共 80+ 处），排除设备信息采集（`devices/info.py`）、健康检查（`core/health.py`）、飞书 API（`core/feishu.py`）、产物清理（`core/cleanup.py`）这些已有充分上下文的模块。重点关注用例执行链路中的日志。

---

## 一、test_excel_runner.py（主入口，本次重点）

### 1.1 `_dispatch_step:383` — "未知动作类型: skip"  ⚠️ 严重

**当前代码：**
```python
else:
    logging.warning(f"未知动作类型: {step.action}")
```

**实际输出：**
```text
14:29:51  WARNING  未知动作类型: skip
```

**问题：**
- `skip` 已是合法动作类型（`_detect_action` 对"检查/查看/校验"步骤返回），不应报 WARNING
- 缺少 `step.seq`, `step.tag`, `step.raw`，完全无法定位

**根因：** `_dispatch_step` 未处理 `action == "skip"`，和 executor.py 的 `_run_step` 不一致。executor.py:126 正确处理了 skip。

**修复：** 增加 `skip` 分支为 no-op
```python
elif step.action == "skip":
    pass  # 检查/查看/校验步骤，不需要 UI 操作
else:
    logging.warning(f"未知动作类型: {step.action}")
```

---

### 1.2 `_dispatch_expected_page:445` — 元素检查失败  ⚠️ 严重

**当前代码：**
```python
logger.error(f"预期结果【{ep.tag}】元素检查失败: {e}")
```

**实际输出：**
```text
ERROR  预期结果【创建菜单弹窗】元素检查失败: ...
```

**问题：** 缺少 `ep.expected_key`（真实 key 名）。排查时需要用 tag 反查 key。

**修复：**
```python
logger.error(f"预期结果【{ep.tag}】（key={ep.expected_key}）元素检查失败: {e}")
```

---

### 1.3 `_dispatch_expected_page:460` — 无匹配设备内容  ⚠️ 中等

**当前代码：**
```python
logger.warning(f"预期结果【{ep.tag}】无匹配的设备内容，跳过")
```

**问题：** 缺少 `ep.expected_key`。排查时需要知道具体哪个预期结果 key 缺少设备适配。

**修复：**
```python
logger.warning(f"预期结果【{ep.tag}】（key={ep.expected_key}）无匹配的设备内容，跳过")
```

---

### 1.4 `_dispatch_expected_page:468` — 获取 page_source 失败  ⚠️ 中等

**当前代码：**
```python
logger.error(f"预期结果【{ep.tag}】获取 page_source 失败: {e}")
```

**修复：**
```python
logger.error(f"预期结果【{ep.tag}】（key={ep.expected_key}）获取 page_source 失败: {e}")
```

---

### 1.5 `_dispatch_expected_page:475-478` — XML 解析失败  ⚠️ 中等

**当前代码：**
```python
logger.error(
    f"预期结果【{ep.tag}】XML 解析失败: {e}\n"
    f"XML 前200字符: {content[:200]}"
)
```

**修复：**
```python
logger.error(
    f"预期结果【{ep.tag}】（key={ep.expected_key}）XML 解析失败: {e}\n"
    f"XML 前200字符: {content[:200]}"
)
```

---

### 1.6 `_dispatch_expected_page:483` — 预期结果检查通过/失败  ⚠️ 中等

**当前代码：**
```python
logger.info(f"步骤{ep.step_seq} 预期结果 [{ep.expected_key}]:\n{result.summary()}")
```

**实际输出：**
```text
14:28:50  INFO   步骤2 预期结果 [笔记首页.创建菜单弹窗]:
预期6个元素全部存在
```

**问题：** 已有 `step_seq` 和 `expected_key`，但在日志流中缺少用例上下文（`R{row} [{priority}] {title}`），无法快速关联到具体用例。

**修复：** 无需改动。用例上下文由 `set_step_context` 和操作层日志提供，预期结果日志紧随步骤执行日志之后，时间戳可关联。

---

## 二、engine/elements.py（元素加载与检查）

### 2.1 `_resolve_device_content:146-149` — 多设备内容缺少默认块  ⚠️ 严重

**当前代码：**
```python
if "__default__" not in blocks:
    logger.warning(
        f"多设备内容缺少默认块，仅有条件块: {list(blocks.keys())}。"
        f"未匹配到条件的设备将跳过"
    )
```

**实际输出：**
```text
14:29:49  WARNING  多设备内容缺少默认块，仅有条件块: ['国内', '海外']。未匹配到条件的设备将跳过
```

**问题：** `_resolve_device_content` 是一个底层工具函数，被元素 locator 解析和预期结果内容解析两处调用，但不知道调用方是谁、处理的是哪个 key。

**修复：** 函数签名加 `key` 参数
```python
def _resolve_device_content(raw: str, device_info: dict, key: str = "") -> str | None:
```
```python
    if "__default__" not in blocks:
        logger.warning(
            f"预期结果/元素【{key}】多设备内容缺少默认块，"
            f"仅有条件块: {list(blocks.keys())}。未匹配到条件的设备将跳过"
        )
```

---

### 2.2 `_check_elements_by_xpath:190/194` — 元素检查通过  ⚠️ 严重

**当前代码：**
```python
logger.info(f"预期不可见检查通过: {len(xpaths)}个元素均不存在")
logger.info(f"预期可见检查通过: {len(xpaths)}个元素均存在")
```

**实际输出：**
```text
14:28:50  INFO   预期可见检查通过: 6个元素均存在
```

**问题：** 完全没有用例/步骤/预期结果 key 信息。6 个元素是哪个预期结果的？哪步检查的？

**修复：** 函数签名加 `expected_key` 和 `step_seq` 参数
```python
def _check_elements_by_xpath(xpath_text: str, mode: str,
                              expected_key: str = "", step_seq: int = 0) -> None:
```
```python
    ctx = f"预期结果【{expected_key}】（步骤{step_seq}）" if expected_key else "元素检查"
    if mode == 'not_visible':
        if found:
            raise AssertionError(f"{ctx}预期不可见的元素仍然存在 ({len(found)}个): {found}")
        logger.info(f"{ctx}检查通过: {len(xpaths)}个元素均不存在（不可见模式）")
    else:
        if missing:
            raise AssertionError(f"{ctx}预期可见的元素未找到 ({len(missing)}个): {missing}")
        logger.info(f"{ctx}检查通过: {len(xpaths)}个元素均存在（可见模式）")
```

调用方（`_dispatch_expected_page` 和 `_check_one_expected`）需同步传入参数：
```python
_check_elements_by_xpath(checks_content, mode=ep.check_mode,
                         expected_key=ep.expected_key, step_seq=ep.step_seq)
```

---

### 2.3 `_parse_expected_rows:483` — 缺少元素标识  ⚠️ 低

**当前代码：**
```python
logger.warning("预期结果行缺少「元素标识」，跳过")
```

**问题：** 缺少行号，无法快速在飞书表格中定位。

**修复：**
```python
logger.warning(f"预期结果第{row_idx_0 + 1}行缺少「元素标识」，跳过")
```
（需要在循环中记录 `row_idx_0`）

---

### 2.4 其他加载时日志 — 上下文已充分  ✓

以下日志已具备足够上下文，无需改动：

| 行号 | 日志 | 评估 |
|---|---|---|
| 241 | `元素来源: 飞书云端（已更新本地缓存）` | ✓ 全局状态声明 |
| 245-248 | `飞书云端加载失败，回退缓存...` | ✓ 全局回退信息 |
| 254-258 | `元素来源: 本地缓存（{age}）...` | ✓ 带缓存年龄 |
| 263 | `无可用缓存，回退本地 Excel` | ✓ 全局状态 |
| 292 | `已从缓存加载 {count} 个元素定义` | ✓ 带数量 |
| 321 | `飞书表格中无可用 sheet（prefix='{prefix}'）...` | ✓ 带前缀 |
| 341 | `已从飞书加载 {total} 个元素定义 ({len} 个 Sheet)` | ✓ 带统计 |
| 362 | `预期结果来源: 飞书云端（已更新本地缓存）` | ✓ 全局声明 |
| 365 | `飞书云端加载预期结果失败，回退缓存` | ✓ 全局回退 |
| 373 | `预期结果来源: 本地缓存` | ✓ 全局声明 |
| 386 | `飞书中无「预期结果」sheet 或数据不足，跳过` | ✓ 明确原因 |
| 390 | `已从飞书加载 {count} 个预期结果定义` | ✓ 带统计 |
| 413 | `已从缓存加载 {count} 个预期结果定义` | ✓ 带统计 |
| 437 | `已从本地 Excel 加载 {count} 个预期结果定义` | ✓ 带统计 |
| 487 | `预期结果【{key}】页面XML和检查元素均为空，跳过` | ✓ 带 key |
| 576 | `已从 {xlsx_path} 加载 {count} 个元素定义...` | ✓ 带路径和统计 |
| 695 | `元素索引构建完成: {count} 个元素, {index} 个索引词` | ✓ DEBUG 级别，带统计 |

---

### 2.5 ElementMatcher 匹配日志  ✓ 上下文已充分

| 行号 | 日志 | 评估 |
|---|---|---|
| 604 | `元素【{element_key}】locator 多设备匹配: {best_key}` | ✓ DEBUG，带 key |
| 737/739 | `【{tag}】{ctx} 未匹配到任何元素` | ✓ 带 tag + case context |
| 746-748 | `【{tag}】{ctx} 匹配到 {n} 个，无页面上下文，使用: {best}` | ✓ WARNING，带候选 |
| 768-771 | `【{tag}】{ctx} {n}个候选, 页面'{page}' → 选 {best}` | ✓ DEBUG，带详情 |
| 773-776 | `【{tag}】{ctx} 匹配到 {n} 个，页面'{page}'无匹配...` | ✓ WARNING，带候选 |

---

## 三、engine/executor.py（独立运行入口用）

### 3.1 `_run_step:131` — 不支持的操作类型  ⚠️ 中等

**当前代码：**
```python
logger.warning(f"步骤{step.seq}: 不支持的操作类型 '{step.action}'")
```

**问题：** 缺少 `step.tag`，有 step 编号但不知道具体内容。

**修复：**
```python
logger.warning(f"步骤{step.seq}: 【{step.tag}】不支持的操作类型 '{step.action}'")
```

---

### 3.2 `_run_step:140` — 未匹配到元素  ⚠️ 中等

**当前代码：**
```python
logger.warning(f"步骤{step.seq}: 【{step.tag}】未匹配到元素")
```

**评估：** 已有 `step.seq` + `step.tag`。OK，但缺少 case 上下文。

**修复：** 可选增强（executor 有 case_id 上下文）
```python
logger.warning(f"{case_id} 步骤{step.seq}: 【{step.tag}】未匹配到元素")
```

---

### 3.3 `_run_step:150` — 步骤执行失败  ✓ 已充分

**当前代码：**
```python
logger.error(f"FAILED  步骤{step.seq}: 【{step.tag}】{step.action} — {e}")
```

**评估：** 带有 step.seq, tag, action, 异常信息。OK。

---

### 3.4 `_check_one_expected:233` — 元素检查失败  ⚠️ 中等

与 test_excel_runner.py 1.2 相同问题，缺少 `ep.expected_key`。

**修复：**
```python
logger.error(f"预期结果【{ep.tag}】（key={ep.expected_key}）元素检查失败: {e}")
```

---

### 3.5 `_check_one_expected:248` — 无匹配设备内容  ⚠️ 中等

**修复：**
```python
logger.warning(f"预期结果【{ep.tag}】（key={ep.expected_key}）无匹配的设备内容，跳过")
```

---

### 3.6 `_check_one_expected:256-259` — XML 解析失败  ⚠️ 中等

**修复：**
```python
logger.error(
    f"预期结果【{ep.tag}】（key={ep.expected_key}）XML 解析失败: {e}\n"
    f"XML 前200字符: {content[:200]}"
)
```

---

### 3.7 其他 executor 日志 — 上下文已充分  ✓

| 行号 | 日志 | 评估 |
|---|---|---|
| 54 | `⏐ SKIPPED {case_id} — {reason}` | ✓ 带 case_id |
| 63 | `⏐ SKIPPED {case_id} — {validation_skip}` | ✓ 带 case_id |
| 66 | `⏐ START  {case_id}` | ✓ 带 case_id |
| 102 | `R{row} 预期结果【{tag}】未在预期结果 sheet 中匹配` | ✓ 带 row + tag |
| 122 | `⏐ PASSED  {case_id}` | ✓ 带 case_id |
| 264 | `步骤{seq} 预期结果 [{key}]:\n{result.summary()}` | ✓ 带 seq + key |

---

## 四、engine/parser.py

### 4.1 `validate_case:331` — 元素未匹配  ⚠️ 低

**当前代码：**
```python
return f"元素未匹配: {items}"
```

**实际输出：**
```text
SKIPPED (元素未匹配: 步骤2【本地笔记引导】、步骤4【创建菜单弹窗】...)
```

**评估：** `items` 格式为 `步骤{n}【{tag}】`，已有步骤号和 tag。OK。此消息通过 pytest.skip 或 case.skip_reason 传递，最终显示在测试结果中。

---

## 五、ui_ops/operations.py（结构化错误日志）

操作层的结构化错误日志（`retry_and_handle_exceptions` 装饰器）已经做到 7 个 `↳` 字段的详细输出，**此处不再改动**。格式：

```text
[{step_label}] 元素查找失败「{element_key}」（重试 {max_retries} 次）
  ↳ 定位方式: {locator_type}
  ↳ 定位值:   {locator_value}
  ↳ 元素键: {element_key}
  ↳ 数据来源: {file}::{sheet}
  ↳ 调用链: func1 → func2 → func3
  ↳ 元素用途: {catalog_description}
  ↳ 截图: {screenshot_path}
```

---

## 六、conftest.py

### 6.1 `pytest_collection_modifyitems:116` — 忽略用例  ✓ 已充分

```python
logging.warning(
    f"[IGNORE] 按规则忽略用例 {len(deselected)} 条，剩余 {len(selected)} 条；规则：{patterns}"
)
```

### 6.2 其他 conftest 日志  ✓ 已充分

Session 级别的设备检查、应用启动等日志均带有充分上下文。

---

## 七、改动汇总

### 必须改（影响日常排查）

| # | 文件 | 行 | 改什么 |
|---|---|---|---|
| 1 | `test_excel_runner.py` | 382-383 | `_dispatch_step` 增加 `skip` 分支为 no-op |
| 2 | `elements.py` | 133 | `_resolve_device_content` 加 `key` 参数，WARNING 附带 key |
| 3 | `elements.py` | 163 | `_check_elements_by_xpath` 加 `expected_key`/`step_seq` 参数，日志附带上下文 |
| 4 | `test_excel_runner.py` | 438 | 调用 `_check_elements_by_xpath` 时传入 `expected_key`/`step_seq` |
| 5 | `executor.py` | 226 | 同上 |

### 建议改（提升排查效率）

| # | 文件 | 行 | 改什么 |
|---|---|---|---|
| 6 | `test_excel_runner.py` | 445 | "元素检查失败" 加 `expected_key` |
| 7 | `test_excel_runner.py` | 460 | "无匹配设备内容" 加 `expected_key` |
| 8 | `test_excel_runner.py` | 468 | "获取 page_source 失败" 加 `expected_key` |
| 9 | `test_excel_runner.py` | 475-478 | "XML 解析失败" 加 `expected_key` |
| 10 | `executor.py` | 131 | "不支持的操作类型" 加 `step.tag` |
| 11 | `executor.py` | 233 | "元素检查失败" 加 `expected_key` |
| 12 | `executor.py` | 248 | "无匹配设备内容" 加 `expected_key` |
| 13 | `executor.py` | 256-259 | "XML 解析失败" 加 `expected_key` |
| 14 | `elements.py` | 483 | "缺少元素标识" 加行号 |
| 15 | `elements.py` | 146 | 调用 `_resolve_device_content` 处传入 key（2处） |

### 不改（已充分或非执行链路）

- `devices/info.py`：设备信息采集，上下文充分
- `core/feishu.py`：API 层，上下文充分
- `core/cleanup.py`：独立工具，上下文充分
- `core/health.py`：健康检查，上下文充分
- `ui_ops/operations.py`：结构化错误日志已足够详细
- `conftest.py`：Session 级别，上下文充分
- `engine/reporter.py`：结果汇总，上下文充分
- `engine/xml_checker.py`：纯数据对比，无日志
- `engine/parser.py`：validate_case 返回消息已充分

### 涉及文件

| 文件 | 改动数 |
|---|---|
| `engine/elements.py` | 5 处（函数签名 x3 + 调用方 x2 + 行号 x1） |
| `tests/test_excel_runner.py` | 6 处（skip 分支 + expected_key x4 + 调用传参 x1） |
| `engine/executor.py` | 6 处（expected_key x3 + step.tag x1 + 调用传参 x1 + 1） |

### 改动后日志效果对比

**改前：**
```text
14:29:51  WARNING  未知动作类型: skip
14:29:49  WARNING  多设备内容缺少默认块，仅有条件块: ['国内', '海外']...
14:28:50  INFO   预期可见检查通过: 6个元素均存在
```

**改后：**
```text
（skip 步骤不再输出 WARNING）
14:29:49  WARNING  预期结果【笔记首页.创建菜单弹窗】多设备内容缺少默认块，仅有条件块: ['国内', '海外']...
14:28:50  INFO   预期结果【笔记首页.创建菜单弹窗】（步骤4）检查通过: 6个元素均存在（可见模式）
```

每条日志都可独立定位到飞书表格的具体行。

### 验证方法

```bash
# 语法检查
python -m py_compile boox_automation/engine/elements.py
python -m py_compile boox_automation/tests/test_excel_runner.py
python -m py_compile boox_automation/engine/executor.py

# 跑用例验证日志输出
pytest boox_automation/tests/test_excel_runner.py -s -k "R2 or R3"
```
