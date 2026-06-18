"""
集中清理项目运行期产物：保留最近 N 轮 allure / html / screenshots。

调用方式：
- pytest 会话结束时自动调用 cleanup_artifacts()
- 手动：python -m boox_automation.core.cleanup
"""

from __future__ import annotations
import logging
import shutil
import sys
from pathlib import Path

from boox_automation.core.paths import (
    ALLURE_HTML_ROOT,
    ALLURE_RESULTS_ROOT,
    DEFAULT_KEEP_LATEST,
    LOGS_ROOT,
    SCREENSHOTS_ROOT,
    TMP_ROOT,
)

logger = logging.getLogger(__name__)


def _keep_latest(parent: Path, keep: int, dry_run: bool = False) -> tuple[int, int]:
    """按 mtime 倒序保留最新 keep 个子项，返回 (删除条数, 删除字节)。"""
    if not parent.exists():
        return 0, 0
    entries = sorted(
        (p for p in parent.iterdir() if not p.name.startswith(".")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    to_delete = entries[keep:]
    if not to_delete:
        return 0, 0
    if dry_run:
        total_size = 0
        for path in to_delete:
            size = _dir_size(path) if path.is_dir() else path.stat().st_size
            total_size += size
            logger.info(f"[DRY RUN] 将删除: {path} ({_format_size(size)})")
        return len(to_delete), total_size
    removed = 0
    freed = 0
    for path in to_delete:
        try:
            size = _dir_size(path) if path.is_dir() else path.stat().st_size
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
            removed += 1
            freed += size
        except Exception as e:
            logger.warning(f"删除失败 {path}: {e}")
    return removed, freed


def _dir_size(path: Path) -> int:
    total = 0
    for sub in path.rglob("*"):
        if sub.is_file():
            try:
                total += sub.stat().st_size
            except OSError:
                pass
    return total


def _format_size(num: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    n = float(num)
    for unit in units:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def cleanup_artifacts(keep_latest: int = DEFAULT_KEEP_LATEST, dry_run: bool = False) -> dict:
    """对各分类目录按 keep_latest 策略清理；返回每类统计。"""
    targets = {
        "allure_results": ALLURE_RESULTS_ROOT,
        "allure_html": ALLURE_HTML_ROOT,
        "screenshots": SCREENSHOTS_ROOT,
        "logs": LOGS_ROOT,
    }
    summary: dict = {}
    for name, parent in targets.items():
        removed, freed = _keep_latest(parent, keep_latest, dry_run=dry_run)
        if removed:
            tag = "[DRY RUN]" if dry_run else "[artifacts]"
            logger.info(f"{tag} 清理 {name}：删除 {removed} 项，释放 {_format_size(freed)}")
        summary[name] = {"removed": removed, "freed_bytes": freed}
    # tmp 目录单独处理：全清
    if TMP_ROOT.exists():
        freed = _dir_size(TMP_ROOT)
        if dry_run:
            logger.info(f"[DRY RUN] tmp：将删除目录，释放 {_format_size(freed)}")
        else:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)
            if freed:
                logger.info(f"[artifacts] 清理 tmp：释放 {_format_size(freed)}")
        summary["tmp"] = {"removed": 1, "freed_bytes": freed}
    else:
        summary["tmp"] = {"removed": 0, "freed_bytes": 0}
    return summary


def main():
    dry_run = "--dry-run" in sys.argv
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    if dry_run:
        logger.info("[DRY RUN] 以下为模拟清理，不会实际删除文件")
    summary = cleanup_artifacts(dry_run=dry_run)
    total_removed = sum(item["removed"] for item in summary.values())
    total_freed = sum(item["freed_bytes"] for item in summary.values())
    if dry_run:
        logger.info(f"[DRY RUN] 模拟完成：将删除 {total_removed} 项，释放 {_format_size(total_freed)}")
    else:
        logger.info(f"清理完成：共删除 {total_removed} 项，释放 {_format_size(total_freed)}")


if __name__ == "__main__":
    main()
