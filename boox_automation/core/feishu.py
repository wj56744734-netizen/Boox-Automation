"""飞书 API 客户端：token 管理 + 电子表格读取 + 本地缓存。

通过 curl 调用飞书 Open API，适配存在自签名证书的企业网络环境。
离线时自动使用本地缓存，避免因网络问题阻塞测试。
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from boox_automation.core.config import (
    feishu_app_id, feishu_app_secret,
    feishu_curl_timeout, feishu_token_cache_ttl,
    cache_max_age, cache_dir,
)

logger = logging.getLogger(__name__)

_TOKEN_CACHE: dict[str, str] = {}
_TOKEN_EXPIRY: dict[str, float] = {}


def _curl_json(method: str, url: str, data: dict | None = None,
               bearer_token: str | None = None) -> dict:
    timeout = feishu_curl_timeout()
    cmd = [
        "curl", "-s", "--max-time", str(timeout),
        "-H", "Content-Type: application/json; charset=utf-8",
        "-X", method,
    ]
    if bearer_token:
        cmd.extend(["-H", f"Authorization: Bearer {bearer_token}"])
    if data:
        cmd.extend(["-d", json.dumps(data, ensure_ascii=False)])
    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except FileNotFoundError:
        raise RuntimeError("curl 命令不可用，请确认已安装 curl 并加入 PATH")
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"curl 请求失败: {stderr}")
    stdout = (result.stdout or "").strip()
    if not stdout:
        raise RuntimeError(f"curl 返回空响应: {url}")
    body = json.loads(stdout)
    if body.get("code") != 0:
        raise RuntimeError(
            f"飞书 API 返回错误: {url}\n"
            f"  code={body.get('code')} msg={body.get('msg')}"
        )
    return body


def _get_tenant_token() -> str:
    """获取 tenant_access_token，自动缓存。"""
    app_id = feishu_app_id()
    app_secret = feishu_app_secret()
    now = time.time()
    if app_id in _TOKEN_CACHE and _TOKEN_EXPIRY.get(app_id, 0) > now:
        return _TOKEN_CACHE[app_id]

    body = _curl_json(
        "POST",
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data={"app_id": app_id, "app_secret": app_secret},
    )
    token = body["tenant_access_token"]
    _TOKEN_CACHE[app_id] = token
    _TOKEN_EXPIRY[app_id] = now + feishu_token_cache_ttl()
    return token


def list_sheet_names(spreadsheet_token: str) -> list[str]:
    """列出电子表格中所有 sheet 名称。"""
    if not spreadsheet_token:
        raise RuntimeError("飞书 spreadsheet_token 未配置")

    app_token = _get_tenant_token()
    url = (
        f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/"
        f"{spreadsheet_token}/sheets/query"
    )
    body = _curl_json("GET", url, bearer_token=app_token)
    return [s["title"] for s in body.get("data", {}).get("sheets", [])]


def read_sheet_by_name(
    sheet_name: str, spreadsheet_token: str
) -> list[list[str]]:
    """按名称读取 sheet 的全部数据，返回二维数组（首行为表头）。

    Feishu sheets API 返回的每行可能不等长，缺失的单元格补空字符串。
    """
    if not spreadsheet_token:
        raise RuntimeError("飞书 spreadsheet_token 未配置")

    app_token = _get_tenant_token()

    # 1. 获取 sheet_id
    list_url = (
        f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/"
        f"{spreadsheet_token}/sheets/query"
    )
    list_body = _curl_json("GET", list_url, bearer_token=app_token)
    sheets = list_body.get("data", {}).get("sheets", [])
    sheet_id = None
    for s in sheets:
        if s.get("title") == sheet_name:
            sheet_id = s["sheet_id"]
            break
    if not sheet_id:
        raise RuntimeError(
            f"Sheet '{sheet_name}' 不存在，可选: "
            f"{[s['title'] for s in sheets]}"
        )

    # 2. 读取全部值（ToString 确保富文本单元格返回纯文本）
    read_url = (
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/"
        f"{spreadsheet_token}/values/{sheet_id}"
        f"?valueRenderOption=ToString"
    )
    read_body = _curl_json("GET", read_url, bearer_token=app_token)
    rows = read_body.get("data", {}).get("valueRange", {}).get("values", [])

    if rows:
        max_cols = max(len(r) for r in rows)
        for r in rows:
            r.extend([""] * (max_cols - len(r)))
            # 兜底：ToString 对某些富文本可能不生效，手动展平 segment 数组
            for i, cell in enumerate(r):
                if isinstance(cell, list):
                    r[i] = "".join(
                        seg.get("text", "") if isinstance(seg, dict) else str(seg)
                        for seg in cell
                    )

    logger.debug(f"已从飞书读取 sheet '{sheet_name}': {len(rows)} 行")
    return rows


def write_sheet_values(
    spreadsheet_token: str,
    sheet_id: str,
    start_row: int,
    start_col: int,
    values: list[list[str]],
) -> dict:
    """向飞书电子表格写入数据。

    Args:
        spreadsheet_token: 表格 token
        sheet_id: sheet ID (不是 sheet 名)
        start_row: 起始行 (1-based)
        start_col: 起始列 (1-based)
        values: 二维数组，每行一个 list
    """
    if not spreadsheet_token:
        raise RuntimeError("飞书 spreadsheet_token 未配置")

    app_token = _get_tenant_token()
    write_url = (
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/"
        f"{spreadsheet_token}/values"
    )

    # 计算结束位置
    end_row = start_row + len(values) - 1
    max_cols = max((len(r) for r in values), default=1)
    end_col = start_col + max_cols - 1
    col_letter_start = _col_to_letter(start_col)
    col_letter_end = _col_to_letter(end_col)
    range_str = f"{sheet_id}!{col_letter_start}{start_row}:{col_letter_end}{end_row}"

    body = {
        "valueRange": {
            "range": range_str,
            "values": values,
        }
    }
    return _curl_json("PUT", write_url, data=body, bearer_token=app_token)


def _col_to_letter(n: int) -> str:
    """列号转字母 (1->A, 27->AA)。"""
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def get_sheet_id(spreadsheet_token: str, sheet_name: str) -> str:
    """按名称获取 sheet_id。"""
    list_url = (
        f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/"
        f"{spreadsheet_token}/sheets/query"
    )
    app_token = _get_tenant_token()
    body = _curl_json("GET", list_url, bearer_token=app_token)
    sheets = body.get("data", {}).get("sheets", [])
    for s in sheets:
        if s.get("title") == sheet_name:
            return s["sheet_id"]
    raise RuntimeError(
        f"Sheet '{sheet_name}' 不存在，可选: "
        f"{[s['title'] for s in sheets]}"
    )


def use_local_excel() -> bool:
    """检查是否使用本地 Excel 文件（离线调试）。"""
    return os.environ.get("USE_LOCAL_EXCEL", "") in ("1", "true", "yes")


# ---- 连通性检查 ----

def check_feishu_reachable(timeout: int = 3) -> bool:
    """快速检查飞书 API 是否可达（DNS + TCP 连通）。"""
    try:
        subprocess.run(
            ["curl", "-s", "--max-time", str(timeout),
             "https://open.feishu.cn"],
            capture_output=True, text=True, timeout=timeout + 2,
        )
        return True
    except Exception:
        return False


# ---- 本地缓存 ----

def _cache_path(cache_name: str) -> Path:
    """获取缓存文件完整路径。"""
    base = Path(__file__).parent.parent  # core/ → boox_automation/
    return base / cache_dir() / f"{cache_name}.json"


def save_cache(data: dict, cache_name: str) -> None:
    """将数据以 JSON 格式写入本地缓存。"""
    path = _cache_path(cache_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "source": "feishu",
        "data": data,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    logger.debug(f"缓存已更新: {path}")


def load_cache(cache_name: str, max_age_seconds: int | None = None) -> dict | None:
    """读取未过期的本地缓存，过期或无文件返回 None。"""
    if max_age_seconds is None:
        max_age_seconds = cache_max_age()

    path = _cache_path(cache_name)
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text())
        cached_at_str = payload.get("cached_at", "")
        if cached_at_str:
            cached_at = datetime.fromisoformat(cached_at_str)
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age > max_age_seconds:
                logger.info(f"缓存 {cache_name} 已过期（{_fmt_age(age)}）")
                return None
        return payload.get("data")
    except (json.JSONDecodeError, KeyError, ValueError):
        logger.warning(f"缓存 {cache_name} 损坏，忽略")
        return None


def get_cache_age(cache_name: str) -> str:
    """返回缓存年龄的描述文本（如'2小时前'），无缓存返回空字符串。"""
    path = _cache_path(cache_name)
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text())
        cached_at_str = payload.get("cached_at", "")
        if cached_at_str:
            cached_at = datetime.fromisoformat(cached_at_str)
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            return _fmt_age(age)
    except Exception:
        pass
    return ""


def _fmt_age(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}秒前"
    if seconds < 3600:
        return f"{int(seconds / 60)}分钟前"
    if seconds < 86400:
        return f"{int(seconds / 3600)}小时前"
    return f"{int(seconds / 86400)}天前"
