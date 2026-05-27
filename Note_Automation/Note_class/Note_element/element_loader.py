"""
YAML元素加载器：从 YAML 文件读取元素定位配置，将字符串类型转为 selenium By 常量。

约定：
  - YAML 顶层键为 'elements'，其值为 dict
  - 每个元素包含 'locator' 字段，格式为 [type_string, value_string]
  - type_string 支持: id, xpath, class_name, accessibility_id
  - 可选字段: name, index, child_locator, sub_index, operation, x_ratio, y_ratio
"""

import logging
from pathlib import Path

import yaml
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


class ElementLoader:
    """
    元素加载器：读取 YAML 定义，按 key 返回标准化后的元素信息字典。

    Usage:
        loader = ElementLoader()
        info = loader.get_element_info("手写笔记.退出手写笔记")
        # info == {
        #     'locator': (By.ID, 'com.onyx.android.note:id/back_icon'),
        #     'operation': '退出手写笔记',
        # }
    """

    def __init__(self, yaml_path=None):
        self._elements: dict = {}
        self._key_source: dict = {}  # element_key → yaml file path
        self._key_line: dict = {}    # element_key → line number in yaml file
        if yaml_path:
            self._load_path(yaml_path)
        else:
            self._auto_discover()

    def _auto_discover(self):
        """自动加载 Note_element/elements/ 下的所有 .yaml/.yml 文件。"""
        elements_dir = Path(__file__).parent / "elements"
        if not elements_dir.is_dir():
            logger.debug(f"YAML 元素目录不存在: {elements_dir}，跳过自动加载")
            return
        for yaml_file in sorted(elements_dir.glob("*.yaml")):
            self._load_path(str(yaml_file))
        for yaml_file in sorted(elements_dir.glob("*.yml")):
            self._load_path(str(yaml_file))

    def _load_path(self, yaml_path: str):
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if not data or 'elements' not in data:
            logger.warning(f"YAML 文件缺少 'elements' 顶层键: {yaml_path}")
            return
        count = len(data['elements'])
        self._elements.update(data['elements'])
        for key in data['elements']:
            self._key_source[key] = yaml_path
        # 记录每个 key 在 YAML 文件中的行号
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for key in data['elements']:
                for i, line in enumerate(lines, start=1):
                    stripped = line.lstrip()
                    if stripped.startswith(key) and stripped.endswith(':\n') or stripped == key + ':':
                        self._key_line[key] = i
                        break
        except Exception:
            pass
        logger.debug(f"已从 {yaml_path} 加载 {count} 个元素定义")

    def get_element_info(self, element_key: str) -> dict:
        """
        返回元素信息字典，locator 字段已转为 (By, value) 元组。

        Raises:
            KeyError: element_key 不存在
        """
        if element_key not in self._elements:
            available = ', '.join(sorted(self._elements.keys())[:20])
            raise KeyError(
                f"元素 '{element_key}' 未在 YAML 配置中找到。"
                f"已加载的 key（前20个）: {available or '(无)'}"
            )

        raw = dict(self._elements[element_key])

        if 'locator' in raw:
            raw['locator'] = self._convert_locator(raw['locator'])
        if 'child_locator' in raw:
            raw['child_locator'] = self._convert_locator(raw['child_locator'])

        return raw

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

    def get_key_line(self, element_key: str) -> int | None:
        """返回元素键在 YAML 文件中的行号，未找到返回 None。"""
        return self._key_line.get(element_key)

    def __contains__(self, element_key: str) -> bool:
        return element_key in self._elements

    def __len__(self) -> int:
        return len(self._elements)
