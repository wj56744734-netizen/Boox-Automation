#!/usr/bin/env python3
"""从当前设备提取 page_source，过滤无意义元素后输出精简 XML。

用途: 将输出粘贴到飞书"预期结果"sheet 的 C 列（页面XML）。

默认行为: PyCharm 直接运行 → 保存到 artifacts/page_xml/ 目录
           -o 指定路径   → 保存到指定文件
           --stdout       → 打印到终端
"""
from __future__ import annotations

import argparse
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# 不需要保留的属性（硬编码过滤）
_IGNORED_ATTRS = {
    'bounds', 'index', 'instance', 'package', 'rotation',
    'display-id', 'NAF', 'enabled',
    'checked', 'selected', 'focused', 'drawing-order',
}

# 交互属性：元素具有任一为 true 即视为可交互
_INTERACTIVE_ATTRS = {'clickable', 'focusable', 'scrollable', 'checkable', 'long-clickable'}


def _is_meaningful(elem: ET.Element) -> bool:
    """判定元素是否值得保留：有 resource-id 且（可交互 或 有可见文本）。

    纯布局容器（ViewGroup/FrameLayout 等）既无交互属性也无文本，
    会被过滤掉，只保留交互骨架用于跨设备/跨版本稳定对比。
    """
    rid = elem.get('resource-id', '')
    if not rid or not rid.strip():
        return False

    text = elem.get('text', '')
    cd = elem.get('content-desc', '')
    if (text and text.strip()) or (cd and cd.strip()):
        return True

    for attr in _INTERACTIVE_ATTRS:
        if elem.get(attr, '').lower() == 'true':
            return True

    return False


def _clean_attrs(elem: ET.Element) -> None:
    for attr in list(elem.attrib):
        if attr in _IGNORED_ATTRS:
            del elem.attrib[attr]


def _prune_tree(elem: ET.Element) -> bool:
    """递归裁剪树。返回 True = 该元素应保留。"""
    children_to_keep = []
    for child in list(elem):
        if _prune_tree(child):
            children_to_keep.append(child)
        else:
            elem.remove(child)

    _clean_attrs(elem)

    if _is_meaningful(elem) or children_to_keep:
        return True
    return False


def extract(xml_string: str, compact: bool = True) -> str:
    """从全量 page_source XML 提取精简版。"""
    root = ET.fromstring(xml_string)

    if compact:
        _prune_tree(root)
    else:
        for elem in root.iter():
            _clean_attrs(elem)

    return ET.tostring(root, encoding='unicode')


def main():
    parser = argparse.ArgumentParser(
        description='从设备提取 page_source 并输出精简 XML'
    )
    parser.add_argument(
        '--from-file', type=str, default=None,
        help='从 Appium Inspector 导出的 XML 文件离线处理（无需连接设备）'
    )
    parser.add_argument(
        '-o', '--output', type=str, default=None,
        help='输出到指定文件（默认自动保存到 artifacts/page_xml/）'
    )
    parser.add_argument(
        '--stdout', action='store_true',
        help='打印到终端而非保存文件'
    )
    parser.add_argument(
        '--full', action='store_true',
        help='输出全量 XML（只清理属性，不过滤空容器）'
    )
    args = parser.parse_args()

    # 获取原始 XML
    if args.from_file:
        print(f'从文件读取: {args.from_file}', file=sys.stderr)
        try:
            with open(args.from_file, 'r', encoding='utf-8') as f:
                raw = f.read()
        except FileNotFoundError:
            print(f'错误: 文件不存在 — {args.from_file}', file=sys.stderr)
            sys.exit(1)
    else:
        print('正在连接设备并获取 page_source ...', file=sys.stderr)
        try:
            from boox_automation.driver import ensure_driver_alive
            ensure_driver_alive(reason="extract_page_xml")
            from boox_automation.driver import driver
            raw = driver.page_source
        except Exception as e:
            print(f'错误: 无法获取 page_source — {e}', file=sys.stderr)
            print('请确认 Appium 已启动且设备已连接', file=sys.stderr)
            print('或使用 --from-file 处理离线 XML 文件', file=sys.stderr)
            sys.exit(1)

    if not raw:
        print('错误: page_source 为空', file=sys.stderr)
        sys.exit(1)

    print(f'原始 XML 长度: {len(raw)} 字符', file=sys.stderr)

    # 原始元素总数
    root_before = ET.fromstring(raw)
    total_count = sum(1 for _ in root_before.iter())

    result = extract(raw, compact=not args.full)

    pct = len(result) * 100 // max(len(raw), 1)
    print(f'精简后长度: {len(result)} 字符 ({pct}%)', file=sys.stderr)

    # 统计并列出保留的元素
    root_after = ET.fromstring(result)
    kept_count = sum(1 for _ in root_after.iter())
    print(f'\n元素统计: 原始 {total_count} → 保留 {kept_count} ({kept_count * 100 // max(total_count, 1)}%)', file=sys.stderr)
    print('-' * 60, file=sys.stderr)
    for i, elem in enumerate(root_after.iter(), 1):
        tag = elem.tag
        rid = elem.get('resource-id', '')
        text = elem.get('text', '')
        cd = elem.get('content-desc', '')
        cls = elem.get('class', '')
        print(f'  {i:3d}. {tag}  class={cls}  resource-id={rid}  text={text}  content-desc={cd}', file=sys.stderr)

    if args.stdout:
        # 显式指定终端输出
        print(result)
        return

    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        # 自动生成路径: artifacts/page_xml/YYYY-MM-DD/HHmmss.xml
        today = time.strftime('%Y-%m-%d')
        ts = time.strftime('%H%M%S')
        base = Path(__file__).resolve().parent.parent  # scripts/ → boox_automation/
        output_dir = base / 'artifacts' / 'page_xml' / today
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f'{ts}.xml'

    output_path.write_text(result, encoding='utf-8')
    print(f'\n✓ 已保存: {output_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
