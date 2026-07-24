"""
集中清理项目运行期产物：按文件修改时间 (mtime) 超期清理。

12h TTL（运行产物）: screenshots, image_diff, reports, page_xml, logs, tmp
24h TTL（缓存数据）: cache, baselines

调用方式：
- pytest 会话结束时自动调用 cleanup_artifacts()
- 手动：python -m boox_automation.core.cleanup
"""

from __future__ import annotations
import logging
import shutil
import sys
import time
from pathlib import Path

from boox_automation.core.paths import (
    SCREENSHOTS_ROOT,
    IMAGE_DIFF_ROOT,
    REPORTS_ROOT,
    PAGE_XML_ROOT,
    CACHE_ROOT,
    BASELINES_ROOT,
    LOGS_ROOT,
    TMP_ROOT,
    DOCS_ROOT,
    CLEANUP_TTL_12H,
    CLEANUP_TTL_24H,
)

logger = logging.getLogger(__name__)

# baselines 下的元数据文件（不超期清理，始终保留）
_BASELINE_META_FILES = {"entries.json", "index.json"}


def _get_cleanup_targets() -> list[tuple[Path, int, str]]:
    """返回清理目标列表，TTL 优先从 config.yaml 读取。"""
    from boox_automation.core.config import cleanup_ttl_12h, cleanup_ttl_24h
    ttl_12h = cleanup_ttl_12h()
    ttl_24h = cleanup_ttl_24h()
    return [
        (SCREENSHOTS_ROOT, ttl_12h, "screenshots"),
        (IMAGE_DIFF_ROOT, ttl_12h, "image_diff"),
        (REPORTS_ROOT, ttl_12h, "reports"),
        (PAGE_XML_ROOT, ttl_12h, "page_xml"),
        (LOGS_ROOT, ttl_12h, "logs"),
        (DOCS_ROOT, ttl_12h, "docs"),
        (CACHE_ROOT, ttl_24h, "cache"),
        (BASELINES_ROOT, ttl_24h, "baselines"),
    ]


def _cleanup_dir(root: Path, ttl_seconds: int, dry_run: bool = False,
                 skip_files: set | None = None) -> tuple[int, int]:
    """递归删除 root 下 mtime 超过 ttl 的文件和空目录。

    Returns:
        (删除文件数, 释放字节数)
    """
    if not root.exists():
        return 0, 0

    now = time.time()
    deadline = now - ttl_seconds
    skip = skip_files or set()
    removed = 0
    freed = 0

    # 先删过期文件
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if f.name in skip:
            continue
        try:
            if f.stat().st_mtime < deadline:
                size = f.stat().st_size
                if dry_run:
                    logger.info(f"[DRY RUN] 将删除: {f}")
                else:
                    f.unlink(missing_ok=True)
                removed += 1
                freed += size
        except OSError:
            pass

    # 清理空目录（自底向上）
    if not dry_run:
        for d in sorted(root.rglob("*"), key=lambda p: len(str(p)), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                try:
                    d.rmdir()
                except OSError:
                    pass

    return removed, freed


def _format_size(num: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    n = float(num)
    for unit in units:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def cleanup_artifacts(dry_run: bool = False) -> dict:
    """按 TTL 清理各分类目录；返回每类统计。"""
    summary: dict = {}

    for root, ttl, name in _get_cleanup_targets():
        skip = _BASELINE_META_FILES if root == BASELINES_ROOT else None
        removed, freed = _cleanup_dir(root, ttl, dry_run=dry_run, skip_files=skip)
        if removed:
            tag = "[DRY RUN]" if dry_run else "[artifacts]"
            logger.info(f"{tag} 清理 {name}：删除 {removed} 项，释放 {_format_size(freed)}")
        summary[name] = {"removed": removed, "freed_bytes": freed}

    # tmp 目录特殊处理：全清（不判断 mtime）
    if TMP_ROOT.exists():
        freed = sum(
            f.stat().st_size for f in TMP_ROOT.rglob("*") if f.is_file()
        )
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
