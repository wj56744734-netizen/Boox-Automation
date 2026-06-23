# 前置条件文件检查 & 测试步骤 ADB 命令 — 实施方案

> 版本: v1.1 | 日期: 2026-06-23 | 状态: 待实施

---

## 一、概述

在飞书元素表下新增两个 Sheet，不改动现有表格结构。

| 功能 | Sheet 名 | 触发位置 | 说明 |
|---|---|---|---|
| 前置条件 — 文件检查 | `前置条件` | 用例表 G 列 | 用例执行前检查设备文件是否存在，不满足则 skip |
| 测试步骤 — ADB 命令 | `ADB命令` | 用例表 H 列 | 测试步骤中执行任意 adb 命令，只记日志不重试不联动断言 |

---

## 二、Sheet 定义

### 2.1 `前置条件`（4 列）

| 列 | 中文名 | 必填 | 说明 |
|---|---|---|---|
| A | 条件名称 | ✓ | G 列 `【】` 内文字匹配此列 |
| B | 检查类型 | ✓ | `文件存在` 或 `文件不存在` |
| C | 文件路径 | ✓ | 设备路径，如 `/sdcard/笔记自动化测试文件/从本地文件/喻世明言.pdf`，支持多设备块 |
| D | 用途说明 | | 人类可读描述 |

**用例表 G 列**：每行提取 `【】` 内容匹配，外面文字给人看，不影响解析。

```
1. 新设备或重置设备后未打开过笔记
2. 没有登录过账号
3.【清理应用数据】
4.检查设备【测试文件】是否存在
```

第 4 行提取到 `测试文件` → 内置关键字未命中 → 去「前置条件」sheet 找 A 列=`测试文件` → 找到 → 执行文件检查。

**系统拼装**：

| B 列 | 命令 |
|---|---|
| `文件存在` | `adb -s <id> shell "test -f <C列路径>"` |
| `文件不存在` | `adb -s <id> shell "test ! -f <C列路径>"` |

### 2.2 `ADB命令`（3 列）

| 列 | 中文名 | 必填 | 说明 |
|---|---|---|---|
| A | 命令名称 | ✓ | H 列 `【】` 内文字匹配此列 |
| B | adb命令 | ✓ | 完整命令（不含 `adb` 前缀），如 `shell am broadcast -a ...`，支持多设备块 |
| C | 用途说明 | | 人类可读描述 |

**用例表 H 列**：语法与 UI 元素完全一致。

```
10. 输入命令【生成笔画】检查
11. 点击【退出手写笔记】
```

`10. 输入命令【生成笔画】检查` → 提取 `生成笔画` → 匹配到 ADB命令 sheet → D 列=`adb命令` → 执行 B 列命令。

外面的 `输入命令...检查` 是给人看的，解析时不影响——只有 `检查/查看/校验` 开头才会触发 skip 模式，`输入命令` 不会。

**系统执行**：拼接 `adb -s <device_id> <B列命令>` → `subprocess.run()`。

- exit 0 → `INFO [ADB命令] 执行成功: 生成笔画`
- exit ≠ 0 → `ERROR [ADB命令] 执行失败: 生成笔画 | exit=X | stderr: ...`
- 超时（config.yaml `adb.command_timeout`，默认 10s）→ `ERROR [ADB命令] 执行超时: 生成笔画`
- **不重试、不联动 I 列断言、失败不中断用例**

---

## 三、用户测试数据校验

用户已填数据：

**前置条件 Sheet**：

| A | B | C | D |
|---|---|---|---|
| 测试文件 | 文件存在 | /sdcard/笔记自动化测试文件/从本地文件/喻世明言.pdf | |

✅ 格式正确。

**ADB命令 Sheet**：

| A | B | C |
|---|---|---|
| 生成笔画 | shell am broadcast -a com.onyx.android.note.test.add_custom_shape --ei test_shape_type_index 1 --es test_shape_pressure "0,500#10" --ei test_shape_line_style_index 3 --ei test_shape_stroke_width 10 --ei test_shape_color_index 6 --ei test_shape_count 3 --es test_shape_start_end_point "100,100,1000,100#100,200,1000,200" --ez test_shape_draw_line_path false | 测试生成笔画 |

✅ 格式正确。B 列不含 `adb` 前缀，系统会自动拼接。

**用例表 G 列**：

```
1. 新设备或重置设备后未打开过笔记              → 描述型，正确
2. 没有登录过账号                              → 描述型，正确
3.【清理应用数据】                              → 清理型，正确
4.检查设备【测试文件】是否存在                   → 提取 测试文件 → file_check ✅
```

**用例表 H 列**：

```
...（前略）
10. 输入命令【生成笔画】检查                     → 提取 生成笔画 → adb_cmd ✅
11. 点击【退出手写笔记】                         → 提取 退出手写笔记 → click ✅
12. 检查【检查笔记-1】手写笔记命名和是否显示正常   → 检查开头 → skip → I列断言 ✅
```

⚠️ 注意：原数据两个步骤 10，第二个已改为 11，后续顺延（12）。

---

## 四、代码改动

### 4.1 改动清单

| # | 文件 | 改动 |
|---|---|---|
| 1 | `config.yaml` | 新增 `adb.command_timeout: 10` |
| 2 | `core/config.py` | 新增 `adb_command_timeout()` |
| 3 | `engine/schema.py` | 新增 `前置条件` 4 列 + `ADB命令` 3 列的索引常量 |
| 4 | `engine/elements.py` | `_ACTION_CN_TO_EN` 加 `"adb命令": "adb_cmd"`；加载 `前置条件`/`ADB命令` sheet；`suggest_action` 加 `"adb_cmd"` |
| 5 | `engine/parser.py` | `parse_preconditions()` 对未命中内置关键字的 `【】` 标记为 `file_check_candidate`；新增 `_check_file()`；`check_conditions()` 新增 device_id 参数 |
| 6 | `conftest.py` | `check_conditions()` 传入 `device_id` |
| 7 | `ui_ops/operations.py` | 新增 `execute_adb_command()` |
| 8 | `tests/test_excel_runner.py` | `_dispatch_step()` 新增 `adb_cmd` 分支 |
| 9 | `CLAUDE.md` + `README.md` | 已更新 ✅ |

### 4.2 关键改动细节

#### 4.2.1 `engine/schema.py` — 新增常量

```python
# 前置条件 Sheet 4 列: 条件名称 | 检查类型 | 文件路径 | 用途说明
PRECOND_COL_NAME = 0
PRECOND_COL_CHECK_TYPE = 1
PRECOND_COL_PATH = 2
PRECOND_COL_DESC = 3

# ADB命令 Sheet 3 列: 命令名称 | adb命令 | 用途说明
ADB_CMD_COL_NAME = 0
ADB_CMD_COL_COMMAND = 1
ADB_CMD_COL_DESC = 2
```

#### 4.2.2 `engine/elements.py` — 核心改动

**1) `_ACTION_CN_TO_EN` 新增**：

```python
"adb命令": "adb_cmd",
```

**2) `ElementLoader` 新增属性**：

```python
self._preconditions: dict[str, dict] = {}
self._adb_commands: dict[str, dict] = {}
```

**3) Sheet 加载逻辑**：在 `_load_from_cloud` / `_load_excel` 的 sheet 遍历中，遇到 `前置条件` 和 `ADB命令` sheet 时特殊处理：

- `前置条件` → 解析行 → 以 A 列为 key 存入 `_preconditions`
- `ADB命令` → 构造元素行（模块=ADB命令, 匹配文本=A列, locator=B列, action=adb命令）→ 同时写入 `_elements`，复用 ElementMatcher 索引

**4) `ElementMatcher.suggest_action()`**：`valid_actions` 新增 `"adb_cmd"`。

**5) 新增公开方法**：

```python
def get_precondition(self, name: str) -> dict | None:
    self._ensure_loaded()
    return self._preconditions.get(name)
```

**6) 缓存**：`_save_to_cache` / `_load_from_cache` 新增 `_preconditions` / `_adb_commands` 持久化。

#### 4.2.3 `engine/parser.py` — 解析改动

**`parse_preconditions()`**：对不匹配内置关键字的 `【】` 内容，不再直接归为 descriptive，而是标记为 `file_check_candidate`：

```python
# 旧逻辑（第 166 行）：
preconditions.append(Precondition(raw=line, type="descriptive"))

# 新逻辑：有 tag 但不匹配内置关键字 → file_check_candidate
if tags:
    preconditions.append(Precondition(
        raw=tags[0].strip(),
        type="file_check_candidate",
        kind=tags[0].strip(),
        skip_reason=f"前置条件不满足: 【{tags[0].strip()}】",
    ))
else:
    preconditions.append(Precondition(raw=line, type="descriptive"))
```

**`check_conditions()`**：新增 `device_id` 参数，新增 `file_check_candidate` 分支：

```python
def check_conditions(preconditions, device_info, device_id="") -> str | None:
    for pc in preconditions:
        if pc.type == "condition":
            ...
        elif pc.type == "file_check_candidate":
            loader = get_element_loader()
            pc_info = loader.get_precondition(pc.kind)
            if pc_info:
                ok, reason = _check_file(pc_info, device_info, device_id)
                if not ok:
                    return reason
        ...
```

**新增 `_check_file()`**：

```python
def _check_file(pc_info, device_info, device_id) -> tuple[bool, str]:
    check_type = pc_info.get("check_type", "文件存在")
    path_raw = pc_info.get("path", "")
    path = _resolve_device_content(path_raw, device_info)
    if not path:
        return True, ""
    path = path.strip()
    is_exists = check_type == "文件存在"
    flag = "-f" if is_exists else "! -f"
    cmd = ["adb", "-s", device_id, "shell", f"test {flag} {path}"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        return True, ""
    reason = f"文件{'不存在' if is_exists else '仍存在'} — {path}"
    return False, f"前置条件不满足: {reason}"
```

#### 4.2.4 `conftest.py`

`note_test_initial` fixture 中 `check_conditions()` 调用传入 `device_id`：

```python
runtime_skip = check_conditions(case.preconditions, device_info, device_id=device_id)
```

#### 4.2.5 `ui_ops/operations.py` — 新增方法

```python
def execute_adb_command(self, element_key: str):
    import subprocess, shlex
    from boox_automation.core.config import adb_command_timeout
    from boox_automation.engine.elements import ElementLoader, _resolve_device_content
    from boox_automation.devices.info import Device_basic_information

    info = self.get_element(element_key)
    loc_str = (info['locator'][1] if isinstance(info.get('locator'), (list, tuple))
               else str(info.get('locator', '')))
    cmd_name = info.get('match', element_key)

    # 多设备块解析
    device_info = ElementLoader._get_device_info()
    adb_cmd = _resolve_device_content(loc_str, device_info) or loc_str

    # 获取 device_id
    device_id = ""
    try:
        dbi = Device_basic_information()
        device_id = dbi.get_connected_device_ids()
    except Exception:
        pass

    full_cmd = f"adb -s {device_id} {adb_cmd}" if device_id else f"adb {adb_cmd}"
    timeout = adb_command_timeout()

    with allure.step(f"ADB命令「{cmd_name}」"):
        try:
            result = subprocess.run(
                shlex.split(full_cmd), capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            logging.error(f"[ADB命令] 执行超时({timeout}s): {cmd_name}")
            return

    if result.returncode == 0:
        logging.info(f"[ADB命令] 执行成功: {cmd_name}")
        if result.stdout:
            logging.debug(f"[ADB命令] stdout: {result.stdout.strip()}")
    else:
        stderr = (result.stderr or "").strip()
        logging.error(
            f"[ADB命令] 执行失败: {cmd_name} | "
            f"exit={result.returncode} | stderr: {stderr}")
```

**注意**：使用 `shlex.split()` 处理含引号的命令参数（如 `"0,500#10"`），避免 `str.split()` 破坏参数中的空格。

#### 4.2.6 `tests/test_excel_runner.py`

`_dispatch_step()` 新增：

```python
elif step.action == "adb_cmd":
    method.execute_adb_command(ek)
```

---

## 五、运行时流程

### 5.1 前置条件文件检查

```
parse_preconditions("4.检查设备【测试文件】是否存在")
  → _TAG_RE 提取 ["测试文件"]
  → "测试文件" 不在内置关键字 → type="file_check_candidate", kind="测试文件"

test_case()
  → check_conditions(preconditions, device_info, device_id="xxx")
    → pc.type="file_check_candidate"
    → loader.get_precondition("测试文件")
      → 命中: {check_type:"文件存在", path:"/sdcard/...", ...}
      → _check_file(pc_info, device_info, device_id)
        → _resolve_device_content(path) → "/sdcard/..."
        → subprocess: adb -s xxx shell "test -f /sdcard/..."
        ├─ exit 0 → return None (继续执行)
        └─ exit≠0 → return "前置条件不满足: 文件不存在 — /sdcard/..."
  → runtime_skip 非空 → pytest.skip()
```

### 5.2 ADB 命令执行

```
_resolve_case_elements()
  → step.tag="生成笔画"
  → ElementMatcher.match("生成笔画", page_context="笔记首页")
    → key="ADB命令.生成笔画"  (A列=生成笔画, 模块=ADB命令)
  → suggest_action("ADB命令.生成笔画") → "adb_cmd"
  → step.action = "adb_cmd"

test_case()
  → _dispatch_step(method, public, step)
    → step.action == "adb_cmd"
    → method.execute_adb_command("ADB命令.生成笔画")
      → get_element_info() → locator=["xpath", "shell am broadcast ..."]
      → _resolve_device_content() → "shell am broadcast ..."
      → subprocess: adb -s xxx shell am broadcast ...
      ├─ exit 0 → INFO: [ADB命令] 执行成功: 生成笔画
      └─ exit≠0 → ERROR: [ADB命令] 执行失败: 生成笔画 | exit=1 | ...
```

---

## 六、配置变更

`config.yaml` 新增：

```yaml
adb:
  command_timeout: 10      # ADB命令 Sheet 中命令的执行超时（秒）
```

`core/config.py` 新增：

```python
def adb_command_timeout():
    return get_int("adb.command_timeout", 10)
```

---

## 七、实施步骤

| 步骤 | 内容 |
|---|---|
| 1 | `config.yaml` + `core/config.py` 新增 `adb.command_timeout` |
| 2 | `engine/schema.py` 新增 `PRECOND_COL_*` / `ADB_CMD_COL_*` 常量 |
| 3 | `engine/elements.py` — 加载两个新 sheet + `adb_cmd` action + 缓存 |
| 4 | `engine/parser.py` — `parse_preconditions` file_check_candidate + `_check_file` + `device_id` 参数 |
| 5 | `conftest.py` — `check_conditions` 传入 `device_id` |
| 6 | `ui_ops/operations.py` — 新增 `execute_adb_command()` |
| 7 | `tests/test_excel_runner.py` — 新增 `adb_cmd` dispatch |
| 8 | `python -m py_compile` 语法检查 |
| 9 | 端到端验证 — 跑用户已填的测试用例 |

---

## 八、边界与风险

1. **ADB命令 Sheet 被当作通用元素加载**：A 列=`生成笔画`，模块固定为 `ADB命令`，B 列为命令文本。会出现在元素索引中，但不会干扰其他模块的匹配。

2. **命令含引号**：用户命令中有 `"0,500#10"` 等参数，`shlex.split()` 能正确分词。

3. **两个新 sheet 不存在时**：静默跳过（WARNING 日志），已有用例不受影响。

4. **`【】` 在 G 列既不是内置关键字也不在「前置条件」sheet**：降级为 descriptive，不阻断。
