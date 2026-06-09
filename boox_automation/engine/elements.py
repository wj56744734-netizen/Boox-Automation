"""
元素加载器：从 elements.xlsx 读取元素定位配置，将字符串类型转为 selenium By 常量。

约定：
  - 每个 Sheet 对应一个页面，Sheet 名 = 页面名
  - 每个元素包含 'locator' 字段，格式为 [type_string, value_string]
  - type_string 支持: id, xpath, class_name, accessibility_id
  - 可选字段: match, action, operation, index
  - locator 列支持多设备「键：」分块格式
"""
from __future__ import annotations

import logging
from pathlib import Path

from selenium.webdriver.common.by import By
from appium.webdriver.common.appiumby import AppiumBy

LOCATOR_TYPE_MAP = {
    'id': By.ID,
    'xpath': By.XPATH,
    'class_name': By.CLASS_NAME,
    'accessibility_id': AppiumBy.ACCESSIBILITY_ID,
    'name': By.NAME,
    'tag_name': By.TAG_NAME,
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

# 设备级 action（不需要元素匹配，纯关键词驱动）
_DEVICE_ACTIONS = {
    "swipe_up", "swipe_down", "swipe_left", "swipe_right",
    "press_back",
}


# ---- 多设备块解析（元素 C 列 + 预期结果 C 列通用） ----

# 有效的设备键
_VALID_DEVICE_KEYS = {
    "国内", "海外", "全球",
    "阅读器", "平板",
    "6", "7.8", "10.3", "13.3",
    "黑白", "彩色",
}


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
    version = device_info.get("version_info", "").split("-")[0]

    for p in parts:
        if p in (device_type, device_size, device_region, version):
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
    from selenium.common.exceptions import NoSuchElementException
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
    for xpath, expected_text in items:
        try:
            el = driver.find_element(By.XPATH, xpath)
            if expected_text:
                actual = (el.text or "").strip()
                expected_text = expected_text.replace("\\n", "\n")
                if actual != expected_text:
                    text_mismatch.append((xpath, expected_text, actual))
                    continue  # 文本不匹配，不加入 found
            found.append(xpath)
        except NoSuchElementException:
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
        logger.info("\n".join(lines))
        if found:
            raise AssertionError(lines[0])
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
        logger.info("\n".join(lines))
        if has_failure:
            raise AssertionError(lines[0])


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
        self._auto_discover()

    def _auto_discover(self):
        """自动加载元素定义（云端优先 → 缓存兜底 → 本地 Excel）。"""
        from boox_automation.core.feishu import (
            use_local_excel, check_feishu_reachable,
            load_cache, save_cache, get_cache_age,
        )

        if use_local_excel():
            self._load_from_local_xlsx()
            self._load_expected_results()
            return

        # 1. 尝试云端
        if check_feishu_reachable():
            try:
                self._load_from_cloud()
                self._save_to_cache()
                logger.info(f"元素来源: 飞书云端（已更新本地缓存）")
                self._load_expected_results()
                return
            except Exception:
                logger.warning(
                    "飞书云端加载失败，回退缓存。如已修改飞书在线文档但未生效，"
                    "请删缓存后重试: rm boox_automation/data/.cache/elements.json",
                    exc_info=True,
                )

        # 2. 云端不可用 → 缓存兜底
        if self._load_from_cache():
            age = get_cache_age("elements")
            logger.warning(
                f"元素来源: 本地缓存（{age}）。"
                f"如飞书在线文档已有更新，请删缓存后重试: "
                f"rm boox_automation/data/.cache/elements.json"
            )
            self._load_expected_results()
            return

        # 3. 兜底本地 Excel
        logger.warning("无可用缓存，回退本地 Excel")
        self._load_from_local_xlsx()
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
        from boox_automation.core.config import (
            feishu_elements_token, feishu_element_sheet_prefix)

        token = feishu_elements_token()
        prefix = feishu_element_sheet_prefix()
        all_sheets = list_sheet_names(token)

        # 过滤：支持前缀匹配；前缀为空时加载全部（排除 使用说明）
        if prefix:
            element_sheets = [s for s in all_sheets if s.startswith(prefix)]
        else:
            element_sheets = [s for s in all_sheets if s != "使用说明"]

        if not element_sheets:
            logger.warning(
                f"飞书表格中无可用 sheet（prefix='{prefix}'），已加载 {len(self._elements)} 个元素"
            )
            return

        total = 0
        for sheet_name in element_sheets:
            rows = read_sheet_by_name(sheet_name, token)
            if len(rows) < 3:
                continue
            headers = [str(c).strip() for c in rows[1]]  # 第2行为表头
            for row in rows[2:]:
                if not row or not row[0]:
                    continue
                key = str(row[0]).strip()
                info = self._parse_row(row, headers, key=key)
                self._elements[key] = info
                self._key_source[key] = f"feishu::{sheet_name}"
                total += 1

        logger.debug(f"已从飞书加载 {total} 个元素定义 ({len(element_sheets)} 个 Sheet)")

    # ---- 预期结果 sheet 加载 ----

    # 预期结果 sheet 名
    _EXPECTED_SHEET = "预期结果"

    def _load_expected_results(self):
        """加载「预期结果」sheet（三级回退：云端 → 缓存 → 本地）。"""
        from boox_automation.core.feishu import use_local_excel

        if use_local_excel():
            self._load_expected_from_local()
            return

        try:
            from boox_automation.core.feishu import check_feishu_reachable
            if check_feishu_reachable():
                try:
                    self._load_expected_from_cloud()
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

        if self._load_expected_from_cache():
            logger.warning("预期结果来源: 本地缓存")
            return

        self._load_expected_from_local()

    def _load_expected_from_cloud(self):
        """从飞书加载预期结果 sheet。"""
        from boox_automation.core.feishu import read_sheet_by_name
        from boox_automation.core.config import feishu_elements_token

        token = feishu_elements_token()
        rows = read_sheet_by_name(self._EXPECTED_SHEET, token)
        if not rows or len(rows) < 3:
            logger.debug("飞书中无「预期结果」sheet 或数据不足，跳过")
            return

        self._parse_expected_rows(rows)
        logger.debug(f"已从飞书加载 {len(self._expected_results)} 个预期结果定义")

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
        logger.debug(f"已从缓存加载 {len(er_data)} 个预期结果定义")
        return True

    def _load_expected_from_local(self):
        """从本地 Excel 加载预期结果 sheet。"""
        base = Path(__file__).parent.parent  # engine/ → boox_automation/
        xlsx = base / "data" / "elements.xlsx"
        if not xlsx.exists():
            logger.debug("elements.xlsx 不存在，跳过预期结果加载")
            return

        import openpyxl
        wb = openpyxl.load_workbook(xlsx)
        if self._EXPECTED_SHEET not in wb.sheetnames:
            logger.debug("本地 Excel 中无「预期结果」sheet，跳过")
            wb.close()
            return

        ws = wb[self._EXPECTED_SHEET]
        rows = []
        for row in ws.iter_rows(min_row=1, values_only=True):
            rows.append([str(v) if v is not None else "" for v in row])
        wb.close()
        self._parse_expected_rows(rows)
        logger.info(f"已从本地 Excel 加载 {len(self._expected_results)} 个预期结果定义")

    def _parse_expected_rows(self, rows: list[list[str]]):
        """解析预期结果 sheet 行数据（4 列 A-D）。

        列A: 元素标识 (key)
        列B: 匹配文本 (match)
        列C: 页面XML (content) — 从 Appium Inspector 导出，支持多设备「键：」分块
        列D: 用途说明 (description)
        """
        if len(rows) < 3:
            return

        headers = [str(c).strip() for c in rows[1]]  # 第2行为表头
        _EXPECTED_HEADER_MAP = {
            "元素标识": "key",
            "匹配文本": "match",
            "页面XML": "content",
            "检查元素": "element_checks",
            "用途说明": "description",
        }

        for row_idx_0, row in enumerate(rows[2:]):
            if not row or not row[0]:
                continue

            key = ""
            info: dict = {}
            for i, h in enumerate(headers):
                val = str(row[i]).strip() if i < len(row) and row[i] else ""
                if not val:
                    continue
                field = _EXPECTED_HEADER_MAP.get(h, h)

                if field == "key":
                    key = val
                elif field == "match":
                    info["match"] = val
                elif field == "content":
                    info["content"] = val
                elif field == "element_checks":
                    info["element_checks"] = val
                elif field == "description":
                    info["description"] = val

            if not key:
                logger.warning(f"预期结果第{row_idx_0 + 3}行缺少「元素标识」，跳过")
                continue

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
        return self._expected_match_index.get(tag, "")

    # 中文表头 → 英文内部 key 映射（兼容中英文两种表头）
    _HEADER_MAP = {
        "元素标识": "key",
        "匹配文本": "match",
        "定位方式": "locator",
        "操作类型": "action",
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
        """从 Excel 加载元素定义。每个 Sheet 对应一个页面。"""
        import openpyxl

        wb = openpyxl.load_workbook(xlsx_path)
        count = 0

        for sheet_name in wb.sheetnames:
            if sheet_name == "使用说明":
                continue
            ws = wb[sheet_name]
            headers = [str(c.value or "") for c in ws[2]]  # 标题在第2行（第1行是注释）

            for row in ws.iter_rows(min_row=3, values_only=True):
                row_vals = [str(v) if v is not None else "" for v in row]
                if not row_vals or not row_vals[0]:
                    continue

                key = row_vals[0].strip()
                info = self._parse_row(row_vals, headers, key=key)
                self._elements[key] = info
                self._key_source[key] = f"{xlsx_path}::{sheet_name}"
                count += 1

        logger.info(f"已从 {xlsx_path} 加载 {count} 个元素定义 ({len(wb.sheetnames)} 个 Sheet)")

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
                        f"元素【{element_key}】locator 多设备匹配: {best_key}"
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

        logger.debug(f"元素索引构建完成: {len(loader._elements)} 个元素, {len(self._index)} 个索引词")

    # ---- 匹配逻辑 ----

    def match(self, tag: str, page_context: str = "", case_context: str = "",
             warn: bool = True) -> str:
        """根据【】标记文本查找 element_key。

        匹配优先级：
        1. 唯一精确匹配 → 直接返回
        2. 多候选时按页面上下文评分排序，取最佳
        3. 无精确匹配时尝试部分匹配
        4. 都无则返回空
        """
        if not tag:
            return ""

        ctx = f" [{case_context}]" if case_context else ""
        elements = self._get_elements()

        # 1. 精确匹配
        exact = self._index.get(tag, [])
        if len(exact) == 1:
            return exact[0]

        # 2. 多候选 → 按页面上下文评分
        if len(exact) > 1:
            best = self._pick_best(tag, exact, page_context, ctx, warn)
            if best:
                return best

        # 3. 部分匹配
        partial = [k for k, v in elements.items()
                   if tag in str(v.get("locator", ["", ""])[1])]
        if len(partial) == 1:
            return partial[0]
        if len(partial) > 1:
            best = self._pick_best(tag, partial, page_context, ctx, warn)
            if best:
                return best

        if warn:
            logger.warning(f"【{tag}】{ctx} 未匹配到任何元素")
        else:
            logger.debug(f"【{tag}】{ctx} 未匹配到任何元素")
        return ""

    def _pick_best(self, tag: str, candidates: list[str],
                   page_context: str, ctx: str, warn: bool = True) -> str:
        if not page_context:
            if warn:
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

        if best_score > 0 and len(candidates) > 1:
            alt = ", ".join(k for _, k in scored[1:3])
            logger.debug(
                f"【{tag}】{ctx} {len(candidates)}个候选, "
                f"页面'{page_context}' → 选 {best_key} (alt: {alt})"
            )
        elif len(candidates) > 1 and warn:
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
        """根据元素信息推断推荐动作类型。

        优先级: 显式 action 字段 > 关键词推断 > 默认 click
        """
        info = self._get_elements().get(element_key)
        if not info:
            return ""
        if not info.get("locator"):
            return ""  # 无可操作的定位器，不能执行 UI 操作

        explicit = info.get("action", "")
        valid_actions = ("click", "assert_toast", "input", "long_press",
                         "click_coord", "long_press_coord", "swipe_coord")
        if explicit in valid_actions:
            return explicit

        keywords = " ".join([element_key, info.get("operation", "")])
        if any(w in keywords for w in ("toast", "Toast", "提示")):
            return "assert_toast"

        return "click"

    @property
    def element_count(self) -> int:
        return len(self._get_elements())
