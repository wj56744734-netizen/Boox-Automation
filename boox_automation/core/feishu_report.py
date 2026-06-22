"""飞书测试报告卡片构建 + 推送。"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from boox_automation.core.feishu import send_card_message, upload_file_to_im, send_file_message
from boox_automation.core.config import feishu_chat_id, feishu_report_enabled

logger = logging.getLogger(__name__)

SEP = " ｜ "


def build_report_card(
    passed: int, failed: int, skipped: int,
    duration_sec: float,
    modules: list[str] | None = None,
    failed_cases: list[str] | None = None,
    skipped_cases: list[tuple[str, str]] | None = None,
    device: dict | None = None,
) -> dict:
    device = device or {}
    total = passed + failed + skipped
    pass_rate = passed / total * 100 if total > 0 else 0

    if failed > 0:
        header_color = "red"
    elif skipped > 0:
        header_color = "yellow"
    else:
        header_color = "green"

    mins, secs = divmod(int(duration_sec), 60)
    duration_str = f"{mins}m{secs}s" if mins else f"{secs}s"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    elements = []

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": _device_section(device)},
    })
    elements.append({"tag": "hr"})

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": _summary_section(
            modules, now, duration_str, passed, failed, skipped, pass_rate,
        )},
    })

    if skipped_cases:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": _cases_section("跳过用例", skipped_cases)},
        })

    if failed_cases:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": _failed_section(failed_cases)},
        })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "📎 完整 HTML 测试报告见下方文件，下载后双击即可打开"}],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📊 boox_automation 测试报告"},
            "template": header_color,
        },
        "elements": elements,
    }


def _device_section(device: dict) -> str:
    d = device or {}
    name = d.get("device_name", "") or "未知"
    size = d.get("device_size", "")
    colour = d.get("driver_colour", "")
    dtype = d.get("devices_reader", "")
    region = d.get("device_region", "")
    plat = d.get("device_platform", "")
    bt = d.get("build_type", "")
    res = d.get("filtered_size", "")
    bdt = d.get("build_date_time", "")

    rows = []

    row1 = [f"设备：{name}"]
    if size:
        row1.append(f"尺寸：{size}寸")
    if colour:
        row1.append(f"屏幕：{colour}")
    rows.append(SEP.join(row1))

    row2 = []
    if dtype:
        row2.append(f"类型：{dtype}")
    if res:
        row2.append(f"分辨率：{res}")
    if plat:
        row2.append(f"平台：{plat}")
    if region:
        row2.append(f"区域：{region}")
    if row2:
        rows.append(SEP.join(row2))

    row3 = []
    if bt:
        row3.append(f"构建：{bt}")
    if bdt:
        row3.append(f"系统版本号：{bdt}")
    if row3:
        rows.append(SEP.join(row3))

    return "**设备信息**\n" + "\n".join(rows)


def _summary_section(
    modules: list[str] | None,
    now: str, duration_str: str,
    passed: int, failed: int, skipped: int, pass_rate: float,
) -> str:
    lines = ["**执行概况**"]
    if modules:
        lines.append(f"模块：{'、'.join(modules)}")
    lines.append(f"时间：{now}{SEP}耗时：{duration_str}")
    lines.append(f"✅ 通过：**{passed}**{SEP}❌ 失败：**{failed}**{SEP}⏭️ 跳过：**{skipped}**")
    lines.append(f"通过率：**{pass_rate:.1f}%**")
    return "\n".join(lines)


def _cases_section(title: str, cases: list[tuple[str, str]]) -> str:
    items = [f"· {name} — {reason}" for name, reason in cases[:10]]
    more = f"\n... 等共 {len(cases)} 条" if len(cases) > 10 else ""
    return f"**{title}**\n" + "\n".join(items) + more


def _failed_section(cases: list[str]) -> str:
    items = [f"· {name}" for name in cases[:10]]
    more = f"\n... 等共 {len(cases)} 条" if len(cases) > 10 else ""
    return f"**失败用例**\n" + "\n".join(items) + more


def push_report(
    card: dict,
    html_report_path: str | None = None,
) -> bool:
    """推送测试报告到飞书：先发卡片，再发 HTML 报告文件。

    返回 True 表示卡片至少发送成功。
    """
    if not feishu_report_enabled():
        logger.info("飞书报告推送未启用（feishu.report.enabled=false），跳过")
        return False

    chat_id = feishu_chat_id()
    if not chat_id:
        logger.warning("未配置 feishu.report.chat_id，跳过飞书报告推送")
        return False

    try:
        send_card_message(chat_id, card)
        logger.info("飞书报告卡片已发送")
    except Exception as e:
        logger.error(f"飞书报告卡片发送失败: {e}")
        return False

    if html_report_path:
        try:
            _upload_html_report(chat_id, html_report_path)
        except Exception as e:
            logger.error(f"飞书报告文件上传失败: {e}")

    return True


def _upload_html_report(chat_id: str, html_path: str) -> None:
    """上传 HTML 报告文件到飞书。"""
    path = Path(html_path)
    if not path.exists():
        logger.warning(f"HTML 报告文件不存在: {html_path}")
        return

    file_key = upload_file_to_im(str(path), file_type="stream")
    send_file_message(chat_id, file_key)
    logger.info("飞书 HTML 报告文件已发送")
