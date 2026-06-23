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


def test_case_sheets() -> list[str]:
    """返回要加载的用例 sheet 列表，支持环境变量逗号分隔。"""
    env = os.environ.get("NOTE_TEST_CASE_SHEETS")
    if env:
        return [s.strip() for s in env.split(",") if s.strip()]
    sheets = get("excel.test_case_sheets")
    if isinstance(sheets, list):
        return sheets
    return ["笔记"]



def feishu_report_enabled() -> bool:
    return get_bool("feishu.report.enabled", False)


def feishu_chat_id() -> str:
    return os.environ.get("FEISHU_CHAT_ID") or get_str("feishu.report.chat_id", "")


def feishu_curl_timeout() -> int:
    return get_int("feishu.curl_timeout", 15)


def feishu_token_cache_ttl() -> int:
    return get_int("feishu.token_cache_ttl", 5400)


def excel_source() -> str:
    """用例和元素的加载方式: cloud | cache | local。
    USE_LOCAL_EXCEL=1 强制 local，NOTE_EXCEL_SOURCE 环境变量次之。
    """
    if os.environ.get("USE_LOCAL_EXCEL", "") in ("1", "true", "yes"):
        return "local"
    env = os.environ.get("NOTE_EXCEL_SOURCE", "")
    if env and env.strip().lower() in ("cloud", "cache", "local"):
        return env.strip().lower()
    val = get_str("excel.source", "cloud")
    if val not in ("cloud", "cache", "local"):
        raise ValueError(
            f"config.yaml excel.source 无效值: '{val}'，"
            f"有效值: cloud | cache | local"
        )
    return val


def case_path() -> str:
    """本地用例文件路径（仅 excel_source=local 时生效）。
    支持相对路径（相对于项目根目录）或绝对路径。
    环境变量 NOTE_TEST_CASE_PATH 可覆盖。
    """
    env = os.environ.get("NOTE_TEST_CASE_PATH", "")
    if env:
        return _resolve_local_path(env)
    raw = get_str("excel.test_case_path", "data/test_cases.xlsx")
    return _resolve_local_path(raw)


def elements_path() -> str:
    """本地元素文件路径（仅 excel_source=local 时生效）。
    环境变量 NOTE_ELEMENTS_PATH 可覆盖。
    """
    env = os.environ.get("NOTE_ELEMENTS_PATH", "")
    if env:
        return _resolve_local_path(env)
    raw = get_str("excel.elements_path", "data/elements.xlsx")
    return _resolve_local_path(raw)


def _resolve_local_path(raw: str) -> str:
    """将相对路径转为基于项目根目录的绝对路径。"""
    p = Path(raw)
    if p.is_absolute():
        return str(p)
    return str(_resolve_config_path().parent / p)


def excel_priority_filter() -> str:
    return get_str("excel.priority_filter", "P0")


def excel_test_case_file() -> str:
    """已弃用: 请使用 case_path()。保留以兼容旧代码。"""
    return get_str("excel.test_case_path", "data/test_cases.xlsx")


def excel_elements_file() -> str:
    """已弃用: 请使用 elements_path()。保留以兼容旧代码。"""
    return get_str("excel.elements_path", "data/elements.xlsx")


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


def case_column(name: str) -> int:
    """读取用例表列索引（0-based）。name 如 title/priority/module/precondition/steps/expected/result/remark。"""
    return get_int(f"excel.columns.{name}", -1)


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


def adb_command_timeout() -> int:
    """ADB 命令执行超时（秒），用于 ADB命令 sheet 中的命令。"""
    return get_int("adb.command_timeout", 10)


def adb_cleanup_app_data_packages() -> list[str]:
    """【清理应用数据】pm clear 目标包名列表。环境变量 ADB_CLEANUP_PACKAGES 逗号分隔可覆盖。"""
    env = os.environ.get("ADB_CLEANUP_PACKAGES")
    if env:
        return [p.strip() for p in env.split(",") if p.strip()]
    pkgs = get("adb.cleanup.app_data.packages")
    if isinstance(pkgs, list):
        return [str(p) for p in pkgs if p]
    return ["com.onyx.android.note", "com.onyx.android.ksync", "com.onyx"]


def adb_cleanup_storage_paths() -> list[str]:
    """【清理存储文件】rm -rf 目标路径列表。环境变量 ADB_CLEANUP_PATHS 逗号分隔可覆盖。"""
    env = os.environ.get("ADB_CLEANUP_PATHS")
    if env:
        return [p.strip() for p in env.split(",") if p.strip()]
    paths = get("adb.cleanup.storage_files.paths")
    if isinstance(paths, list):
        return [str(p) for p in paths if p]
    return ["/sdcard/note/*"]


def coord_max_tap_retries() -> int:
    return get_int("coord.max_tap_retries", 3)


def coord_tap_retry_delay() -> float:
    return get_float("coord.tap_retry_delay", 0.5)


def coord_verify_timeout() -> int:
    return get_int("coord.verify_timeout", 5)


def timeout_default() -> int:
    return get_int("timeout.default", 5)


def timeout_xml_element_wait() -> int:
    return get_int("timeout.xml_element_wait", 5)


def timeout_app_launch() -> int:
    return get_int("timeout.app_launch", 30)


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
