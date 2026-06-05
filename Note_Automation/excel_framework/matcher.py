"""元素匹配器：根据【】标记文本查找对应的 YAML element_key。"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ElementMatcher:
    """构建 text → element_key 反向索引，支持精确和模糊匹配。"""

    def __init__(self, elements_dir: str | None = None):
        if elements_dir is None:
            elements_dir = str(Path(__file__).resolve().parent)
        self._index: dict[str, list[str]] = {}  # text → [element_key, ...]
        self._elements: dict[str, dict] = {}  # element_key → element info
        self._build_index(Path(elements_dir))

    def _build_index(self, elements_dir: Path) -> None:
        """遍历元素定义文件（仅 Excel），构建反向索引。"""
        xlsx = elements_dir / "elements.xlsx"

        if xlsx.exists():
            self._load_from_excel(str(xlsx))
        else:
            logger.warning("elements.xlsx 不存在，元素索引为空")

        logger.debug(f"元素索引构建完成: {len(self._elements)} 个元素, {len(self._index)} 个索引词")

    def _load_from_excel(self, xlsx_path: str) -> None:
        """从 elements.xlsx 加载元素。"""
        import openpyxl
        from Note_Automation.Note_class.Note_element.element_loader import (
            _parse_overrides_text, _parse_checks_text)

        wb = openpyxl.load_workbook(xlsx_path)
        for sheet_name in wb.sheetnames:
            if sheet_name == "使用说明":
                continue
            ws = wb[sheet_name]
            headers = [str(c.value or "") for c in ws[2]]
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

                self._index_element(key, info)

    def _index_element(self, key: str, info: dict) -> None:
        """索引单个元素。"""
        self._elements[key] = info

        match = info.get("match", "")
        if match:
            self._index.setdefault(str(match), []).append(key)

        locator = info.get("locator", [])
        if len(locator) >= 2 and locator[1]:
            text = str(locator[1])
            if text != match:
                self._index.setdefault(text, []).append(key)

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
        partial = [k for k, v in self._elements.items()
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
        """从候选列表中按页面上下文评分选最佳匹配。"""
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

    def get_element(self, element_key: str) -> dict | None:
        return self._elements.get(element_key)

    def suggest_action(self, element_key: str) -> str:
        """根据 YAML 元素信息推断推荐动作类型。

        优先级: YAML 显式 action 字段 > 关键词推断 > 默认 click
        支持: click, assert, assert_not, assert_text, assert_toast, input, long_press
        """
        info = self._elements.get(element_key)
        if not info:
            return ""

        # 1. YAML 显式声明（最高优先级）
        explicit = info.get("action", "")
        valid_actions = ("click", "assert", "assert_not", "assert_text",
                         "assert_toast", "input", "long_press", "dismiss")
        if explicit in valid_actions:
            return explicit

        # 1.5 有 checks 多元素定义 → 推断为 assert 或 dismiss
        if info.get("checks"):
            if info.get("dismiss_with"):
                return "dismiss"
            return "assert"

        # 2. 从 element_key + operation 关键词推断
        keywords = " ".join([element_key, info.get("operation", "")])
        # toast 关键词
        if any(w in keywords for w in ("toast", "Toast", "提示")):
            return "assert_toast"
        # 文本校验
        if any(w in keywords for w in ("校验", "命名", "文案")):
            return "assert_text"
        # 不存在
        if any(w in keywords for w in ("不存在", "未找到", "暂无", "无笔记", "无记录")):
            return "assert_not"
        # 引导弹窗（可自动关闭）
        if any(w in keywords for w in ("首次引导", "弹窗引导", "知道了", "引导提示")):
            return "dismiss"
        # 引导/检查
        if any(w in keywords for w in ("引导", "检查", "查看")):
            return "assert"

        # 3. 默认点击
        return "click"

    @property
    def element_count(self) -> int:
        return len(self._elements)
