"""XML 页面对比引擎：从预期和实际 page_source 提取元素签名集做集合对比。

匹配只看 class + resource-id，text 和 content-desc 差异仅 INFO 级别报告，不影响结果。
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# 自动忽略的属性
_IGNORED_ATTRS = {
    'bounds', 'index', 'instance', 'package', 'rotation',
    'display-id', 'NAF', 'focusable', 'clickable', 'enabled',
    'checked', 'checkable', 'scrollable', 'long-clickable',
    'selected', 'focused', 'drawing-order',
}

# 有意义元素判定：至少有一个非空
_MEANINGFUL_ATTRS = {'resource-id', 'text', 'content-desc'}


def _is_meaningful(elem: ET.Element) -> bool:
    for attr in _MEANINGFUL_ATTRS:
        val = elem.get(attr, '')
        if val and val.strip():
            return True
    return False


@dataclass(frozen=True)
class ElementSignature:
    class_name: str
    resource_id: str
    text: str
    content_desc: str

    def match_key(self) -> tuple:
        """匹配键只基于 class + resource-id。"""
        return (self.class_name, self.resource_id)

    def __hash__(self):
        return hash(self.match_key())

    def __eq__(self, other):
        if not isinstance(other, ElementSignature):
            return False
        return self.match_key() == other.match_key()

    def to_human(self) -> str:
        """人类可读的描述，缺失时用于报告。"""
        short_class = self.class_name.split('.')[-1] if '.' in self.class_name else self.class_name
        parts = [f'[{short_class}]']
        if self.resource_id:
            parts.append(f'resource-id={self.resource_id}')
        if self.text:
            parts.append(f"text='{self.text}'")
        if self.content_desc:
            parts.append(f"content-desc='{self.content_desc}'")
        return ' '.join(parts)


class SignatureExtractor:
    """从 XML 字符串中提取元素签名集。"""

    @staticmethod
    def extract(xml_string: str) -> set[ElementSignature]:
        root = ET.fromstring(xml_string)
        signatures = set()
        for elem in root.iter():
            if _is_meaningful(elem):
                signatures.add(ElementSignature(
                    class_name=elem.tag,
                    resource_id=elem.get('resource-id', ''),
                    text=elem.get('text', ''),
                    content_desc=elem.get('content-desc', ''),
                ))
        return signatures


@dataclass
class CompareResult:
    status: str  # pass / fail
    expected_count: int
    actual_count: int
    matched_count: int
    missing: list[ElementSignature] = field(default_factory=list)
    extra: list[ElementSignature] = field(default_factory=list)
    text_diffs: list[dict] = field(default_factory=list)
    mode: str = 'visible'  # visible / not_visible

    @property
    def text_diff_count(self) -> int:
        return len(self.text_diffs)

    def summary(self) -> str:
        suffix = f' (文本变更: {self.text_diff_count}个)' if self.text_diff_count else ''

        if self.mode == 'not_visible':
            if self.status == 'pass':
                return f'预期{self.expected_count}个元素全部不存在，验证通过{suffix}'
            else:
                lines = [
                    f'预期{self.expected_count}个元素应全部不存在，'
                    f'但仍有{self.matched_count}个存在{suffix}'
                ]
                for sig in self.extra:
                    lines.append(f'  仍存在: {sig.to_human()}')
                return '\n'.join(lines)

        if self.status == 'pass':
            lines = [f'预期{self.expected_count}个元素全部存在{suffix}']
        else:
            lines = [
                f'预期{self.expected_count}个元素，匹配{self.matched_count}个，'
                f'缺失{len(self.missing)}个{suffix}'
            ]
            for sig in self.missing:
                lines.append(f'  缺失: {sig.to_human()}')

        for d in self.text_diffs:
            lines.append(
                f'  文本变更(INFO): {d["element"]}\n'
                f'                  预期text={d["expected"]!r} 实际text={d["actual"]!r}'
            )
        return '\n'.join(lines)


class XmlChecker:
    """XML 对比引擎。"""

    @staticmethod
    def check(expected_xml: str, actual_xml: str,
              mode: str = 'visible') -> CompareResult:
        expected_sigs = SignatureExtractor.extract(expected_xml)
        actual_sigs = SignatureExtractor.extract(actual_xml)

        # 显式从 expected 端构建匹配集（保证保留 expected 端的 text）
        matched_expected = {s for s in expected_sigs if s in actual_sigs}
        missing_list = sorted(expected_sigs - matched_expected, key=lambda s: s.to_human())
        extra_list = sorted(actual_sigs - expected_sigs, key=lambda s: s.to_human())

        # 不可见模式: 预期元素都不该存在
        if mode == 'not_visible':
            still_present = sorted(matched_expected, key=lambda s: s.to_human())
            status = 'fail' if matched_expected else 'pass'
            return CompareResult(
                status=status,
                expected_count=len(expected_sigs),
                actual_count=len(actual_sigs),
                matched_count=len(matched_expected),
                extra=still_present,
                mode='not_visible',
            )

        # 可见模式: 预期元素都应存在
        text_diffs = []
        actual_map = {s.match_key(): s for s in actual_sigs}
        for exp_sig in matched_expected:
            act_sig = actual_map.get(exp_sig.match_key())
            if act_sig is None:
                continue
            if exp_sig.text and act_sig.text and exp_sig.text != act_sig.text:
                text_diffs.append({
                    'element': exp_sig.to_human(),
                    'expected': exp_sig.text,
                    'actual': act_sig.text,
                })

        status = 'fail' if missing_list else 'pass'

        return CompareResult(
            status=status,
            expected_count=len(expected_sigs),
            actual_count=len(actual_sigs),
            matched_count=len(matched_expected),
            missing=missing_list,
            text_diffs=text_diffs,
            mode='visible',
        )


# ---- 单元测试 ----
if __name__ == '__main__':
    xml_a = '''<hierarchy>
        <android.widget.FrameLayout resource-id="com.test:id/root">
            <android.widget.TextView resource-id="com.test:id/title" text="笔记"/>
            <android.widget.Button resource-id="com.test:id/btn_create" text="创建"/>
            <android.widget.ImageView resource-id="com.test:id/icon"/>
        </android.widget.FrameLayout>
    </hierarchy>'''

    xml_b = '''<hierarchy>
        <android.widget.FrameLayout resource-id="com.test:id/root">
            <android.widget.TextView resource-id="com.test:id/title" text="My Notes"/>
            <android.widget.Button resource-id="com.test:id/btn_create" text="新建"/>
            <android.widget.TextView resource-id="com.test:id/tv_new" text="新功能"/>
        </android.widget.FrameLayout>
    </hierarchy>'''

    print("=== 基础对比（有缺失）===")
    r = XmlChecker.check(xml_a, xml_b)
    print(r.summary())
    # xml_a: root, title, btn_create, icon = 4
    # xml_b: root, title, btn_create, tv_new = 4
    # match_key 只看 (class, resource-id): root=root✓, title=title✓, btn_create=btn_create✓, icon只在xml_a, tv_new只在xml_b
    # matched=3, missing=1(icon), text_diffs: title text不同, btn_create text不同
    assert r.status == 'fail', f"应有缺失, got {r.status}"
    assert len(r.missing) == 1, f"应缺1个(icon), got {len(r.missing)}"
    assert r.text_diff_count == 2, f"应有2个文本变更, got {r.text_diff_count}"
    print("✓ 基础对比通过")

    print("\n=== 完全相同 ===")
    r = XmlChecker.check(xml_a, xml_a)
    print(r.summary())
    assert r.status == 'pass', f"应pass, got {r.status}"
    assert r.text_diff_count == 0, "文本变更应为0"
    print("✓ 完全相同通过")

    print("\n=== text 差异不影响 pass ===")
    xml_c = '''<hierarchy>
        <android.widget.FrameLayout resource-id="com.test:id/root">
            <android.widget.TextView resource-id="com.test:id/title" text="新标题"/>
            <android.widget.Button resource-id="com.test:id/btn_create" text="创建新"/>
            <android.widget.ImageView resource-id="com.test:id/icon"/>
        </android.widget.FrameLayout>
    </hierarchy>'''
    r = XmlChecker.check(xml_a, xml_c)
    print(r.summary())
    assert r.status == 'pass', f"text差异不应影响pass, got {r.status}"
    assert r.text_diff_count == 2, f"应有2个文本变更, got {r.text_diff_count}"
    print("✓ text差异不影响pass")

    print("\n全部测试通过 ✓")
