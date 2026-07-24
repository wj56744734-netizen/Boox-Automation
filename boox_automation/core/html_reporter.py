"""自包含 HTML 用例测试报告生成器。

生成单文件 HTML 报告，可直接双击在浏览器中打开，无需 HTTP 服务。
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_STEP_PREFIX_RE = re.compile(r"^\d+[\.\、]\s*")

def _strip_step_prefix(text: str) -> str:
    """去掉步骤文本开头的序号前缀（如 '11. '、'12、'），避免与重新编号重复。"""
    return _STEP_PREFIX_RE.sub("", text).strip()

# ── CSS 模板（静态，与 report_case.html 保持一致） ──

_CSS = """
:root {
  --bg: #0f1119; --surface: #1a1d2e; --surface2: #222538;
  --border: #2a2d3e; --border2: #363a50;
  --text: #e1e4ed; --text2: #9ca0b0; --text3: #6b6f80;
  --green: #4ade80; --green-bg: rgba(74,222,128,.1);
  --red: #f87171; --red-bg: rgba(248,113,113,.08);
  --orange: #fbbf24; --orange-bg: rgba(251,191,36,.08);
  --blue: #60a5fa; --blue-bg: rgba(96,165,250,.1);
  --purple: #a78bfa; --purple-bg: rgba(167,139,250,.1);
  --radius: 10px;
  --font: 'Inter','Noto Sans SC','PingFang SC',sans-serif;
  --mono: 'JetBrains Mono','SF Mono',monospace;
}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:var(--font);background:var(--bg);color:var(--text);line-height:1.55;-webkit-font-smoothing:antialiased;padding:32px 24px 48px}
.wrap{max-width:1020px;margin:0 auto}
.hd{margin-bottom:24px}
.hd-row{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}
.hd h1{font-size:26px;font-weight:700;letter-spacing:-.02em}
.pill{font-size:12px;font-weight:600;padding:5px 14px;border-radius:99px;background:var(--red-bg);color:var(--red);border:1px solid rgba(248,113,113,.2)}
.pill.ok{background:var(--green-bg);color:var(--green);border-color:rgba(74,222,128,.2)}
.hd .meta{font-size:13px;color:var(--text3);margin-top:4px;display:flex;gap:16px;flex-wrap:wrap}
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:18px 22px}
.kpi .lbl{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.06em;font-weight:500}
.kpi .val{font-family:var(--mono);font-size:38px;font-weight:700;line-height:1.15;margin-top:2px}
.kpi .sub{font-size:11px;color:var(--text3);margin-top:2px}
.kpi.g{border-bottom:3px solid var(--green)}.kpi.g .val{color:var(--green)}
.kpi.r{border-bottom:3px solid var(--red)}.kpi.r .val{color:var(--red)}
.kpi.o{border-bottom:3px solid var(--orange)}.kpi.o .val{color:var(--orange)}
.kpi.b{border-bottom:3px solid var(--purple)}.kpi.b .val{color:var(--purple)}
.sec{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:14px;overflow:hidden}
.sec-hd{display:flex;align-items:center;gap:10px;padding:14px 22px;font-size:15px;font-weight:600;cursor:pointer;user-select:none;border-bottom:1px solid transparent}
.sec-hd:hover{background:var(--surface2)}
.sec.open .sec-hd{border-bottom-color:var(--border)}
.sec-hd .dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.dot.g{background:var(--green)}.dot.r{background:var(--red)}.dot.o{background:var(--orange)}.dot.p{background:var(--purple)}
.sec-hd .cnt{font-family:var(--mono);font-size:11px;font-weight:500;padding:2px 8px;border-radius:4px}
.cnt.g{background:var(--green-bg);color:var(--green)}.cnt.r{background:var(--red-bg);color:var(--red)}
.cnt.o{background:var(--orange-bg);color:var(--orange)}.cnt.p{background:var(--purple-bg);color:var(--purple)}
.sec-arrow{margin-left:auto;font-size:11px;color:var(--text3);transition:transform .2s}
.sec.open .sec-arrow{transform:rotate(180deg)}
.sec:not(.open) .sec-hd{border-bottom:none}
.sec-bd{display:none}.sec.open .sec-bd{display:block}
.dev-row{display:flex;flex-wrap:wrap;gap:6px;padding:14px 22px}
.dev-chip{display:inline-flex;align-items:center;gap:5px;padding:5px 12px;border-radius:6px;font-family:var(--mono);font-size:11px;background:var(--surface2);border:1px solid var(--border)}
.dev-chip .dl{color:var(--text3)}.dev-chip .dv{font-weight:500}
.fail-list{padding:6px 22px 18px;display:flex;flex-direction:column;gap:8px}
.fail-card{background:var(--surface2);border:1px solid var(--border);border-left:3px solid var(--red);border-radius:0 8px 8px 0;padding:14px 18px;cursor:pointer;transition:background .2s}
.fail-card:hover{background:rgba(248,113,113,.06)}
.fail-card .fc-top{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:4px}
.fail-card .fc-title{font-size:14px;font-weight:600}
.fail-card .fc-meta{font-size:12px;color:var(--text3);display:flex;gap:10px}
.fail-card .fc-cause{font-size:13px;color:var(--red);margin-bottom:6px}
.fail-steps{margin-top:8px}
.fstep{display:flex;gap:8px;padding:5px 0;font-size:13px;align-items:flex-start}
.fstep .fsi{width:18px;flex-shrink:0;text-align:center}
.fstep .fst{flex:1}.fstep .fsx{color:var(--text3);font-size:12px;text-align:right;max-width:300px;flex-shrink:0}
.fbar{display:flex;gap:8px;align-items:center;padding:12px 22px 8px;flex-wrap:wrap}
.fbtn{background:var(--surface);border:1px solid var(--border);border-radius:99px;padding:5px 14px;font-size:11px;color:var(--text2);cursor:pointer;font-family:var(--font);font-weight:500;transition:all .2s}
.fbtn:hover{color:var(--text);border-color:var(--border2)}
.fbtn.act{color:var(--blue);border-color:var(--blue);background:var(--blue-bg)}
.fbtn.fr.act{color:var(--red);border-color:var(--red);background:var(--red-bg)}
.fsearch{background:var(--surface);border:1px solid var(--border);border-radius:99px;padding:5px 14px;font-size:11px;color:var(--text);outline:none;font-family:var(--font);width:170px;margin-left:auto}
.fsearch:focus{border-color:var(--blue)}.fsearch::placeholder{color:var(--text3)}
.tbl-scroll{max-height:60vh;overflow-y:auto;border-top:1px solid var(--border)}
.tbl-scroll::-webkit-scrollbar{width:4px}
.tbl-scroll::-webkit-scrollbar-track{background:transparent}
.tbl-scroll::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl thead{position:sticky;top:0;z-index:2}
.tbl thead th{text-align:left;padding:9px 14px;font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text3);font-weight:500;background:var(--surface);border-bottom:1px solid var(--border)}
.tbl tbody td{padding:9px 14px;border-bottom:1px solid var(--border);vertical-align:middle}
.tbl .num{font-family:var(--mono);font-size:12px;text-align:right}
.mod-div td{padding:9px 14px;font-size:12px;font-weight:600;color:var(--blue);background:var(--surface2)}
.exp-row{cursor:pointer;transition:background .15s}
.exp-row:hover td{background:var(--surface2)}
.exp-row.hidden{display:none}
.row-fail{background:var(--red-bg)}.row-fail.hidden{display:none}
.row-skip{opacity:.5}.row-skip.hidden{display:none}
.exp-icon{display:inline-block;width:16px;font-size:10px;color:var(--text3);transition:transform .2s;text-align:center}
.exp-icon.open{transform:rotate(90deg)}
.detail-row{display:none}
.detail-row.open{display:table-row}
.detail-row td{padding:0 14px 14px 36px}
.dbox{background:var(--surface2);border:1px solid var(--border);border-radius:8px;overflow:hidden}
.dbox.fail{border-left:3px solid var(--red)}
.dbox .dh{font-size:12px;color:var(--text3);padding:9px 14px;display:flex;gap:18px;border-bottom:1px solid var(--border)}
.dbox .dp{font-size:12px;color:var(--text3);padding:7px 14px;border-bottom:1px solid var(--border)}
.step{display:flex;gap:8px;padding:7px 14px;font-size:13px;align-items:flex-start;border-bottom:1px solid var(--border)}
.step:last-child{border-bottom:none}
.step .si{width:18px;flex-shrink:0;text-align:center}
.step .stx{flex:1}.step .sx{color:var(--text3);font-size:12px;text-align:right;max-width:300px;flex-shrink:0}
.step.err{background:var(--red-bg)}
.pr{display:inline-block;padding:2px 8px;border-radius:4px;font-family:var(--mono);font-size:10px;font-weight:600}
.pr.p0{background:rgba(248,113,113,.15);color:var(--red)}
.pr.p1{background:rgba(251,191,36,.15);color:var(--orange)}
.pr.p2{background:rgba(96,165,250,.15);color:var(--blue)}
.st{display:inline-block;padding:2px 8px;border-radius:4px;font-family:var(--mono);font-size:10px;font-weight:500}
.st.pass{background:rgba(74,222,128,.12);color:var(--green)}
.st.fail{background:rgba(248,113,113,.12);color:var(--red)}
.st.skip{background:rgba(251,191,36,.1);color:var(--orange)}
@keyframes flash{0%,100%{box-shadow:none}50%{box-shadow:0 0 0 3px var(--purple),0 0 24px rgba(167,139,250,.25)}}
tr.flash td{animation:flash 1.2s ease 3;border-radius:4px}
.ft{text-align:center;padding:24px;font-size:12px;color:var(--text3)}
"""

_JS = """
var cf='all';
function tgl(id){
  var d=document.getElementById(id),ic=document.getElementById('ic-'+id);
  if(d.classList.contains('open')){d.classList.remove('open');if(ic)ic.classList.remove('open')}
  else{d.classList.add('open');if(ic)ic.classList.add('open')}
}
function fil(mode,btn){
  if(mode!=='search'){cf=mode;document.querySelectorAll('.fbtn').forEach(function(b){b.classList.remove('act')});if(btn)btn.classList.add('act')}
  var q=(document.getElementById('fs').value||'').toLowerCase();
  var rows=document.querySelectorAll('#caseSec tbody tr'),n=0;
  for(var i=0;i<rows.length;i++){
    var r=rows[i];
    if(r.classList.contains('detail-row'))continue;
    if(r.classList.contains('mod-div')){if(cf==='search'&&q){r.classList.add('hidden')}else{r.classList.remove('hidden')};continue}
    var f=r.classList.contains('row-fail'),s=r.classList.contains('row-skip'),p=!f&&!s;
    var show=true;
    if(cf==='fail')show=f;else if(cf==='skip')show=s;else if(cf==='pass')show=p;
    if(q)show=show&&(r.textContent||'').toLowerCase().indexOf(q)>=0;
    r.classList.toggle('hidden',!show);
    var dd=r.getAttribute('data-detail');
    if(dd){var d=document.getElementById(dd);if(d)d.classList.toggle('hidden',!show)}
    if(show)n++;
  }
  var divs=document.querySelectorAll('#caseSec tbody tr.mod-div');
  for(var j=0;j<divs.length;j++){
    var d=divs[j],nxt=d.nextElementSibling,hv=false;
    while(nxt&&!nxt.classList.contains('mod-div')){if(!nxt.classList.contains('hidden')&&!nxt.classList.contains('detail-row')){hv=true;break}nxt=nxt.nextElementSibling}
    if(cf==='search'&&q)d.classList.add('hidden');else d.classList.toggle('hidden',!hv);
  }
  document.getElementById('caseCnt').textContent=n;
}
function goFail(id){
  var sec=document.getElementById('caseSec');if(!sec.classList.contains('open'))sec.classList.add('open');
  cf='all';document.querySelectorAll('.fbtn').forEach(function(b){b.classList.remove('act')});var ba=document.querySelector('.fbtn');if(ba)ba.classList.add('act');
  document.getElementById('fs').value='';
  var rows=document.querySelectorAll('#caseSec tbody tr');
  for(var i=0;i<rows.length;i++)rows[i].classList.remove('hidden');
  document.getElementById('caseCnt').textContent='TOTAL';
  document.querySelectorAll('#caseSec tbody tr.mod-div').forEach(function(d){d.classList.remove('hidden')});
  var tr=document.getElementById(id);if(!tr)return;
  var dd=tr.getAttribute('data-detail');
  if(dd){var d=document.getElementById(dd),ic=document.getElementById('ic-'+dd);if(d){d.classList.add('open');if(ic)ic.classList.add('open')}}
  var ts=document.getElementById('ts');if(ts){var cr=ts.getBoundingClientRect(),tr2=tr.getBoundingClientRect();ts.scrollTo({top:ts.scrollTop+(tr2.top-cr.top)-cr.height/3,behavior:'smooth'})}
  tr.classList.add('flash');setTimeout(function(){tr.classList.remove('flash')},3600);
}
"""


def _pr(priority: str) -> str:
    """优先级标签 HTML。"""
    p = (priority or "").upper()
    cls = "p0" if p == "P0" else ("p1" if p == "P1" else "p2")
    return f'<span class="pr {cls}">{p}</span>'


def _st(status: str) -> str:
    """状态标签 HTML。"""
    if status == "pass":
        return '<span class="st pass">通过</span>'
    elif status == "fail":
        return '<span class="st fail">失败</span>'
    elif status == "skip":
        return '<span class="st skip">跳过</span>'
    return '<span class="st">—</span>'


def _escape(text: str) -> str:
    """HTML 实体转义。"""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _case_status(case: Any) -> str:
    """根据 ParsedCase 的步骤/预期结果状态计算整体状态。"""
    if case.skip_reason:
        return "skip"
    for step in case.steps:
        if step.status in ("fail", ""):
            return "fail"
    for ep in case.expected_pages:
        if ep.status in ("fail", ""):
            return "fail"
    # 全部 pass 或 skip
    all_skip = all(s.status == "skip" for s in case.steps) if case.steps else False
    if all_skip:
        return "skip"
    return "pass"


def _build_steps_html(steps: list, expected_pages: list | None = None) -> str:
    """生成步骤明细 HTML。"""
    parts = []
    for i, step in enumerate(steps):
        seq = i + 1
        if step.status == "fail":
            si = '<span class="si" style="color:var(--red)">✕</span>'
            stx = f'<span class="stx" style="color:var(--red)">{seq}. {_escape(_strip_step_prefix(step.raw))}</span>'
            sx = f'<span class="sx" style="color:var(--red)">{_escape(step.tag)}</span>'
            parts.append(f'<div class="step err">{si}{stx}{sx}</div>')
        elif step.status == "pass":
            si = '<span class="si" style="color:var(--green)">✓</span>'
            stx = f'<span class="stx">{seq}. {_escape(_strip_step_prefix(step.raw))}</span>'
            sx = f'<span class="sx">{_escape(step.action)}</span>'
            parts.append(f'<div class="step">{si}{stx}{sx}</div>')
        else:
            si = '<span class="si" style="color:var(--text3)">—</span>'
            stx = f'<span class="stx" style="color:var(--text3)">{seq}. {_escape(_strip_step_prefix(step.raw))}</span>'
            sx = f'<span class="sx" style="color:var(--text3)">未执行</span>'
            parts.append(f'<div class="step">{si}{stx}{sx}</div>')
    return "\n".join(parts)


def _build_precondition_html(case: Any) -> str:
    """生成前置条件显示。"""
    if not case.preconditions:
        return "无"
    tags = []
    for pc in case.preconditions:
        if pc.type == "condition":
            tags.append(f'<span style="color:var(--blue)">【{_escape(pc.kind)}】</span>')
        elif pc.type == "cleanup":
            tags.append(f'<span style="color:var(--orange)">【{_escape(pc.kind)}】</span>')
        else:
            tags.append(_escape(pc.raw))
    return " · ".join(tags) if tags else "无"


def _build_device_chips(device: dict) -> str:
    """生成设备信息芯片 HTML。"""
    if not device:
        return ""
    chips = []
    mapping = [
        ("设备", device.get("device_name", "") or "未知"),
        ("类型", device.get("devices_reader", "")),
        ("屏幕", f"{device.get('device_size', '')}寸 {device.get('driver_colour', '')}".strip("寸 ")),
        ("分辨率", device.get("filtered_size", "")),
        ("平台", device.get("device_platform", "")),
        ("区域", device.get("device_region", "")),
        ("系统", f"{device.get('version_info', '')} ({device.get('build_type', '')})".strip(" ()")),
        ("构建", device.get("build_date_time", "")),
    ]
    for label, value in mapping:
        if value:
            chips.append(
                f'<span class="dev-chip"><span class="dl">{label}</span>'
                f'<span class="dv">{_escape(str(value))}</span></span>'
            )
    return "\n".join(chips)


def build_case_report(
    cases: list,
    device_info: dict | None = None,
    session_start: float | None = None,
    modules: list[str] | None = None,
) -> str:
    """生成用例测试报告 HTML 字符串。

    Args:
        cases: ParsedCase 列表（含运行时填充的 status 字段）
        device_info: 设备信息字典
        session_start: 测试开始时间戳 (time.time())
        modules: 执行的模块列表
    """
    device_info = device_info or {}
    total = len(cases)

    # ── 按状态分类 ──
    failed: list[Any] = []
    skipped: list[Any] = []
    passed: list[Any] = []
    for c in cases:
        st = _case_status(c)
        if st == "fail":
            failed.append(c)
        elif st == "skip":
            skipped.append(c)
        else:
            passed.append(c)

    passed_n = len(passed)
    failed_n = len(failed)
    skipped_n = len(skipped)
    pass_rate = passed_n / total * 100 if total > 0 else 0

    # ── Header ──
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    duration_sec = time.time() - session_start if session_start else 0
    mins, secs = divmod(int(duration_sec), 60)
    duration_str = f"{mins}m{secs}s" if mins else f"{secs}s"

    module_str = "、".join(modules) if modules else ""
    device_str = (
        f"{device_info.get('device_name', '') or '未知'} · "
        f"{device_info.get('device_size', '')}寸 {device_info.get('driver_colour', '')} · "
        f"{device_info.get('device_region', '')} · "
        f"{device_info.get('version_info', '')}"
    )

    status_pill = (
        '<span class="pill">全部通过</span>' if failed_n == 0
        else f'<span class="pill">{failed_n} 条失败</span>'
    )

    # ── Failed cases section ──
    failed_section = ""
    if failed:
        fail_cards = []
        for idx, c in enumerate(failed):
            fid = f"fc{idx}"
            rid = f"rf{idx}"
            steps_html = _build_steps_html(c.steps)
            cause = "根因："
            for s in c.steps:
                if s.status == "fail":
                    cause += _escape(s.raw[:80])
                    break
            if not cause:
                cause = "根因：断言失败"

            fail_cards.append(
                f'<div class="fail-card" id="{fid}" '
                f'onclick="goFail(\'{rid}\')">'
                f'<div class="fc-top">'
                f'<span class="fc-title">{_escape(c.title)}</span>'
                f'<span class="fc-meta">{_pr(c.priority)} {_escape(c.module)} · {duration_str}</span>'
                f'</div>'
                f'<div class="fc-cause">{_escape(cause)}</div>'
                f'<div class="fail-steps">{steps_html}</div>'
                f'</div>'
            )

        failed_section = f"""
<div class="sec open">
  <div class="sec-hd" onclick="this.parentElement.classList.toggle('open')">
    <span class="dot r"></span> 失败用例 <span class="cnt r">{failed_n}</span>
    <span class="sec-arrow">▾</span>
  </div>
  <div class="sec-bd">
    <div class="fail-list">
      {"".join(fail_cards)}
    </div>
  </div>
</div>"""

    # ── All cases table ──
    # 按模块分组
    module_groups: dict[str, list] = {}
    module_order: list[str] = []
    for c in cases:
        mod = c.module or "其他"
        if mod not in module_groups:
            module_groups[mod] = []
            module_order.append(mod)
        module_groups[mod].append(c)

    table_rows = []
    detail_idx = 0
    fail_row_ids: dict[int, str] = {}  # failed case index → row id
    fail_idx = 0

    for mod in module_order:
        mod_cases = module_groups[mod]
        mod_pass = sum(1 for c in mod_cases if _case_status(c) == "pass")
        mod_fail = sum(1 for c in mod_cases if _case_status(c) == "fail")
        mod_skip = sum(1 for c in mod_cases if _case_status(c) == "skip")
        parts = [f"{mod}"]
        if mod_pass: parts.append(f"通过 {mod_pass}")
        if mod_fail: parts.append(f"失败 {mod_fail}")
        if mod_skip: parts.append(f"跳过 {mod_skip}")
        table_rows.append(f'<tr class="mod-div"><td colspan="6">{_escape(" · ".join(parts))}</td></tr>')

        for c in mod_cases:
            st = _case_status(c)
            detail_idx += 1
            did = f"d{detail_idx}"
            row_class = "exp-row"
            row_extra = ""
            if st == "fail":
                row_class += " row-fail"
                row_extra = ' style="font-weight:600"'
                fid = f"rf{fail_idx}"
                fail_row_ids[fail_idx] = fid
                fail_idx += 1
            elif st == "skip":
                row_class += " row-skip"

            # icon state
            icon_state = "open" if st == "fail" else ""
            detail_open = " open" if st == "fail" else ""

            # title
            title_html = f"<b>{_escape(c.title)}</b>" if st == "fail" else _escape(c.title)

            # duration
            dur = "—" if st == "skip" else "—"

            # detail box
            precond_html = _build_precondition_html(c)
            steps_html = _build_steps_html(c.steps)
            dbox_class = "dbox fail" if st == "fail" else "dbox"
            detail_html = (
                f'<div class="{dbox_class}">'
                f'<div class="dp">前置条件：{precond_html}</div>'
                f'{steps_html}'
                f'</div>'
            )

            # row id for fail cards
            rid_attr = f'id="{fail_row_ids.get(fail_idx - 1 if st == "fail" else -1, "")}" data-detail="{did}"' if st == "fail" else ""

            table_rows.append(
                f'<tr class="{row_class}" {rid_attr} onclick="tgl(\'{did}\')"{row_extra}>'
                f'<td><span class="expand-icon {icon_state}" id="ic-{did}">▶</span></td>'
                f'<td>{title_html}</td>'
                f'<td>{_pr(c.priority)}</td>'
                f'<td>{_escape(c.module)}</td>'
                f'<td>{_st(st)}</td>'
                f'<td class="num">{dur}</td>'
                f'</tr>'
                f'<tr class="detail-row{detail_open}" id="{did}">'
                f'<td></td><td colspan="5">{detail_html}</td>'
                f'</tr>'
            )

    table_html = "\n".join(table_rows)

    # ── Assemble full HTML ──
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Boox 用例测试报告</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">

<div class="hd">
  <div class="hd-row">
    <h1>Boox 用例测试报告</h1>
    {status_pill}
  </div>
  <div class="meta">
    <span>{now}</span><span>耗时 {duration_str}</span>
    {"<span>模块：" + _escape(module_str) + "</span>" if module_str else ""}
    <span>{_escape(device_str)}</span>
  </div>
</div>

<div class="kpi-row">
  <div class="kpi g"><div class="lbl">通过</div><div class="val">{passed_n}</div><div class="sub">共 {total} 条用例</div></div>
  <div class="kpi r"><div class="lbl">失败</div><div class="val">{failed_n}</div><div class="sub">需立即处理</div></div>
  <div class="kpi o"><div class="lbl">跳过</div><div class="val">{skipped_n}</div><div class="sub">条件不满足</div></div>
  <div class="kpi b"><div class="lbl">通过率</div><div class="val">{pass_rate:.1f}%</div><div class="sub">目标 ≥ 90%</div></div>
</div>

<div class="sec">
  <div class="sec-hd" onclick="this.parentElement.classList.toggle('open')">
    <span class="dot p"></span> 设备信息 <span class="sec-arrow">▾</span>
  </div>
  <div class="sec-bd">
    <div class="dev-row">
      {_build_device_chips(device_info)}
    </div>
  </div>
</div>

{failed_section}

<div class="sec open" id="caseSec">
  <div class="sec-hd" onclick="this.parentElement.classList.toggle('open')">
    <span class="dot p"></span> 全部用例 <span class="cnt p" id="caseCnt">{total}</span>
    <span class="sec-arrow">▾</span>
  </div>
  <div class="sec-bd" style="padding:0">
    <div class="fbar">
      <button class="fbtn act" onclick="fil('all',this)">全部</button>
      <button class="fbtn fr" onclick="fil('fail',this)">失败</button>
      <button class="fbtn" onclick="fil('skip',this)">跳过</button>
      <button class="fbtn" onclick="fil('pass',this)">通过</button>
      <input class="fsearch" type="text" placeholder="搜索用例..." oninput="fil('search')" id="fs">
    </div>
    <div class="tbl-scroll" id="ts">
    <table class="tbl">
      <thead><tr><th style="width:22px"></th><th>用例名称</th><th style="width:56px">优先级</th><th style="width:80px">模块</th><th style="width:52px">状态</th><th style="width:48px" class="num">耗时</th></tr></thead>
      <tbody>
      {table_html}
      </tbody>
    </table>
    </div>
  </div>
</div>

<div class="ft">Boox Automation · 自动生成于 {now}</div>

</div>

<script>
var TOTAL = {total};
{_JS}
// fail card click bindings
(function(){{
  var cards = document.querySelectorAll('.fail-card');
  for (var i = 0; i < cards.length; i++) {{
    var cid = cards[i].id;
    var rid = 'rf' + i;
    cards[i].onclick = function(){{ goFail(this.id.replace('fc','rf')); }};
  }}
}})();
</script>

</body>
</html>"""
    return html


def save_report(html: str, output_dir: Path) -> Path:
    """保存 HTML 报告到文件，返回文件路径。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"report_{ts}.html"
    path.write_text(html, encoding="utf-8")
    logger.info(f"HTML 报告已保存: {path}")
    return path
