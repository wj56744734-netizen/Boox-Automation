# 操作类型中文化实施方案

## 前因

飞书元素表 `操作类型` 列当前填英文（`click`），需全部改用中文。同时补全遗漏的操作类型：坐标点击、坐标长按、方向滑动、返回键。

## 一、操作分类

| 类型 | 触发方式 | 是否在飞书元素表中定义 |
|---|---|---|
| **元素级** | 步骤 `【】` tag 匹配元素 | 是，定义在元素表 |
| **设备级（硬编码）** | 步骤关键词直接触发，不用 `【】` | 否，纯关键词驱动 |

## 二、飞书元素表 `操作类型` 列（6 个值）

| 中文 | 内部值 | locator 格式 | 说明 |
|---|---|---|---|
| `点击` | `click` | XPath | 按钮/图标/菜单（**默认值**） |
| `输入` | `input` | XPath | 文本输入框 |
| `长按` | `long_press` | XPath | 长按元素 |
| `校验toast` | `assert_toast` | XPath | 校验 Toast 弹窗文本 |
| `点击坐标` | `click_coord` | `x,y` 比例 | 屏幕比例坐标点击，如 `0.5,0.3` |
| `长按坐标` | `long_press_coord` | `x,y` 比例 | 屏幕比例坐标长按 |

不填 = 自动推断（`suggest_action`），默认 `点击`。

### 坐标 locator 格式

```
0.5,0.3          → 屏幕宽50%、高30%的位置
0.8,0.5          → 屏幕宽80%、高50%的位置
```

支持多设备块（和 XPath locator 一致）：

```
0.5,0.3

国内：
0.5,0.3

海外：
0.5,0.35
```

### 飞书元素表示例

```
元素标识: 通用操作.屏幕中央        元素标识: 通用操作.左上角返回区
匹配文本: 屏幕中央                匹配文本: 左上角返回区
定位方式: 0.5,0.5                定位方式: 0.1,0.08
操作类型: 点击坐标                操作类型: 点击坐标
用途说明: 点击屏幕正中央            用途说明: 点击左上角返回箭头区域
```

---

## 三、步骤关键词映射（`_ACTION_MAP`）

```python
_ACTION_MAP = {
    # ── 点击类 → click ──
    "点击": "click",
    "打开": "click",
    "进入": "click",
    "选择": "click",
    "双击": "click",
    "退出": "click",
    "返回": "click",
    "清空": "click",
    "确认": "click",
    "关闭": "click",

    # ── 输入 ──
    "输入": "input",

    # ── 长按 ──
    "长按": "long_press",

    # ── 方向滑动（设备级硬编码，不用【】）──
    "上滑":     "swipe_up",
    "向上滑动":  "swipe_up",
    "下滑":     "swipe_down",
    "向下滑动":  "swipe_down",
    "左滑":     "swipe_left",
    "向左滑动":  "swipe_left",
    "右滑":     "swipe_right",
    "向右滑动":  "swipe_right",

    # ── 坐标操作（需【】匹配飞书元素，locator=x,y）──
    "点击坐标":  "click_coord",
    "长按坐标":  "long_press_coord",

    # ── 系统键（设备级硬编码，不用【】）──
    "按返回键":  "press_back",
    "返回键":    "press_back",
}
```

> 精确关键词（如 `向上滑动`）放泛关键词（如 `滑动`）前面，靠遍历顺序保证精确匹配优先。

### 用例步骤写法

```text
# J 列（操作步骤）

1. 点击【创建笔记】             ← 元素级，【】匹配元素表
2. 输入【笔记标题】测试名称     ← 元素级
3. 向下滑动                    ← 设备级硬编码，不用【】
4. 点击坐标【屏幕中央】         ← 元素级，【】匹配坐标元素
5. 左滑                       ← 设备级硬编码，不用【】
6. 按返回键                    ← 设备级硬编码，不用【】
7. 长按坐标【左上角返回区】     ← 元素级，【】匹配坐标元素
```

**规则：**
- 元素级操作（点击/输入/长按/校验toast/点击坐标/长按坐标）：步骤中写 `动作【匹配文本】`，需要飞书元素表有对应元素
- 设备级操作（方向滑动/返回键）：步骤中只写关键词，**不用 `【】`**，不在飞书元素表中定义
- "检查/查看/校验" 开头的步骤 → action=`skip`，不走 UI 操作

---

## 四、中→英翻译映射

```python
# 飞书元素表"操作类型"列加载时，中文→内部英文
_ACTION_CN_TO_EN = {
    "点击":          "click",
    "输入":          "input",
    "长按":          "long_press",
    "校验toast":     "assert_toast",
    "点击坐标":      "click_coord",
    "长按坐标":      "long_press_coord",
}
```

> 英文值也兼容：不在映射中的原样保留。设备级操作（swipe_*/press_back）不在此映射中，它们不由元素表驱动。

---

## 五、设备级步骤的调度修复

### 问题

当前 `test_excel_runner.py` 过滤掉了无 `element_key` 的步骤：

```python
for s in case.steps:
    if not s.element_key:
        s.status = "skip"
steps = [s for s in case.steps if s.element_key]  # ← 设备级步骤被丢弃
```

滑动、返回键等设备级步骤没有 `【】` tag → 没有 `element_key` → 被过滤 → 不执行。

### 修复

过滤时放行设备级 action：

```python
_DEVICE_ACTIONS = {"swipe_up", "swipe_down", "swipe_left", "swipe_right",
                   "press_back"}

for s in case.steps:
    if not s.element_key and s.action not in _DEVICE_ACTIONS:
        s.status = "skip"
steps = [s for s in case.steps if s.element_key or s.action in _DEVICE_ACTIONS]
```

`_dispatch_step` 中设备级 action 不依赖 `ek`：

```python
elif step.action in ("swipe_up", "swipe_down", "swipe_left", "swipe_right"):
    direction = step.action.replace("swipe_", "")
    method.swipe_direction(direction)

elif step.action == "click_coord":
    method.click_by_coord(ek)  # ek 的 locator 是 "x,y"

elif step.action == "long_press_coord":
    method.long_press_by_coord(ek)

elif step.action == "press_back":
    method.press_back()
```

---

## 六、代码改动清单

### 6.1 `engine/parser.py`

| # | 位置 | 改动 |
|---|---|---|
| 1 | L8-21 `_ACTION_MAP` | 扩展：4 个滑动方向 + 坐标操作 + 返回键 |
| 2 | 模块级 | 新增 `_DEVICE_ACTIONS` 集合 |

### 6.2 `engine/elements.py`

| # | 位置 | 改动 |
|---|---|---|
| 3 | 模块级 | 新增 `_ACTION_CN_TO_EN` 映射，`_DEVICE_ACTIONS`（从 parser import） |
| 4 | `_parse_row` | action 字段：`val_str` 通过 `_ACTION_CN_TO_EN` 翻译后再存储 |

### 6.3 `ui_ops/operations.py`

| # | 改动 | 说明 |
|---|---|---|
| 5 | 新增 `swipe_direction(direction)` | `direction`: up/down/left/right，全屏滑动 |
| 6 | 新增 `click_by_coord(element_key)` | 从元素 locator 解析 `x,y` 比例坐标后 tap |
| 7 | 新增 `long_press_by_coord(element_key, duration=2)` | 同上，长按 |
| 8 | 新增 `press_back()` | `driver.press_keycode(4)` |

### 6.4 `tests/test_excel_runner.py`

| # | 位置 | 改动 |
|---|---|---|
| 9 | L317-320 | 过滤逻辑：放行 `_DEVICE_ACTIONS` |
| 10 | `_dispatch_step` | 新增 7 个 action 分支 |

### 6.5 `engine/executor.py`

| # | 位置 | 改动 |
|---|---|---|
| 11 | L34-39 `_handlers` | 新增 handler 注册 |
| 12 | 新增方法 | `_handle_swipe_up/_down/_left/_right`、`_handle_click_coord`、`_handle_long_press_coord`、`_handle_press_back` |
| 13 | L125-141 `_run_step` | 放行设备级 action（不要求 element_key） |

### 6.6 文档同步

| # | 文件 | 改动 |
|---|---|---|
| 14 | `CLAUDE.md` | 更新元素表规范：操作类型中文值 + 坐标格式 + 步骤关键词表 |
| 15 | `boox_automation/docs/使用指南.md` | 同步更新操作类型章节 |
| 16 | 飞书元素表（各 sheet 第 1 行） | 更新使用说明注释行 |

---

## 七、CLAUDE.md 更新内容

### 7.1 元素表规范（替换当前 L196-210）

**6 列结构：**

| 中文表头 | 英文兼容 | 必填 | 说明 |
|---|---|---|---|
| 元素标识 | key | ✓ | 格式 `页面名.元素名`，全局唯一 |
| 匹配文本 | match | | 测试步骤中 `【】` 内的文字 |
| 定位方式 | locator | ✓ | XPath / 纯文本 / 坐标 `x,y`，支持多设备「键：」分块 |
| 操作类型 | action | | 中文值，不填自动推断 |
| 用途说明 | operation | | 日志/截图中的元素描述 |
| 序号 | index | | 同 match 多元素时区分 |

**操作类型（中文）：**

| 值 | 说明 | locator 格式 |
|---|---|---|
| `点击` | 点击元素（**默认值**） | XPath |
| `输入` | 输入文本 | XPath |
| `长按` | 长按元素 | XPath |
| `校验toast` | 校验 Toast 提示 | XPath |
| `点击坐标` | 按屏幕比例坐标点击 | `x,y` 如 `0.5,0.3` |
| `长按坐标` | 按屏幕比例坐标长按 | `x,y` 如 `0.5,0.3` |

`assert`/`assert_not`/`assert_text`/`dismiss` — **已废弃**，页面/弹窗验证统一由 K 列预期结果完成。

### 7.2 步骤关键词表（新增到 CLAUDE.md）

| 步骤关键词 | 动作 | 是否需 `【】` 元素匹配 |
|---|---|---|
| 点击/打开/进入/选择/双击/退出/返回/清空/确认/关闭 | `点击` | 是 |
| 输入 | `输入` | 是 |
| 长按 | `长按` | 是 |
| 上滑/向上滑动/下滑/向下滑动/左滑/向左滑动/右滑/向右滑动 | 方向滑动 | **否**，纯关键词触发 |
| 点击坐标 | `点击坐标` | 是，locator 为 `x,y` |
| 长按坐标 | `长按坐标` | 是，locator 为 `x,y` |
| 按返回键/返回键 | 系统返回键 | **否**，纯关键词触发 |
| 检查/查看/校验（步骤开头） | 跳过 | —，由 K 列预期结果接管 |

---

## 八、使用指南更新内容

替换 `使用指南.md` 中"步骤关键词"表格（L96-105）为：

```markdown
| 写在步骤里的词 | 程序做的事 | 是否需要【】 | 示例 |
|---|---|---|---|
| `点击` `打开` `进入` `选择` `双击` `退出` `返回` `清空` `确认` `关闭` | 点击元素 | 是 | `点击【创建笔记】` |
| `输入` | 在输入框里填内容 | 是 | `输入【笔记标题】测试名称` |
| `长按` | 长按元素 | 是 | `长按【笔记条目】` |
| `点击坐标` | 按比例坐标点击 | 是 | `点击坐标【屏幕中央】` |
| `长按坐标` | 按比例坐标长按 | 是 | `长按坐标【左上角】` |
| `上滑` `向上滑动` `下滑` `向下滑动` `左滑` `向左滑动` `右滑` `向右滑动` | 全屏方向滑动 | **否** | `向下滑动` |
| `按返回键` `返回键` | 按系统返回键 | **否** | `按返回键` |

> **注意：** `检查`/`查看`/`校验` 开头的步骤会被跳过（由 K 列预期结果检查）。方向滑动和返回键是硬编码设备操作，**不要在步骤中写 `【】`**。
```

替换元素表 `action` 列说明（L291-297）为操作类型中文值表格。

---

## 九、不涉及的范围

- 等待（`wait`）— 不需要
- 滑动次数参数 — 暂不需要
- 内部 action 存储 — 全部保持英文不变
- 日志 action 名中文化 — 后续单独做
- 飞书现有数据 — 英文值兼容，无需迁移；新元素建议用中文

---

## 十、验证

```bash
# 语法检查
python -m py_compile boox_automation/engine/parser.py
python -m py_compile boox_automation/engine/elements.py
python -m py_compile boox_automation/tests/test_excel_runner.py
python -m py_compile boox_automation/ui_ops/operations.py

# 关键词解析验证
python3 -c "
from boox_automation.engine.parser import _detect_action
tests = ['向左滑动', '左滑', '点击坐标【屏幕中央】', '向下滑动', '按返回键', '点击【创建笔记】']
for t in tests:
    tag = '屏幕中央' if '【' in t else ''
    print(f'{t:25s} → {_detect_action(t, tag)}')
"
```
