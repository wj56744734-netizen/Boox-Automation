"""
集中管理项目运行期产生的临时/产物文件路径。

所有产物默认写到 boox_automation/artifacts/ 下，可通过环境变量
NOTE_ARTIFACTS_ROOT 改写到外部目录（CI 场景常用）。

目录约定：

- artifacts/screenshots/<YYYY-MM-DD>/     失败截图等运行期截图（12h 清理）
- artifacts/image_diff/{设备}/{模块}/      截图对比产物（12h 清理）
- artifacts/reports/                       HTML 测试报告（12h 清理）
- artifacts/page_xml/<YYYY-MM-DD>/         页面 XML 导出（12h 清理）
- artifacts/cache/                         飞书数据缓存（24h 清理）
- artifacts/baselines/                     基准图缓存（24h 清理）
- artifacts/logs/                          测试日志（12h 清理）
- artifacts/tmp/                           临时文件（12h 清理）
- artifacts/docs/                          开发方案文档（12h 清理，不入库）
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"


def get_artifacts_root() -> Path:
    """返回当前产物根目录，环境变量 NOTE_ARTIFACTS_ROOT 优先。"""
    override = os.getenv("NOTE_ARTIFACTS_ROOT", "").strip()
    return Path(override).expanduser().resolve() if override else DEFAULT_ARTIFACTS_ROOT


ARTIFACTS_ROOT = get_artifacts_root()

# ── 产物目录 ──
SCREENSHOTS_ROOT = ARTIFACTS_ROOT / "screenshots"
IMAGE_DIFF_ROOT = ARTIFACTS_ROOT / "image_diff"
REPORTS_ROOT = ARTIFACTS_ROOT / "reports"
PAGE_XML_ROOT = ARTIFACTS_ROOT / "page_xml"
CACHE_ROOT = ARTIFACTS_ROOT / "cache"
BASELINES_ROOT = ARTIFACTS_ROOT / "baselines"
LOGS_ROOT = ARTIFACTS_ROOT / "logs"
TMP_ROOT = ARTIFACTS_ROOT / "tmp"
DOCS_ROOT = ARTIFACTS_ROOT / "docs"

# ── 清理 TTL（秒）──
CLEANUP_TTL_12H = 12 * 3600   # 运行产物
CLEANUP_TTL_24H = 24 * 3600   # 缓存类数据


def ensure_dir(path: Path) -> Path:
    """确保目录存在，返回 Path。"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def screenshot_dir_today() -> Path:
    """按日期分子目录，避免单目录文件膨胀。"""
    return ensure_dir(SCREENSHOTS_ROOT / datetime.now().strftime("%Y-%m-%d"))


def safe_screenshot_path(name: str) -> Path:
    """生成安全的截图文件路径（剥离非法字符 + 时间戳）。"""
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[:120]
    ts = datetime.now().strftime("%H%M%S")
    return screenshot_dir_today() / f"{ts}_{safe}.png"


__all__ = [
    "PROJECT_ROOT",
    "ARTIFACTS_ROOT",
    "SCREENSHOTS_ROOT",
    "IMAGE_DIFF_ROOT",
    "REPORTS_ROOT",
    "PAGE_XML_ROOT",
    "CACHE_ROOT",
    "BASELINES_ROOT",
    "LOGS_ROOT",
    "TMP_ROOT",
    "DOCS_ROOT",
    "CLEANUP_TTL_12H",
    "CLEANUP_TTL_24H",
    "ensure_dir",
    "screenshot_dir_today",
    "safe_screenshot_path",
]
