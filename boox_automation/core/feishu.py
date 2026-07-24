"""飞书 API 客户端：token 管理 + 电子表格读取 + 本地缓存。

通过 requests 调用飞书 Open API，跨平台兼容，无需外部命令行依赖。
离线时自动使用本地缓存，避免因网络问题阻塞测试。
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from boox_automation.core.config import (
    feishu_app_id, feishu_app_secret,
    feishu_curl_timeout, feishu_token_cache_ttl,
    cache_max_age,
)

logger = logging.getLogger(__name__)

_TOKEN_CACHE: dict[str, str] = {}
_TOKEN_EXPIRY: dict[str, float] = {}


def _feishu_request(method: str, url: str, data: dict | None = None,
                    bearer_token: str | None = None) -> dict:
    timeout = feishu_curl_timeout()
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    try:
        resp = requests.request(
            method, url,
            headers=headers,
            json=data,
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.ConnectionError as e:
        raise RuntimeError(f"无法连接飞书 API: {e}")
    except requests.Timeout as e:
        raise RuntimeError(f"飞书 API 请求超时: {e}")
    except requests.RequestException as e:
        raise RuntimeError(f"飞书 API 请求失败: {e}")

    body = resp.json()
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

    body = _feishu_request(
        "POST",
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data={"app_id": app_id, "app_secret": app_secret},
    )
    token = body["tenant_access_token"]
    _TOKEN_CACHE[app_id] = token
    _TOKEN_EXPIRY[app_id] = now + feishu_token_cache_ttl()
    return token


_SHEET_META_CACHE: dict[str, list[dict]] = {}


def _get_sheet_meta(spreadsheet_token: str) -> list[dict]:
    """获取表格的 sheet 元数据列表（同 token 首次查询后缓存）。

    Returns: [{"title": str, "sheet_id": str}, ...]
    """
    if spreadsheet_token in _SHEET_META_CACHE:
        return _SHEET_META_CACHE[spreadsheet_token]

    if not spreadsheet_token:
        raise RuntimeError("飞书 spreadsheet_token 未配置")

    app_token = _get_tenant_token()
    url = (
        f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/"
        f"{spreadsheet_token}/sheets/query"
    )
    body = _feishu_request("GET", url, bearer_token=app_token)
    sheets = body.get("data", {}).get("sheets", [])
    meta = [{"title": s["title"], "sheet_id": s["sheet_id"]} for s in sheets]
    _SHEET_META_CACHE[spreadsheet_token] = meta
    return meta


def list_sheet_names(spreadsheet_token: str) -> list[str]:
    """列出电子表格中所有 sheet 名称。"""
    return [s["title"] for s in _get_sheet_meta(spreadsheet_token)]


def read_sheet_by_name(
    sheet_name: str, spreadsheet_token: str
) -> list[list[str]]:
    """按名称读取 sheet 的全部数据，返回二维数组（首行为表头）。

    Feishu sheets API 返回的每行可能不等长，缺失的单元格补空字符串。
    """
    if not spreadsheet_token:
        raise RuntimeError("飞书 spreadsheet_token 未配置")

    # 1. 从缓存获取 sheet_id
    sheets = _get_sheet_meta(spreadsheet_token)
    sheet_id = None
    for s in sheets:
        if s["title"] == sheet_name:
            sheet_id = s["sheet_id"]
            break
    if not sheet_id:
        raise RuntimeError(
            f"Sheet '{sheet_name}' 不存在，可选: "
            f"{[s['title'] for s in sheets]}"
        )

    app_token = _get_tenant_token()

    # 2. 读取全部值（ToString 确保富文本单元格返回纯文本）
    read_url = (
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/"
        f"{spreadsheet_token}/values/{sheet_id}"
        f"?valueRenderOption=ToString"
    )
    read_body = _feishu_request("GET", read_url, bearer_token=app_token)
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

    logger.debug(f"已从飞书读取工作表「{sheet_name}」: {len(rows)} 行")
    return rows


def read_sheet_with_media(
    sheet_name: str, spreadsheet_token: str
) -> list[list]:
    """读取 sheet 时保留嵌入图片 fileToken（不展平为字符串）。

    专用于基准图表的加载：图片所在单元格会返回带 fileToken 的 dict/list 结构，
    交由 extract_file_tokens() 解析；普通文本单元格仍返回字符串。
    """
    if not spreadsheet_token:
        raise RuntimeError("飞书 spreadsheet_token 未配置")

    sheets = _get_sheet_meta(spreadsheet_token)
    sheet_id = None
    for s in sheets:
        if s["title"] == sheet_name:
            sheet_id = s["sheet_id"]
            break
    if not sheet_id:
        raise RuntimeError(
            f"Sheet '{sheet_name}' 不存在，可选: "
            f"{[s['title'] for s in sheets]}"
        )

    app_token = _get_tenant_token()
    read_url = (
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/"
        f"{spreadsheet_token}/values/{sheet_id}"
        f"?valueRenderOption=FormattedValue"
    )
    read_body = _feishu_request("GET", read_url, bearer_token=app_token)
    rows = read_body.get("data", {}).get("valueRange", {}).get("values", [])

    if rows:
        max_cols = max(len(r) for r in rows)
        for r in rows:
            r.extend([""] * (max_cols - len(r)))

    logger.debug(f"已从飞书读取工作表「{sheet_name}」(含媒体): {len(rows)} 行")
    return rows


def extract_file_tokens(cell_value) -> list[str]:
    """递归提取单元格中所有 fileToken 字段。

    适配飞书 FormattedValue 返回结构：dict/list/JSON 字符串均支持。
    """
    tokens: list[str] = []
    if isinstance(cell_value, dict):
        ft = cell_value.get("fileToken")
        if ft:
            tokens.append(str(ft))
        for v in cell_value.values():
            tokens.extend(extract_file_tokens(v))
    elif isinstance(cell_value, list):
        for item in cell_value:
            tokens.extend(extract_file_tokens(item))
    elif isinstance(cell_value, str):
        s = cell_value.strip()
        if s.startswith("{") or s.startswith("["):
            try:
                obj = json.loads(s)
                tokens.extend(extract_file_tokens(obj))
            except (json.JSONDecodeError, ValueError):
                pass
    return tokens


_MEDIA_EXT_MAP = {
    "image/jpeg": ".jpg", "image/jpg": ".jpg",
    "image/png": ".png", "image/gif": ".gif",
    "image/webp": ".webp", "image/bmp": ".bmp",
}


def download_media(file_token: str, save_dir: str, filename: str) -> str:
    """通过 fileToken 下载飞书素材到本地，返回完整路径。

    Args:
        file_token: 飞书素材 token
        save_dir: 保存目录（自动创建）
        filename: 文件名（不含扩展名），扩展名按 Content-Type 自动判断
    """
    if not file_token:
        raise RuntimeError("download_media: file_token 为空")

    app_token = _get_tenant_token()
    url = (
        "https://open.feishu.cn/open-apis/drive/v1/medias/"
        f"batch_get_tmp_download_url?file_tokens={file_token}"
    )
    body = _feishu_request("GET", url, bearer_token=app_token)
    tmp_urls = body.get("data", {}).get("tmp_download_urls", [])
    if not tmp_urls:
        raise RuntimeError(f"download_media: 未获取到 {file_token} 的临时下载链接")
    tmp_url = tmp_urls[0].get("tmp_download_url")
    if not tmp_url:
        raise RuntimeError(f"download_media: 临时下载链接为空 token={file_token}")

    try:
        resp = requests.get(tmp_url, stream=True, timeout=feishu_curl_timeout() * 2)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"download_media: 下载失败 token={file_token}: {e}")

    content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
    ext = _MEDIA_EXT_MAP.get(content_type, ".png")
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)
    full = save_path / f"{filename}{ext}"
    with open(full, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    logger.debug(f"飞书素材已下载: {full}")
    return str(full)


# ---- 连通性检查 ----

_FEISHU_REACHABLE_CACHE = {"value": None, "timestamp": 0}
_REACHABLE_TTL = 60  # 探测结果缓存 60 秒


def check_feishu_reachable(timeout: int = 3) -> bool:
    """快速检查飞书 API 是否可达（60s TTL 缓存）。"""
    now = time.time()
    if _FEISHU_REACHABLE_CACHE["value"] is not None:
        if now - _FEISHU_REACHABLE_CACHE["timestamp"] < _REACHABLE_TTL:
            return _FEISHU_REACHABLE_CACHE["value"]

    try:
        requests.head("https://open.feishu.cn", timeout=timeout)
        _FEISHU_REACHABLE_CACHE["value"] = True
    except Exception:
        _FEISHU_REACHABLE_CACHE["value"] = False
    _FEISHU_REACHABLE_CACHE["timestamp"] = now
    return _FEISHU_REACHABLE_CACHE["value"]


# ---- 本地缓存 ----

def _cache_path(cache_name: str) -> Path:
    """获取缓存文件完整路径（统一落在 artifacts/cache/）。"""
    from boox_automation.core.paths import CACHE_ROOT
    _maybe_migrate_old_cache(CACHE_ROOT)
    return CACHE_ROOT / f"{cache_name}.json"


def _maybe_migrate_old_cache(target: Path) -> None:
    """旧缓存目录 data/.cache/ 若存在，迁移至 artifacts/cache/。"""
    old_cache = Path(__file__).parent.parent / "data" / ".cache"
    if not old_cache.exists() or target.exists():
        return
    import shutil
    logger.info(f"迁移旧缓存: {old_cache} → {target}")
    try:
        shutil.move(str(old_cache), str(target))
    except Exception as e:
        logger.warning(f"旧缓存迁移失败: {e}")


def save_cache(data: dict, cache_name: str) -> None:
    """将数据以 JSON 格式写入本地缓存。"""
    path = _cache_path(cache_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "source": "feishu",
        "data": data,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.debug(f"缓存已更新: {path}")


def load_cache(cache_name: str, max_age_seconds: int | None = None) -> dict | None:
    """读取未过期的本地缓存，过期或无文件返回 None。"""
    if max_age_seconds is None:
        max_age_seconds = cache_max_age()

    path = _cache_path(cache_name)
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
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




def _fmt_age(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}秒前"
    if seconds < 3600:
        return f"{int(seconds / 60)}分钟前"
    if seconds < 86400:
        return f"{int(seconds / 3600)}小时前"
    return f"{int(seconds / 86400)}天前"


# ---- 消息与文件发送 ----

def send_card_message(chat_id: str, card: dict) -> dict:
    """向飞书群聊发送交互式卡片消息。

    Args:
        chat_id: 群聊 ID
        card: 飞书卡片 JSON（dict 形式，不含 config/header 顶层键时自动补）
    """
    app_token = _get_tenant_token()
    url = (
        "https://open.feishu.cn/open-apis/im/v1/messages"
        "?receive_id_type=chat_id"
    )
    body = {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False),
    }
    return _feishu_request("POST", url, data=body, bearer_token=app_token)


def upload_file_to_im(file_path: str, file_type: str = "stream") -> str:
    """上传文件到飞书 IM，返回 file_key。

    Args:
        file_path: 本地文件路径
        file_type: 文件类型（stream/opus/mp4/pdf/doc等），默认 stream
    """
    app_token = _get_tenant_token()
    url = "https://open.feishu.cn/open-apis/im/v1/files"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    file_name = os.path.basename(file_path)

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {app_token}"},
            files={"file": (file_name, file_bytes)},
            data={
                "file_type": file_type,
                "file_name": file_name,
            },
            timeout=feishu_curl_timeout(),
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"飞书文件上传失败: HTTP {resp.status_code}\n"
                f"  响应: {resp.text[:500]}"
            )
    except requests.RequestException as e:
        raise RuntimeError(f"飞书文件上传失败: {e}")

    body = resp.json()
    if body.get("code") != 0:
        raise RuntimeError(
            f"飞书文件上传返回错误: code={body.get('code')} msg={body.get('msg')}"
        )
    return body["data"]["file_key"]


def send_file_message(chat_id: str, file_key: str) -> dict:
    """向飞书群聊发送文件消息（需先通过 upload_file_to_im 上传）。

    Args:
        chat_id: 群聊 ID
        file_key: 上传文件返回的 file_key
    """
    app_token = _get_tenant_token()
    url = (
        "https://open.feishu.cn/open-apis/im/v1/messages"
        "?receive_id_type=chat_id"
    )
    body = {
        "receive_id": chat_id,
        "msg_type": "file",
        "content": json.dumps({"file_key": file_key}),
    }
    return _feishu_request("POST", url, data=body, bearer_token=app_token)
