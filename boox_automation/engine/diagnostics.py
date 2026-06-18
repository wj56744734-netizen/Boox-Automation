"""预期结果匹配失败的诊断信息模板。"""


def expected_sheet_not_found(searched: list[str], module_hint: str) -> str:
    """情况A：完全没有加载到任何预期结果工作表。"""
    lines = []
    lines.append("──────────────────────────────────────────────────")
    lines.append("  原因: 飞书元素表中不存在以下预期结果工作表:")
    for s in searched:
        lines.append(f"    {s} → 缺失")
    lines.append("  ────────────────────────────────────────────────")
    lines.append("  解决方式:")
    lines.append(f"    1. 在飞书元素表中新建「预期结果【{module_hint}】」工作表")
    lines.append(f"       表头: 模块 | 匹配文本 | 定位元素 | xml页面 | 操作 | 用途说明")
    lines.append(f"       数据行: {module_hint} | <匹配文本> | (XPath或留空) | (XML或留空) | 断言存在 | (说明)")
    lines.append("    2. 或将预期页面 XML 放入本地文件:")
    lines.append(f"       data/expected_pages/{module_hint}.<匹配文本>.xml")
    lines.append("──────────────────────────────────────────────────")
    return "\n".join(lines)


def expected_tag_not_matched(tag: str, found_sheets: list[str], total: int,
                              match_index: dict, module_hint: str) -> str:
    """情况B：有预期结果工作表，但 B 列未匹配。"""
    found_str = '、'.join(found_sheets) if found_sheets else "无"
    index_keys = sorted(match_index.keys()) if match_index else []
    index_str = '、'.join(index_keys) if index_keys else "(空)"

    lines = []
    lines.append("──────────────────────────────────────────────────")
    lines.append(f"  已加载预期结果工作表: {found_str}")
    lines.append(f"  已加载预期结果条目: {total}")
    lines.append(f"  当前 B 列已有匹配文本({len(match_index)}条): {index_str}")
    lines.append(f"  未匹配的文本: 【{tag}】")
    lines.append("  ────────────────────────────────────────────────")
    lines.append("  解决方式:")
    lines.append(f"    在「预期结果【{module_hint}】」工作表中新增一行:")
    lines.append(f"    B 列（匹配文本）: {tag}")
    lines.append("    C 列（定位元素）: 填入对应 XPath")
    lines.append("    D 列（xml页面）: 填入 Appium Inspector 导出的页面 XML")
    lines.append("    E 列（操作）: 断言存在 / 断言不存在 / 断言toast / 断言toast不出现")
    lines.append(f"    注意: B 列文字必须与 I 列【{tag}】完全一致")
    lines.append("──────────────────────────────────────────────────")
    return "\n".join(lines)
