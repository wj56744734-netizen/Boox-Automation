"""
集中管理项目运行期产生的临时/产物文件路径。

所有产物默认写到 boox_automation/artifacts/ 下，可通过环境变量
NOTE_ARTIFACTS_ROOT 改写到外部目录（CI 场景常用）。

目录约定：

- artifacts/screenshots/<YYYY-MM-DD>/     失败截图等运行期截图
- artifacts/logs/                         备用：测试日志
- artifacts/tmp/                          临时下载、中间文件
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

SCREENSHOTS_ROOT = ARTIFACTS_ROOT / "screenshots"
LOGS_ROOT = ARTIFACTS_ROOT / "logs"
TMP_ROOT = ARTIFACTS_ROOT / "tmp"

# 每个分类下保留多少最新批次（清理时使用）
from boox_automation.core.config import cleanup_keep_latest
DEFAULT_KEEP_LATEST = cleanup_keep_latest()


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
    "LOGS_ROOT",
    "TMP_ROOT",
    "DEFAULT_KEEP_LATEST",
    "ensure_dir",
    "screenshot_dir_today",
    "safe_screenshot_path",
]
