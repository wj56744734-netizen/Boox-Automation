"""
元素加载器：从 elements.xlsx 读取元素定位配置，将字符串类型转为 selenium By 常量。

约定：
  - 每个 Sheet 对应一个页面，Sheet 名 = 页面名
  - 每个元素包含 'locator' 字段，格式为 [type_string, value_string]
  - type_string 支持: id, xpath, class_name
  - 可选字段: match, action, operation, index
  - locator 列支持多设备「键：」分块格式
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

LOCATOR_TYPE_MAP = {
    'id': By.ID,
    'xpath': By.XPATH,
    'class_name': By.CLASS_NAME,
}

logger = logging.getLogger(__name__)

# 飞书元素表「操作类型」列中文→内部英文映射
_ACTION_CN_TO_EN = {
    "点击": "click",
    "输入": "input",
    "长按": "long_press",
    "校验toast": "assert_toast",
    "点击坐标": "click_coord",
    "长按坐标": "long_press_coord",
    "滑动": "swipe_coord",
}



# ---- 多设备块解析（元素 C 列 + 预期结果 C 列通用） ----

# 预期结果 sheet 名格式: 预期结果【模块名】
_EXPECTED_SHEET_MODULE_RE = re.compile(r"预期结果【(.+?)】")

# 表头关键字（用于自动检测哪行是表头）
_HEADER_KEYWORDS = {"模块", "元素标识", "匹配文本", "定位方式", "定位元素", "操作类型", "操作", "页面XML", "xml页面", "检查元素", "用途说明", "断言存在", "断言不存在", "断言toast", "断言toast不出现"}


def _find_header_row(rows: list, default: int = 1) -> int:
    """自动检测表头行位置。任意行含表头关键字即视为表头行。

    Returns: 表头行索引，未找到返回 default。
    """
    for i, row in enumerate(rows):
        if not row:
            continue
        texts = {str(c).strip() for c in row if c}
        if _HEADER_KEYWORDS & texts:
            return i
    return default


from boox_automation.devices.registry import device_list

_EXPECTED_ACTION_MAP = {
    "断言存在": "visible",
    "断言不存在": "not_visible",
    "断言toast": "toast",
    "断言toast不出现": "toast_not",
}

_VALID_EXPECTED_ACTIONS = set(_EXPECTED_ACTION_MAP.keys())

# 从设备 YAML 模型动态推导有效设备键（region/type/size/colour 的枚举值）
_VALID_DEVICE_KEYS: set[str] = set()
for _attrs in device_list.values():
    for _field in ("region", "type", "size", "colour"):
        _val = str(_attrs.get(_field, "")).strip()
        if _val and _val.lower() != "none":
            _VALID_DEVICE_KEYS.add(_val)


def _is_device_key(text: str) -> bool:
    """判断字符串是否为有效的设备条件键。"""
    text = text.strip()
    if text in _VALID_DEVICE_KEYS:
        return True
    import re
    if re.match(r'^\d+\.\d+$', text):
        return True
    if "," in text:
        parts = [p.strip() for p in text.split(",")]
        return all(_is_device_key(p) for p in parts)
    return False


def _parse_device_blocks(raw: str) -> dict[str, str]:
    """解析多设备块格式为 {键: 内容} 字典。

    格式:
      默认内容（不带前缀的块，必填，放在最前面）
      键：
      设备专属内容
      键：
      设备专属内容

    返回: {'__default__': '默认内容', '键': '设备专属内容', ...}
           单一块（无设备键行）返回 {'__default__': raw}
           空输入返回 {}
    """
    if not raw or not raw.strip():
        return {}

    raw = raw.strip()
    blocks: dict[str, str] = {}
    current_key = "__default__"
    current_lines: list[str] = []

    for line in raw.split('\n'):
        stripped = line.strip()
        if stripped and (stripped.endswith('：') or stripped.endswith(':')):
            key_candidate = stripped.rstrip('：:')
            if _is_device_key(key_candidate):
                if current_lines:
                    blocks[current_key] = '\n'.join(current_lines).strip()
                current_key = key_candidate
                current_lines = []
                continue
        current_lines.append(line)

    if current_lines:
        blocks[current_key] = '\n'.join(current_lines).strip()

    return blocks


def _device_key_matches(key: str, device_info: dict) -> bool:
    """检查设备是否匹配某个条件键。"""
    key = key.strip()
    parts = [p.strip() for p in key.split(",")]

    device_type = device_info.get("devices_reader", "")
    device_size = device_info.get("device_size", "")
    device_region = device_info.get("device_region", "")
    device_colour = device_info.get("driver_colour", "")
    version = device_info.get("version_info", "").split("-")[0]

    for p in parts:
        if p in (device_type, device_size, device_region, device_colour, version):
            continue
        return False
    return True


def _resolve_best_device_key(keys: set[str], device_info: dict) -> str:
    """从可用键中选择最佳匹配（最多条件项的胜出）。

    返回: 最佳匹配的键，或 '__default__'
    """
    best_key = "__default__"
    best_score = -1

    for key in keys:
        if key == "__default__":
            continue
        if _device_key_matches(key, device_info):
            score = len([p.strip() for p in key.split(",")])
            if score > best_score:
                best_score = score
                best_key = key

    return best_key


def _resolve_device_content(raw: str, device_info: dict, key: str = "") -> str | None:
    """从多设备格式内容中解析当前设备对应的块。

    元素 C 列和预期结果 C 列共用此函数。
    """
    if not raw or not raw.strip():
        return None

    blocks = _parse_device_blocks(raw)
    if not blocks:
        return None

    if "__default__" not in blocks:
        ctx = f"预期结果/元素【{key}】" if key else "多设备内容"
        logger.warning(
            f"{ctx}缺少默认块，仅有条件块: {list(blocks.keys())}。"
            f"未匹配到条件的设备将跳过"
        )

    best_key = _resolve_best_device_key(set(blocks.keys()), device_info)
    content = blocks.get(best_key)
    if best_key == "__default__" and not content and len(blocks) > 1:
        ctx = f"预期结果/元素【{key}】" if key else "多设备内容"
        logger.warning(
            f"{ctx} 当前设备未匹配到任何条件块（可用: {sorted(blocks.keys())}），"
            f"且默认块为空，操作将跳过或失败。"
            f"请检查设备信息（type/region/size）是否与元素表中的设备键匹配"
        )
    return content


def _load_expected_from_file(key: str) -> str | None:
    """从本地文件加载预期结果 XML 内容。"""
    file_path = Path(__file__).parent.parent / "data" / "expected_pages" / f"{key}.xml"
    if file_path.exists():
        return file_path.read_text(encoding='utf-8')
    return None


def _check_elements_by_xpath(xpath_text: str, mode: str,
                              expected_key: str = "", step_seq: int = 0) -> None:
    """逐 XPath 检查元素存在性。

    Args:
        xpath_text: 多行 XPath 文本（长时已通过 _resolve_device_content 解析）
        mode: visible（所有 XPath 均存在 = pass）或 not_visible（所有 XPath 均不存在 = pass）
        expected_key: 预期结果 key（用于日志上下文）
        step_seq: 步骤序号（用于日志上下文）
    """
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import TimeoutException
    from boox_automation.driver import driver

    raw_lines = [line.strip() for line in xpath_text.split('\n') if line.strip()]
    if not raw_lines:
        raise ValueError("检查元素为空")

    # 解析每行：格式为 '//xpath[,期望文本]'
    # 在引号外的第一个中文或逗号之后视为期望文本
    import re as _re
    items = []  # [(xpath, expected_text)]

    for line in raw_lines:
        # 跳过引号内的字符，找到引号外的第一个中文/逗号
        in_quote = False
        quote_char = ''
        xpath_end = len(line)
        for i, ch in enumerate(line):
            if ch in ('"', "'") and (in_quote is False or ch == quote_char):
                in_quote = not in_quote
                if in_quote:
                    quote_char = ch
                else:
                    quote_char = ''
                continue
            if not in_quote and ('一' <= ch <= '鿿' or ch in (',', '，')):
                xpath_end = i
                break

        xpath = line[:xpath_end].rstrip(' ,，;；')
        if not (xpath.startswith('/') or xpath.startswith('(')):
            ctx = f"预期结果【{expected_key}】（步骤{step_seq}）" if expected_key else "元素检查"
            raise ValueError(
                f"{ctx}D列检查元素不是有效 XPath: {xpath[:80]}\n"
                f"  请检查飞书元素表「预期结果」sheet 的 D 列，该行内容看起来是中文描述而非 XPath"
            )

        # 提取期望文本（英文逗号后的部分），去首尾空白
        expected_text = ""
        if xpath_end < len(line):
            tail = line[xpath_end:].lstrip(' ,，;；')
            if tail:
                expected_text = tail

        items.append((xpath, expected_text))

    missing = []
    found = []
    text_mismatch = []  # [(xpath, expected, actual)]
    from boox_automation.core.config import timeout_default
    check_timeout = timeout_default()

    for xpath, expected_text in items:
        try:
            el = WebDriverWait(driver, check_timeout).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            if expected_text:
                actual = (el.text or "").strip()
                expected_text = expected_text.replace("\\n", "\n")
                if actual != expected_text:
                    text_mismatch.append((xpath, expected_text, actual))
                    continue
            found.append(xpath)
        except TimeoutException:
            missing.append(xpath)

    ctx = f"预期结果【{expected_key}】（步骤{step_seq}）" if expected_key else "元素检查"
    has_failure = bool(missing) or bool(text_mismatch)
    if mode == 'not_visible':
        status = "失败" if found else "通过"
        lines = [f"{ctx}检查{status} ({len(items)}个):"]
        for xp, expected_text in items:
            if xp in found:
                lines.append(f"  ↳ ✗ 仍可见: {xp}")
            else:
                lines.append(f"  ↳ ✓ 不存在: {xp}")
        if found:
            logger.info("\n".join(lines))
            raise AssertionError(lines[0])
        logger.debug("\n".join(lines))
    else:
        ok = len(found)
        total = len(items)
        status = "通过" if not has_failure else "失败"
        lines = [f"{ctx}检查{status} ({ok}/{total}):"]
        for xp, expected_text in items:
            if xp in missing:
                lines.append(f"  ↳ ✗ 未找到: {xp}")
            elif xp in [t[0] for t in text_mismatch]:
                _, exp, act = next(t for t in text_mismatch if t[0] == xp)
                lines.append(f"  ↳ ✗ 文本不符: {xp}")
                lines.append(f"              期望: {exp!r}")
                lines.append(f"              实际: {act!r}")
            else:
                detail = f"  文本: {expected_text!r}" if expected_text else ""
                lines.append(f"  ↳ ✓ 存在:   {xp}{detail}")
        if has_failure:
            logger.info("\n".join(lines))
            raise AssertionError(lines[0])
        logger.debug("\n".join(lines))


_ELEMENT_LOADER_INSTANCE = None


def get_element_loader():
    """获取全局唯一的 ElementLoader 实例（单例）。"""
    global _ELEMENT_LOADER_INSTANCE
    if _ELEMENT_LOADER_INSTANCE is None:
        _ELEMENT_LOADER_INSTANCE = ElementLoader()
    return _ELEMENT_LOADER_INSTANCE


class ElementLoader:
    """
    元素加载器：读取 Excel 定义，按 key 返回标准化后的元素信息字典。

    Usage:
        loader = ElementLoader()
        info = loader.get_element_info("手写笔记.退出手写笔记")
    """

    def __init__(self):
        self._elements: dict = {}
        self._key_source: dict = {}  # element_key → sheet name
        self._expected_results: dict = {}      # key → expected page info
        self._expected_match_index: dict = {}  # match文本 → key
        # 诊断信息：记录预期结果加载过程
        self._expected_modules: list[str] = []
        self._expected_sheets_found: list[str] = []
        self._expected_sheets_missing: list[str] = []
        self._auto_discover()

    def _auto_discover(self):
        """自动加载元素定义（云端优先 → 缓存兜底 → 本地 Excel）。

        元素和预期结果各自独立回退，预期结果加载不受元素加载异常影响。
        """
        from boox_automation.core.feishu import (
            use_local_excel, check_feishu_reachable,
            load_cache, save_cache, get_cache_age,
        )

        # ── 阶段1：加载元素 ──
        if use_local_excel():
            logger.debug("元素加载路径: 本地 Excel（USE_LOCAL_EXCEL=1）")
            self._load_from_local_xlsx()
        elif check_feishu_reachable():
            logger.debug("元素加载路径: 飞书云端")
            try:
                self._load_from_cloud()
                self._save_to_cache()
                logger.info(f"元素来源: 飞书云端（已更新本地缓存）")
            except Exception:
                logger.warning(
                    "飞书云端加载元素失败，回退缓存。如已修改飞书在线文档但未生效，"
                    "请删缓存后重试: rm boox_automation/data/.cache/elements.json",
                    exc_info=True,
                )
                if not self._load_from_cache():
                    logger.warning("无可用缓存，回退本地 Excel")
                    self._load_from_local_xlsx()
        else:
            logger.debug("元素加载路径: 本地缓存")
            if self._load_from_cache():
                age = get_cache_age("elements")
                logger.warning(
                    f"元素来源: 本地缓存（{age}）。"
                    f"如飞书在线文档已有更新，请删缓存后重试: "
                    f"rm boox_automation/data/.cache/elements.json"
                )
            else:
                logger.debug("元素加载路径: 本地 Excel（兜底）")
                logger.warning("无可用缓存，回退本地 Excel")
                self._load_from_local_xlsx()

        # ── 阶段2：加载预期结果（独立回退，失败直接中断测试）──
        self._load_expected_results()

    def _save_to_cache(self):
        """将当前加载的元素原始数据保存到本地缓存。"""
        from boox_automation.core.feishu import save_cache
        sheet_data = {}
        for key, source in self._key_source.items():
            if source.startswith("feishu::"):
                sheet_name = source.split("::", 1)[1]
                sheet_data.setdefault(sheet_name, {})[key] = self._elements[key]
        if sheet_data:
            save_cache({"sheets": sheet_data, "key_source": self._key_source}, "elements")

    def _load_from_cache(self) -> bool:
        """从缓存加载元素数据，成功返回 True。"""
        from boox_automation.core.feishu import load_cache
        cached = load_cache("elements")
        if not cached:
            return False
        sheet_data = cached.get("sheets", {})
        key_source = cached.get("key_source", {})
        if not sheet_data:
            return False
        for sheet_name, elements in sheet_data.items():
            for key, info in elements.items():
                self._elements[key] = info
        self._key_source.update(key_source)
        logger.debug(f"已从缓存加载 {len(self._elements)} 个元素定义")
        return True

    def _load_from_local_xlsx(self):
        """本地 Excel 兜底加载。"""
        base = Path(__file__).parent.parent  # engine/ → boox_automation/
        xlsx = base / "data" / "elements.xlsx"
        if xlsx.exists():
            self._load_excel(str(xlsx))
        else:
            logger.debug("elements.xlsx 不存在，跳过自动加载")

    def _load_from_cloud(self):
        """从飞书电子表格加载元素定义。"""
        from boox_automation.core.feishu import list_sheet_names, read_sheet_by_name
        from boox_automation.core.config import feishu_elements_token, test_case_sheets

        token = feishu_elements_token()
        modules = {"通用"} | set(test_case_sheets())
        all_sheets = list_sheet_names(token)

        def _sheet_matches_module(sheet_name: str) -> bool:
            """sheet 名匹配任一配置模块（精确匹配或「通用」）。"""
            if sheet_name == "使用说明":
                return False
            if _EXPECTED_SHEET_MODULE_RE.match(sheet_name):
                return False
            if sheet_name.startswith("预期结果"):
                return False  # 含半角括号的预期结果格式（如 预期结果（Reader））
            if sheet_name == "通用" or sheet_name in modules:
                return True
            return False

        element_sheets = [s for s in all_sheets if _sheet_matches_module(s)]

        if not element_sheets:
            logger.warning(
                f"飞书表格中无模块 {sorted(modules)} 匹配的 sheet，已加载 {len(self._elements)} 个元素"
            )
            return

        total = 0
        for sheet_name in element_sheets:
            rows = read_sheet_by_name(sheet_name, token)
            if len(rows) < 2:
                continue
            h_idx = _find_header_row(rows)
            headers = [str(c).strip() for c in rows[h_idx]]
            for row in rows[h_idx + 1:]:
                if not row or not row[0]:
                    continue
                a_val = str(row[0]).strip()
                b_val = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                # 旧格式: A列含'.' = 完整key; 新格式: A列=模块名, key=模块.匹配文本
                key = a_val if "." in a_val or not b_val else f"{a_val}.{b_val}"
                info = self._parse_row(row, headers, key=key)
                self._elements[key] = info
                self._key_source[key] = f"feishu::{sheet_name}"
                total += 1

        logger.debug(f"已从飞书加载 {total} 个元素定义 ({len(element_sheets)} 个工作表)")

    # ---- 预期结果 sheet 加载 ----

    def _load_expected_results(self):
        """加载「预期结果」sheet（三级回退：云端 → 缓存 → 本地）。

        云端为权威数据源：云端可达且查询成功但无预期结果时，不回退缓存，
        直接中断测试（因为云端明确表示表不存在，缓存数据已过期）。
        """
        from boox_automation.core.feishu import use_local_excel

        if use_local_excel():
            logger.debug("预期结果加载路径: 本地 Excel（USE_LOCAL_EXCEL=1）")
            self._load_expected_from_local()
        else:
            cloud_checked = False  # 云端是否成功查询（无论有无数据）
            try:
                from boox_automation.core.feishu import check_feishu_reachable
                if check_feishu_reachable():
                    logger.debug("预期结果加载路径: 飞书云端")
                    try:
                        self._load_expected_from_cloud()
                        cloud_checked = True  # 云端查询成功
                        if self._expected_results:
                            self._save_expected_to_cache()
                            logger.info("预期结果来源: 飞书云端（已更新本地缓存）")
                            return
                    except Exception:
                        logger.warning(
                            "飞书云端加载预期结果失败，回退缓存",
                            exc_info=True,
                        )
            except Exception:
                pass

            # 云端明确表示无预期结果 → 不回退缓存，直接中断
            if cloud_checked:
                self._ensure_expected_loaded()

            # 云端不可达 → 缓存兜底
            logger.debug("预期结果加载路径: 本地缓存")
            if self._load_expected_from_cache():
                logger.warning("预期结果来源: 本地缓存")
                return

            # 缓存也无 → 本地兜底
            logger.debug("预期结果加载路径: 本地 Excel（兜底）")
            self._load_expected_from_local()

        self._ensure_expected_loaded()

    def _ensure_expected_loaded(self):
        """确保至少加载到一个预期结果条目，否则中断测试。"""
        if self._expected_results:
            return
        modules = self._expected_modules or ["(未知)"]
        searched = '、'.join(f"预期结果【{m}】" for m in modules)

        if self._expected_sheets_found:
            found_str = '、'.join(self._expected_sheets_found)
            raise RuntimeError(
                f"预期结果工作表已找到（{found_str}），但所有条目均校验失败，测试中断。\n"
                f"请检查 E 列（操作）是否已填写，有效值: {sorted(_VALID_EXPECTED_ACTIONS)}\n"
                f"表头: 模块 | 匹配文本 | 定位元素 | xml页面 | 操作 | 用途说明"
            )
        raise RuntimeError(
            f"未加载到任何预期结果工作表，测试中断。\n"
            f"已搜索: {searched}\n"
            f"请确认飞书元素表（或本地 elements.xlsx）中已创建对应的预期结果工作表。\n"
            f"格式: 工作表名 = 预期结果【模块名】（如 预期结果【阅读】），"
            f"表头: 模块 | 匹配文本 | 定位元素 | xml页面 | 操作 | 用途说明"
        )

    def _load_expected_from_cloud(self):
        """从飞书加载预期结果 sheet（多模块格式：预期结果【模块名】）。"""
        from boox_automation.core.feishu import list_sheet_names, read_sheet_by_name
        from boox_automation.core.config import feishu_elements_token, test_case_sheets

        token = feishu_elements_token()
        modules = test_case_sheets()
        self._expected_modules = modules
        self._expected_sheets_found = []
        self._expected_sheets_missing = []

        all_sheets = list_sheet_names(token)
        logger.debug(
            f"飞书元素表共有 {len(all_sheets)} 个工作表: "
            f"{', '.join(all_sheets)}"
        )
        logger.debug(
            f"预期结果搜索模块列表: {', '.join(modules)}"
        )

        total_before = len(self._expected_results)

        for module in modules:
            sheet_name = f"预期结果【{module}】"
            if sheet_name not in all_sheets:
                self._expected_sheets_missing.append(sheet_name)
                logger.warning(
                    f"预期结果工作表「{sheet_name}」不存在，"
                    f"请确认飞书元素表中已创建该工作表。"
                    f"当前可选工作表: {', '.join(all_sheets)}"
                )
                continue
            rows = read_sheet_by_name(sheet_name, token)
            if not rows or len(rows) < 2:
                logger.warning(
                    f"预期结果工作表「{sheet_name}」无数据，"
                    f"请确认该工作表中已填入预期结果定义（至少需要表头行 + 1 行数据）"
                )
                continue
            self._parse_expected_rows(rows)
            self._expected_sheets_found.append(sheet_name)
            logger.debug(
                f"已解析预期结果工作表「{sheet_name}」: "
                f"{len(rows) - 1} 行数据"
            )

        loaded = len(self._expected_results) - total_before
        if loaded:
            found_str = '、'.join(self._expected_sheets_found)
            missing_str = '、'.join(self._expected_sheets_missing) if self._expected_sheets_missing else '无'
            logger.debug(
                f"飞书预期结果加载完成: 共 {loaded} 个定义"
                f"（找到工作表: {found_str}"
                f"；缺失工作表: {missing_str}）"
            )
        elif self._expected_sheets_found:
            found_str = '、'.join(self._expected_sheets_found)
            logger.warning(
                f"预期结果工作表已找到（{found_str}），但所有条目均校验失败。"
                f"请检查 E 列（操作）是否已填写，有效值: {_VALID_EXPECTED_ACTIONS}"
            )
        else:
            missing_str = '、'.join(self._expected_sheets_missing)
            logger.warning(
                f"飞书中未找到任何预期结果工作表。"
                f"已搜索: {', '.join(f'预期结果【{m}】' for m in modules)}，"
                f"均不存在。"
                f"可选工作表: {', '.join(all_sheets)}"
            )

    def _save_expected_to_cache(self):
        """将预期结果数据保存到本地缓存。"""
        from boox_automation.core.feishu import save_cache
        if self._expected_results:
            save_cache({
                "expected_results": self._expected_results,
                "expected_match_index": self._expected_match_index,
            }, "expected_results")

    def _load_expected_from_cache(self) -> bool:
        """从缓存加载预期结果，成功返回 True。"""
        from boox_automation.core.feishu import load_cache
        cached = load_cache("expected_results")
        if not cached:
            return False
        er_data = cached.get("expected_results", {})
        match_idx = cached.get("expected_match_index", {})
        if not er_data:
            return False
        self._expected_results.update(er_data)
        self._expected_match_index.update(match_idx)
        self._expected_sheets_found = ["(缓存)"]
        self._expected_sheets_missing = []
        logger.debug(
            f"已从缓存加载 {len(er_data)} 个预期结果定义，"
            f"匹配索引 {len(match_idx)} 条: "
            f"{', '.join(sorted(match_idx.keys()))}"
        )
        return True

    def _load_expected_from_local(self):
        """从本地 Excel 加载预期结果 sheet（多模块格式：预期结果【模块名】）。"""
        from boox_automation.core.config import test_case_sheets

        base = Path(__file__).parent.parent  # engine/ → boox_automation/
        xlsx = base / "data" / "elements.xlsx"
        if not xlsx.exists():
            logger.debug("本地 elements.xlsx 不存在，跳过预期结果加载")
            return

        import openpyxl
        wb = openpyxl.load_workbook(xlsx)
        modules = test_case_sheets()
        self._expected_modules = modules
        self._expected_sheets_found = []
        self._expected_sheets_missing = []

        logger.debug(
            f"本地元素表共有 {len(wb.sheetnames)} 个工作表: "
            f"{', '.join(wb.sheetnames)}"
        )
        logger.debug(
            f"预期结果搜索模块列表: {', '.join(modules)}"
        )

        total_before = len(self._expected_results)

        for module in modules:
            sheet_name = f"预期结果【{module}】"
            if sheet_name not in wb.sheetnames:
                self._expected_sheets_missing.append(sheet_name)
                logger.warning(
                    f"预期结果工作表「{sheet_name}」不存在，"
                    f"请确认本地 elements.xlsx 中已创建该工作表。"
                    f"当前可选工作表: {', '.join(wb.sheetnames)}"
                )
                continue
            ws = wb[sheet_name]
            rows = []
            for row in ws.iter_rows(min_row=1, values_only=True):
                rows.append([str(v) if v is not None else "" for v in row])
            self._parse_expected_rows(rows)
            self._expected_sheets_found.append(sheet_name)
            logger.debug(
                f"已解析预期结果工作表「{sheet_name}」: "
                f"{len(rows)} 行"
            )

        wb.close()
        loaded = len(self._expected_results) - total_before
        if loaded:
            found_str = '、'.join(self._expected_sheets_found)
            logger.info(
                f"已从本地 Excel 加载 {loaded} 个预期结果定义 "
                f"（工作表: {found_str}）"
            )
        elif self._expected_sheets_found:
            found_str = '、'.join(self._expected_sheets_found)
            logger.warning(
                f"本地预期结果工作表已找到（{found_str}），但所有条目均校验失败。"
                f"请检查 E 列（操作）是否已填写，有效值: {sorted(_VALID_EXPECTED_ACTIONS)}"
            )
        else:
            missing_str = '、'.join(self._expected_sheets_missing)
            logger.warning(
                f"本地 Excel 中未找到任何预期结果工作表。"
                f"已搜索: {', '.join(f'预期结果【{m}】' for m in modules)}"
            )

    def _parse_expected_rows(self, rows: list[list[str]]):
        """解析预期结果 sheet 行数据（6 列）。

        列结构: 模块 | 匹配文本 | 定位元素 | xml页面 | 操作 | 用途说明
        key = 模块 + "." + 匹配文本
        """
        if len(rows) < 2:
            return

        h_idx = _find_header_row(rows)
        headers = [str(c).strip() for c in rows[h_idx]]
        _EXPECTED_HEADER_MAP = {
            "元素标识": "key",
            "模块": "key",
            "匹配文本": "match",
            "页面XML": "content",
            "xml页面": "content",
            "检查元素": "element_checks",
            "定位元素": "element_checks",
            "操作": "action",
            "用途说明": "description",
        }

        for row_idx_0, row in enumerate(rows[h_idx + 1:]):
            if not row or not row[0]:
                continue

            key = ""
            key_part = ""
            info: dict = {}
            for i, h in enumerate(headers):
                val = str(row[i]).strip() if i < len(row) and row[i] else ""
                if not val:
                    continue
                field = _EXPECTED_HEADER_MAP.get(h, h)

                if field == "key":
                    key_part = val
                elif field == "match":
                    info["match"] = val
                elif field == "content":
                    info["content"] = val
                elif field == "element_checks":
                    info["element_checks"] = val
                elif field == "action":
                    info["action"] = val
                elif field == "description":
                    info["description"] = val

            # key 拼接: 旧格式 A列含'.' = 完整key; 新格式 key=模块.匹配文本
            match = info.get("match", "")
            if key_part and "." not in key_part and match:
                key = f"{key_part}.{match}"
            else:
                key = key_part

            if not key:
                logger.warning(f"预期结果第{row_idx_0 + h_idx + 2}行缺少 key（模块+匹配文本 或 元素标识），跳过")
                continue

            # E 列（操作）校验：不允许为空或无效
            action = info.get("action", "")
            if not action:
                logger.warning(f"预期结果【{key}】E列（操作）为空，跳过")
                continue
            if action not in _VALID_EXPECTED_ACTIONS:
                logger.warning(
                    f"预期结果【{key}】E列（操作）无效值'{action}'，"
                    f"有效值: {_VALID_EXPECTED_ACTIONS}，跳过")
                continue

            # toast 模式：不需要 C/D 列，match 用于 toast 文本
            if action in ("断言toast", "断言toast不出现"):
                if not match:
                    logger.warning(f"预期结果【{key}】E列为'{action}'但B列（匹配文本）为空，跳过")
                    continue
            else:
                # visible / not_visible 模式：C/D 列至少有一个
                if not info.get("content") and not info.get("element_checks"):
                    logger.warning(f"预期结果【{key}】页面XML和检查元素均为空，跳过")
                    continue

            self._expected_results[key] = info

            # 建立匹配文本 → key 索引
            match_text = info.get("match", "")
            if match_text:
                self._expected_match_index[match_text] = key

    def get_expected_page(self, key: str) -> dict | None:
        """按 key 获取预期结果页面信息。"""
        return self._expected_results.get(key)

    def match_expected_result(self, tag: str) -> str:
        """按匹配文本查找预期结果 key，未匹配返回空字符串。"""
        result = self._expected_match_index.get(tag, "")
        if not result:
            logger.debug(
                f"预期结果匹配失败: 匹配文本「{tag}」未在索引中找到。"
                f"当前索引共 {len(self._expected_match_index)} 条: "
                f"{', '.join(sorted(self._expected_match_index.keys())) if self._expected_match_index else '(空)'}"
            )
        return result

    def get_expected_diagnostics(self) -> dict:
        """获取预期结果加载的诊断信息，用于错误报告。"""
        return {
            "modules": self._expected_modules,
            "sheets_found": self._expected_sheets_found,
            "sheets_missing": self._expected_sheets_missing,
            "match_index": dict(self._expected_match_index),
            "total_results": len(self._expected_results),
        }

    # 中文表头 → 英文内部 key 映射（兼容新旧两种表头）
    _HEADER_MAP = {
        "元素标识": "key",
        "模块": "key",          # 新格式：模块列 = key 前缀，需与匹配文本拼接
        "匹配文本": "match",
        "定位方式": "locator",
        "定位元素": "locator",  # 新格式：定位元素 = locator
        "操作类型": "action",
        "操作": "action",       # 新格式：操作 = action
        "用途说明": "operation",
        "序号": "index",
    }

    def _normalize_header(self, h: str) -> str:
        """将表头标准化为内部英文 key，中文表头自动映射。"""
        h = h.strip()
        return self._HEADER_MAP.get(h, h)

    def _parse_row(self, row: list[str], headers: list[str], key: str = "") -> dict:
        """将一行数据按表头解析为元素信息字典。

        表头支持中文和英文，中文表头自动映射为内部 key：
          元素标识→key  匹配文本→match  定位方式→locator  操作类型→action
          用途说明→operation  序号→index

        locator 列支持多设备「键：」分块格式，解析后存入 _locator_blocks。
        """
        info = {}
        for i, h in enumerate(headers):
            val = row[i] if i < len(row) else None
            if val is None or str(val).strip() == "":
                continue
            val_str = str(val).strip()
            field = self._normalize_header(h)

            if field in ("key",):
                continue
            elif field == "action":
                info["action"] = _ACTION_CN_TO_EN.get(val_str, val_str)
            elif field == "locator":
                blocks = _parse_device_blocks(val_str)
                if len(blocks) > 1:
                    info["locator"] = ["xpath", blocks.get("__default__", "")]
                    info["_locator_blocks"] = blocks
                else:
                    info["locator"] = ["xpath", val_str]
            elif field == "index":
                info["index"] = int(val_str)
            else:
                info[field] = val_str
        return info

    def _load_excel(self, xlsx_path: str):
        """从 Excel 加载元素定义。自动检测表头行。"""
        import openpyxl

        wb = openpyxl.load_workbook(xlsx_path)
        count = 0

        for sheet_name in wb.sheetnames:
            if sheet_name == "使用说明":
                continue
            if _EXPECTED_SHEET_MODULE_RE.match(sheet_name):
                continue  # 预期结果 sheet 不加载为元素
            ws = wb[sheet_name]
            # 读取所有行（1-indexed → 0-indexed 列表）
            all_rows = []
            for row in ws.iter_rows(min_row=1, values_only=True):
                all_rows.append([str(v) if v is not None else "" for v in row])

            if len(all_rows) < 2:
                continue
            h_idx = _find_header_row(all_rows)
            headers = [h.strip() for h in all_rows[h_idx]]

            for row_vals in all_rows[h_idx + 1:]:
                if not row_vals or not row_vals[0]:
                    continue

                a_val = row_vals[0].strip()
                b_val = row_vals[1].strip() if len(row_vals) > 1 else ""
                key = a_val if "." in a_val or not b_val else f"{a_val}.{b_val}"
                info = self._parse_row(row_vals, headers, key=key)
                self._elements[key] = info
                self._key_source[key] = f"{xlsx_path}::{sheet_name}"
                count += 1

        logger.info(f"已从 {xlsx_path} 加载 {count} 个元素定义 ({len(wb.sheetnames)} 个工作表)")

    def get_element_info(self, element_key: str) -> dict:
        """
        返回元素信息字典，locator 字段已转为 (By, value) 元组。

        自动解析 locator 列内联多设备块。

        Raises:
            KeyError: element_key 不存在
        """
        if element_key not in self._elements:
            available = ', '.join(sorted(self._elements.keys())[:20])
            raise KeyError(
                f"元素 '{element_key}' 未在元素定义中找到。"
                f"已加载的 key（前20个）: {available or '(无)'}"
            )

        raw = dict(self._elements[element_key])

        # 解析 locator 列内联多设备块
        if '_locator_blocks' in raw:
            device_info = self._get_device_info()
            if device_info:
                blocks = raw.pop('_locator_blocks')
                best_key = _resolve_best_device_key(set(blocks.keys()), device_info)
                if best_key in blocks:
                    raw['locator'] = ["xpath", blocks[best_key]]
                    logger.debug(
                        f"元素【{element_key}】定位器多设备匹配: {best_key}"
                    )

        if 'locator' in raw:
            raw['locator'] = self._convert_locator(raw['locator'])

        return raw

    _device_info_cache: dict | None = None
    _device_info_loaded: bool = False

    @classmethod
    def _get_device_info(cls) -> dict:
        """获取当前设备信息（缓存，避免重复调用 ADB）。"""
        if cls._device_info_loaded:
            return cls._device_info_cache or {}
        cls._device_info_loaded = True
        try:
            from boox_automation.devices.info import Device_basic_information
            devices = Device_basic_information()
            cls._device_info_cache = devices.get_device_info() or {}
        except Exception:
            cls._device_info_cache = {}
        return cls._device_info_cache

    @staticmethod
    def _convert_locator(locator):
        """将 YAML 中的 [type_str, value] 转为 (By.CONST, value) 元组。"""
        if isinstance(locator, (list, tuple)) and len(locator) == 2:
            loc_type, loc_value = locator
            if isinstance(loc_type, str):
                mapped = LOCATOR_TYPE_MAP.get(loc_type.lower())
                if mapped is None:
                    raise ValueError(
                        f"不支持的定位类型 '{loc_type}'，"
                        f"支持: {list(LOCATOR_TYPE_MAP.keys())}"
                    )
                loc_type = mapped
            return (loc_type, loc_value)
        return locator

    def get_element_info_safe(self, element_key: str) -> dict | None:
        """返回元素信息字典（不抛异常），未找到返回 None。"""
        return self._elements.get(element_key)

    def get_key_source(self, element_key: str) -> str | None:
        """返回元素键所在的 YAML 文件路径，未找到返回 None。"""
        return self._key_source.get(element_key)

    def __contains__(self, element_key: str) -> bool:
        return element_key in self._elements

    def __len__(self) -> int:
        return len(self._elements)


# ==== ElementMatcher（基于 ElementLoader 构建索引）====


"""元素匹配器：根据【】标记文本查找对应的 element_key。

从 ElementLoader 获取元素数据，构建 text → element_key 反向索引。
"""

class ElementMatcher:
    """构建 text → element_key 反向索引，支持精确和模糊匹配。"""

    def __init__(self):
        self._index: dict[str, list[str]] = {}
        self._build_index()

    def _build_index(self) -> None:
        """从 ElementLoader 获取所有元素，构建 text → key 反向索引。"""
        from boox_automation.engine.elements import get_element_loader

        loader = get_element_loader()
        for key, info in loader._elements.items():
            if not info.get("locator"):
                continue  # 无 locator 的元素（如预期结果）不参与步骤操作匹配

            match = info.get("match", "")
            if match:
                self._index.setdefault(str(match), []).append(key)

            locator = info.get("locator", [])
            if len(locator) >= 2 and locator[1]:
                text = str(locator[1])
                if text != match:
                    self._index.setdefault(text, []).append(key)

            # key 末段兜底: 桌面进入.书库首页 → 索引"书库首页"
            if not match:
                parts = key.rsplit(".", 1)
                if len(parts) == 2 and parts[1]:
                    self._index.setdefault(parts[1], []).append(key)

        logger.debug(f"元素索引构建完成: {len(loader._elements)} 个元素, {len(self._index)} 个索引词")

    # ---- 匹配逻辑 ----

    def match(self, tag: str, page_context: str = "", case_context: str = "",
             warn: bool = True) -> str:
        """根据【】标记文本查找 element_key。

        warn=True:  未匹配时 WARNING（运行时用）
        warn=False: 未匹配时 DEBUG（收集阶段用，不显示在 INFO 级别）
        warn=None:  未匹配时静默（批量收集用）

        匹配优先级（方案 B）：
        1. page_context.tag 精确查找（模块.匹配文本）
        2. 通用.tag 回退查找
        3. 反向索引精确匹配
        4. 多候选时按页面上下文评分
        5. locator 纯文本精确匹配（兜底）
        6. 都无则返回空
        """
        if not tag:
            return ""

        ctx = f" [{case_context}]" if case_context else ""
        elements = self._get_elements()

        # 1. 方案 B 快速路径：模块.匹配文本 直接查找
        if page_context:
            direct_key = f"{page_context}.{tag}"
            if direct_key in elements:
                return direct_key

        # 2. 通用模块回退
        if page_context != "通用":
            fallback_key = f"通用.{tag}"
            if fallback_key in elements:
                return fallback_key

        # 3. 反向索引精确匹配
        exact = self._index.get(tag, [])
        if len(exact) == 1:
            return exact[0]

        # 4. 多候选 → 按页面上下文评分
        if len(exact) > 1:
            best = self._pick_best(tag, exact, page_context, ctx, warn)
            if best:
                return best

        # 5. locator 纯文本精确匹配（仅当 locator 非 XPath 时生效）
        partial = [k for k, v in elements.items()
                   if tag == str(v.get("locator", ["", ""])[1])]
        if len(partial) == 1:
            return partial[0]
        if len(partial) > 1:
            best = self._pick_best(tag, partial, page_context, ctx, warn)
            if best:
                return best

        if warn is True:
            logger.warning(f"【{tag}】{ctx} 未匹配到任何元素")
        elif warn is False:
            logger.debug(f"【{tag}】{ctx} 未匹配到任何元素")
        # warn is None: 静默
        return ""

    def _pick_best(self, tag: str, candidates: list[str],
                   page_context: str, ctx: str, warn: bool = True) -> str:
        silent = warn is None
        if not page_context:
            if warn is True:
                logger.warning(
                    f"【{tag}】{ctx} 匹配到 {len(candidates)} 个，无页面上下文，使用: {candidates[0]}"
                )
            return candidates[0]

        scored = []
        for key in candidates:
            score = 0
            if key.startswith(page_context):
                score += 10
            elif page_context in key:
                score += 5
            key_page = key.split(".")[0] if "." in key else ""
            if key_page and key_page in page_context:
                score += 3
            scored.append((score, key))

        scored.sort(key=lambda x: -x[0])
        best_score, best_key = scored[0]

        if best_score > 0 and len(candidates) > 1 and not silent:
            alt = ", ".join(k for _, k in scored[1:3])
            logger.debug(
                f"【{tag}】{ctx} {len(candidates)}个候选, "
                f"页面'{page_context}' → 选 {best_key} (alt: {alt})"
            )
        elif len(candidates) > 1 and warn is True:
            logger.warning(
                f"【{tag}】{ctx} 匹配到 {len(candidates)} 个，"
                f"页面'{page_context}'无匹配，使用: {best_key}"
            )

        return best_key

    # ---- 元素信息查询 ----

    def _get_elements(self) -> dict:
        from boox_automation.engine.elements import get_element_loader
        return get_element_loader()._elements

    def get_element(self, element_key: str) -> dict | None:
        return self._get_elements().get(element_key)

    def suggest_action(self, element_key: str) -> str:
        """返回元素表 D 列定义的操作类型，未定义或无效时默认 click。"""
        info = self._get_elements().get(element_key)
        if not info:
            return ""
        if not info.get("locator"):
            return ""

        explicit = info.get("action", "")
        valid_actions = ("click", "assert_toast", "input", "long_press",
                         "click_coord", "long_press_coord", "swipe_coord")
        if explicit in valid_actions:
            return explicit

        return "click"

    @property
    def element_count(self) -> int:
        return len(self._get_elements())
