"""配置加载器：从 config.yaml 读取，环境变量优先覆盖，模块级缓存。"""
from __future__ import annotations

import os
from pathlib import Path

import re

import yaml

_SPREADSHEET_TOKEN_RE = re.compile(r"/sheets/([A-Za-z0-9_-]{20,30})")
_BITABLE_TOKEN_RE = re.compile(r"/base/([A-Za-z0-9_-]{20,30})")


def _extract_token(raw: str) -> str:
    """从 URL 或纯 token 中提取飞书表格 token。

    支持格式:
      - https://xxx.feishu.cn/sheets/TOKEN?sheet=0  → TOKEN
      - https://xxx.feishu.cn/base/TOKEN?table=xxx   → TOKEN
      - TOKEN                                       → TOKEN (直接返回)
    """
    if not raw:
        return ""
    raw = raw.strip()
    for pattern in (_SPREADSHEET_TOKEN_RE, _BITABLE_TOKEN_RE):
        m = pattern.search(raw)
        if m:
            return m.group(1)
    # 没有 URL 特征 → 就是纯 token
    return raw

_CONFIG: dict | None = None
_CONFIG_PATH: Path | None = None


def _resolve_config_path() -> Path:
    """定位 config.yaml：从当前文件向上找到项目根目录。"""
    global _CONFIG_PATH
    if _CONFIG_PATH is None:
        _CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.yaml"
    return _CONFIG_PATH


def load() -> dict:
    """加载完整配置（模块级缓存，只读一次 yaml）。"""
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG
    path = _resolve_config_path()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            _CONFIG = yaml.safe_load(f) or {}
    else:
        _CONFIG = {}
    return _CONFIG


def get(path: str, default=None):
    """点号路径读取配置值，例: get('timeout.default') → 5。"""
    cfg = load()
    keys = path.split(".")
    val = cfg
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
            if val is None:
                return default
        else:
            return default
    return val


def get_int(path: str, default: int = 0) -> int:
    v = get(path, default)
    return int(v) if v is not None else default


def get_float(path: str, default: float = 0.0) -> float:
    v = get(path, default)
    return float(v) if v is not None else default


def get_bool(path: str, default: bool = False) -> bool:
    v = get(path, default)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes")
    return bool(v)


def get_str(path: str, default: str = "") -> str:
    v = get(path, default)
    return str(v) if v is not None else default


# ---- 便捷访问器（环境变量优先） ----

def feishu_app_id() -> str:
    return os.environ.get("FEISHU_APP_ID") or get_str("feishu.app_id")


def feishu_app_secret() -> str:
    return os.environ.get("FEISHU_APP_SECRET") or get_str("feishu.app_secret")


def feishu_test_case_token() -> str:
    return _extract_token(
        os.environ.get("FEISHU_TEST_CASE_TOKEN")
        or get_str("feishu.test_case_token")
    )


def feishu_elements_token() -> str:
    return _extract_token(
        os.environ.get("FEISHU_ELEMENTS_TOKEN")
        or get_str("feishu.elements_token")
    )


def feishu_test_case_sheets() -> list[str]:
    """返回要加载的用例 sheet 列表，支持环境变量逗号分隔。"""
    env = os.environ.get("FEISHU_TEST_CASE_SHEETS")
    if env:
        return [s.strip() for s in env.split(",") if s.strip()]
    sheets = get("feishu.test_case_sheets")
    if isinstance(sheets, list):
        return sheets
    # 兼容旧配置 test_case_sheet（单值）
    old = get_str("feishu.test_case_sheet")
    return [old] if old else ["笔记"]


def feishu_element_sheet_prefix() -> str:
    return (os.environ.get("FEISHU_ELEMENT_SHEET_PREFIX")
            or get_str("feishu.element_sheet_prefix", "元素"))


def feishu_curl_timeout() -> int:
    return get_int("feishu.curl_timeout", 15)


def feishu_token_cache_ttl() -> int:
    return get_int("feishu.token_cache_ttl", 5400)


def excel_test_case_sheet() -> str:
    return get_str("excel.test_case_sheet", "笔记")


def excel_priority_filter() -> str:
    return get_str("excel.priority_filter", "P0")


def excel_test_case_file() -> str:
    return get_str("excel.test_case_file", "test_cases.xlsx")


def excel_elements_file() -> str:
    return get_str("excel.elements_file", "elements.xlsx")


def test_modules() -> list[str]:
    """返回要筛选的模块列表，环境变量 NOTE_TEST_MODULES 优先。
    空列表 = 不筛选（全跑）。
    """
    env = os.environ.get("NOTE_TEST_MODULES")
    if env:
        return [m.strip() for m in env.split(",") if m.strip()]
    val = get("excel.test_modules")
    if isinstance(val, list):
        return [str(m).strip() for m in val if str(m).strip()]
    if isinstance(val, str) and val.strip():
        return [m.strip() for m in val.split(",") if m.strip()]
    return []


def excel_result_column() -> int:
    return get_int("excel.result_column", 12)


def excel_remark_column() -> int:
    return get_int("excel.remark_column", 13)


def appium_host() -> str:
    return os.environ.get("APPIUM_HOST") or get_str("appium.host", "127.0.0.1")


def appium_port() -> int:
    port = os.environ.get("APPIUM_PORT")
    if port:
        return int(port)
    return get_int("appium.port", 4723)


def appium_startup_timeout() -> int:
    return get_int("appium.startup_timeout", 15)


def appium_capabilities() -> dict:
    return get("appium.capabilities", {})


def adb_device_ready_retries() -> int:
    return get_int("adb.device_ready_retries", 5)


def adb_device_ready_delay() -> int:
    return get_int("adb.device_ready_delay", 2)


def adb_command_retries() -> int:
    return get_int("adb.command_retries", 3)


def adb_command_delay() -> int:
    return get_int("adb.command_delay", 2)


def timeout_default() -> int:
    return get_int("timeout.default", 5)



def timeout_long_press() -> int:
    return get_int("timeout.long_press", 2000)


def timeout_swipe() -> int:
    return get_int("timeout.swipe", 300)


def timeout_keyboard_hide() -> int:
    return get_int("timeout.keyboard_hide", 1)


def timeout_app_launch() -> int:
    return get_int("timeout.app_launch", 30)


def timeout_import_duration() -> int:
    return get_int("timeout.import_duration", 180)


def retry_max_attempts() -> int:
    return get_int("retry.max_attempts", 3)


def retry_delay() -> float:
    return get_float("retry.delay", 1.5)


def retry_element_click() -> int:
    return get_int("retry.element_click", 2)


def retry_stale_element_delay() -> float:
    return get_float("retry.stale_element_delay", 0.5)


def logcat_capture_timeout() -> int:
    return get_int("logcat.capture_timeout", 80)


def cleanup_keep_latest() -> int:
    return int(os.environ.get("NOTE_ARTIFACTS_KEEP_LATEST",
           str(get_int("cleanup.keep_latest", 5))))


def shape_data_path() -> str:
    return get_str("paths.shape_data", "")


def driver_failure_threshold() -> int:
    return get_int("driver.failure_threshold", 3)


def screenshot_enabled() -> bool:
    return get_bool("screenshot.enabled", True)


def cache_max_age() -> int:
    return get_int("cache.max_age_seconds", 86400)


def cache_dir() -> str:
    return get_str("cache.dir", "data/.cache")
