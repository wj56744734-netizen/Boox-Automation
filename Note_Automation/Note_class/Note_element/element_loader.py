"""
元素加载器：从 elements.xlsx 读取元素定位配置，将字符串类型转为 selenium By 常量。

约定：
  - 每个 Sheet 对应一个页面，Sheet 名 = 页面名
  - 每个元素包含 'locator' 字段，格式为 [type_string, value_string]
  - type_string 支持: id, xpath, class_name, accessibility_id
  - 可选字段: match, action, operation, index, dismiss_with, overrides, checks
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


def _parse_checks_text(text: str) -> list[dict]:
    """解析 checks 列文本为多元素检查列表。

    格式A（推荐 — | 独占一行为分隔符）:
      //xpath1
      期望文本1
      |
      //xpath2
      期望文本2

    格式B（兼容 — 单行' | '分隔）:
      //xpath1 | 期望文本1
      //xpath2 | 期望文本2

    仅 XPath 无文本 → 只检查可见性。
    返回: [{"locator": ["xpath", "//..."], "text": "期望文本"}, ...]
    """
    text = str(text).strip()
    if not text:
        return []

    lines = text.split("\n")

    # 格式A: 存在独占一行的 "|"
    if any(l.strip() == "|" for l in lines):
        return _parse_checks_block_format(lines)

    # 格式B: 单行 " | " 格式
    return _parse_checks_inline_format(lines)


def _parse_checks_block_format(lines: list[str]) -> list[dict]:
    """格式A: xpath\ntext\n|\nxpath\ntext"""
    result = []
    block = []
    for line in lines:
        stripped = line.strip()
        if stripped == "|":
            if block:
                result.append(_checks_block_to_item(block))
                block = []
        else:
            block.append(stripped)
    if block:
        result.append(_checks_block_to_item(block))
    return result


def _checks_block_to_item(block: list[str]) -> dict:
    """将多行块转为元素检查项。行1=xpath, 行2=期望文本(可选)。"""
    xpath = block[0] if block else ""
    text = block[1] if len(block) > 1 else ""
    return {"locator": ["xpath", xpath], "text": text}


def _parse_checks_inline_format(lines: list[str]) -> list[dict]:
    """格式B: xpath | text 每行一条"""
    result = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if " | " in line:
            xpath, expected = line.split(" | ", 1)
            result.append({"locator": ["xpath", xpath.strip()], "text": expected.strip()})
        else:
            result.append({"locator": ["xpath", line], "text": ""})
    return result


def _parse_overrides_text(text: str) -> dict:
    """解析 overrides 单元格文本为 dict。

    格式: 每行一条，': ' 分隔键和值。
      阅读器: (//...function_icon])[3]
      海外: skip
      !4.2: skip
    """
    import ast
    result = {}
    for line in str(text).split("\n"):
        line = line.strip()
        if not line or ": " not in line:
            continue
        key, val = line.split(": ", 1)
        key = key.strip()
        val = val.strip()
        if val == "skip":
            result[key] = {"skip": True}
        elif val.startswith("{") and val.endswith("}"):
            try:
                parsed = ast.literal_eval(val)
                if isinstance(parsed, dict) and parsed.get("skip") is False:
                    continue
                result[key] = parsed
            except (ValueError, SyntaxError):
                result[key] = val
        else:
            # xpath 文本或其他值 → 作为 locator 覆盖值
            result[key] = {"locator": ["xpath", val]}
    return result


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
        self._auto_discover()

    def _auto_discover(self):
        """自动加载元素定义（仅 Excel）。"""
        base = Path(__file__).parent
        xlsx = base.parent.parent / "excel_framework" / "elements.xlsx"

        if xlsx.exists():
            self._load_excel(str(xlsx))
        else:
            logger.debug("elements.xlsx 不存在，跳过自动加载")

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
                if not row[0]:
                    continue

                key = str(row[0]).strip()
                info = {}
                for i, h in enumerate(headers):
                    val = row[i] if i < len(row) else None
                    if val is None or str(val).strip() == "":
                        continue
                    val_str = str(val).strip()

                    if h in ("key",):
                        continue
                    elif h == "locator":
                        info["locator"] = ["xpath", val_str]
                    elif h == "index":
                        info["index"] = int(val_str)
                    elif h == "overrides":
                        info[h] = _parse_overrides_text(val_str)
                    elif h == "checks":
                        info["checks"] = _parse_checks_text(val_str)
                    else:
                        info[h] = val_str

                self._elements[key] = info
                self._key_source[key] = f"{xlsx_path}::{sheet_name}"
                count += 1

        logger.info(f"已从 {xlsx_path} 加载 {count} 个元素定义 ({len(wb.sheetnames)} 个 Sheet)")

    def get_element_info(self, element_key: str) -> dict:
        """
        返回元素信息字典，locator 字段已转为 (By, value) 元组。

        自动解析 overrides：根据设备类型/尺寸/区域匹配覆盖规则。

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

        # 解析设备相关的 overrides
        override = self._resolve_override(raw.get("overrides", {}))
        if override:
            raw.update(override)

        if 'locator' in raw:
            raw['locator'] = self._convert_locator(raw['locator'])

        if 'checks' in raw:
            raw['checks'] = [
                {
                    "locator": self._convert_locator(c["locator"]),
                    "text": c.get("text", ""),
                }
                for c in raw['checks']
            ]

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
            from Note_Automation.Devices_list.Device_basic_information import Device_basic_information
            devices = Device_basic_information()
            cls._device_info_cache = devices.get_device_info() or {}
        except Exception:
            cls._device_info_cache = {}
        return cls._device_info_cache

    def _resolve_override(self, overrides: dict) -> dict | None:
        """根据设备信息匹配 best override，返回覆盖字段或 None。

        override 键支持: 阅读器, 平板, 6, 10.3, 国内, 海外, 全球
        组合键: 阅读器, 国内   /   4.2, 6.13  ...
        特殊值: {skip: true} 表示该设备不适用此元素
        """
        if not overrides:
            return None

        info = self._get_device_info()
        if not info:
            return None

        device_type = info.get("devices_reader", "")
        device_size = info.get("device_size", "")
        device_region = info.get("device_region", "")
        version = info.get("version_info", "").split("-")[0]

        best = None
        best_score = -1

        for key, value in overrides.items():
            # 取反: 键前加 ! 表示「不匹配时生效」
            negate = str(key).startswith("!")
            clean_key = str(key).lstrip("!")
            parts = [p.strip() for p in clean_key.split(",")]

            score = 0
            for p in parts:
                if p in (device_type, device_size, device_region, version):
                    score += 1
            all_match = score == len(parts)
            if negate:
                all_match = not all_match

            if all_match and score > best_score:
                best_score = score
                best = value

        return dict(best) if best else None

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

    def get_key_source(self, element_key: str) -> str | None:
        """返回元素键所在的 YAML 文件路径，未找到返回 None。"""
        return self._key_source.get(element_key)

    def __contains__(self, element_key: str) -> bool:
        return element_key in self._elements

    def __len__(self) -> int:
        return len(self._elements)
