"""基准图存储与加载：从飞书基准图电子表格读取并下载本地。"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 基准图表列结构（9 列）：A屏幕尺寸 | B屏幕DPI | C屏幕颜色 | D设备类型 | E屏幕方向 | F模块 | G场景 | H基准图 | I备注
_BASELINE_COL_SIZE = 0
_BASELINE_COL_DPI = 1
_BASELINE_COL_COLOUR = 2
_BASELINE_COL_DEVICE_TYPE = 3
_BASELINE_COL_ORIENTATION = 4
_BASELINE_COL_MODULE = 5
_BASELINE_COL_SCENE = 6
_BASELINE_COL_IMAGE = 7
_BASELINE_COL_REMARK = 8

_HEADER_KEYWORDS = {"屏幕尺寸", "屏幕DPI", "屏幕颜色", "设备类型", "屏幕方向", "模块", "场景", "基准图"}


def _find_header_row(rows: list) -> int:
    from boox_automation.engine.elements import _find_header_row as _find_hdr
    return _find_hdr(rows, default=0, keywords=_HEADER_KEYWORDS)


def _norm(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _norm_dpi(v) -> str:
    s = _norm(v)
    if not s:
        return ""
    try:
        return str(int(float(s)))
    except (ValueError, TypeError):
        return s


_BASELINE_INSTANCE: Optional["BaselineStore"] = None


class BaselineStore:
    """基准图查表 + 本地缓存管理（单例）。

    数据结构: {(size, dpi, colour, device_type, orientation, module, scene): {"file_token", "row", "sheet"}}
    缓存目录: boox_automation/artifacts/baselines/
    缓存命名: {size}_{dpi}_{colour}_{device_type}_{orientation}/{module}/{scene}.{ext}
    """

    def __init__(self):
        self._entries: dict = {}
        self._index_path: Optional[Path] = None
        self._cache_root: Optional[Path] = None
        self._loaded = False
        self._lock = threading.Lock()

    @classmethod
    def instance(cls) -> "BaselineStore":
        global _BASELINE_INSTANCE
        if _BASELINE_INSTANCE is None:
            _BASELINE_INSTANCE = cls()
        return _BASELINE_INSTANCE

    # ---- 缓存目录 ----

    def _resolve_cache_root(self) -> Path:
        if self._cache_root is not None:
            return self._cache_root
        from boox_automation.core.paths import BASELINES_ROOT
        self._cache_root = BASELINES_ROOT
        self._cache_root.mkdir(parents=True, exist_ok=True)
        self._index_path = self._cache_root / "index.json"
        return self._cache_root

    def _load_index(self) -> dict:
        self._resolve_cache_root()
        if not self._index_path or not self._index_path.exists():
            return {}
        try:
            return json.loads(self._index_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_index(self, idx: dict) -> None:
        self._resolve_cache_root()
        assert self._index_path is not None
        self._index_path.write_text(
            json.dumps(idx, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---- 加载入口 ----

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._load()
            self._loaded = True

    def _load(self) -> None:
        from boox_automation.core.config import excel_source, feishu_baseline_token
        from boox_automation.core.feishu import check_feishu_reachable

        if not feishu_baseline_token():
            logger.warning(
                "基准图加载: feishu.baseline_token 未配置，"
                "「断言截图」将无可用基准图。请在 config.yaml 中配置 feishu.baseline_token"
            )
            return

        source = excel_source()
        if source == "local":
            logger.info("基准图加载: 仅支持云端/缓存，local 模式直接读取本地缓存")
            if not self._load_from_cache():
                logger.warning(
                    "基准图加载失败: local 模式下无可用缓存。"
                    "请先以 cloud 模式运行一次生成缓存"
                )
            return

        if source == "cache":
            logger.info("基准图加载: 本地缓存")
            if not self._load_from_cache():
                logger.warning(
                    "基准图加载失败: excel.source=cache，但无可用缓存。"
                    "请先以 cloud 模式运行一次生成缓存"
                )
            return

        if source == "cloud":
            logger.info("基准图加载: 飞书云端")
            if not check_feishu_reachable():
                logger.warning(
                    "基准图加载: 飞书 API 不可达，回退本地缓存"
                )
                self._load_from_cache()
                return
            try:
                self._load_from_cloud()
                self._save_to_cache()
                logger.info(f"基准图加载完成: 共 {len(self._entries)} 条")
            except Exception as e:
                logger.warning(
                    f"基准图加载: 云端加载异常({e})，回退本地缓存"
                )
                self._load_from_cache()
            return

    def _load_from_cloud(self) -> None:
        from boox_automation.core.feishu import (
            list_sheet_names, read_sheet_with_media, extract_file_tokens,
        )
        from boox_automation.core.config import feishu_baseline_token

        token = feishu_baseline_token()
        sheets = list_sheet_names(token)
        for sheet_name in sheets:
            rows = read_sheet_with_media(sheet_name, token)
            if not rows:
                continue
            self._parse_rows(rows, sheet_name)

    def _parse_rows(self, rows: list, sheet_name: str) -> None:
        if not rows or len(rows) < 2:
            return
        from boox_automation.core.feishu import extract_file_tokens

        h_idx = _find_header_row(rows)
        for row_idx_0, row in enumerate(rows[h_idx + 1:]):
            if not row:
                continue
            sheet_row = row_idx_0 + h_idx + 2

            def _cell(i: int):
                return row[i] if i < len(row) else ""

            size = _norm(_cell(_BASELINE_COL_SIZE))
            dpi = _norm_dpi(_cell(_BASELINE_COL_DPI))
            colour = _norm(_cell(_BASELINE_COL_COLOUR))
            device_type = _norm(_cell(_BASELINE_COL_DEVICE_TYPE))
            orientation = _norm(_cell(_BASELINE_COL_ORIENTATION))
            module = _norm(_cell(_BASELINE_COL_MODULE))
            scene = _norm(_cell(_BASELINE_COL_SCENE))
            image_cell = _cell(_BASELINE_COL_IMAGE)

            if not (size and dpi and colour and device_type and orientation and module and scene):
                continue

            tokens = extract_file_tokens(image_cell)
            if not tokens:
                logger.warning(
                    f"基准图表「{sheet_name}」第{sheet_row}行 "
                    f"({size}/{dpi}/{colour}/{device_type}/{orientation}/{module}/{scene}) "
                    f"H列未找到嵌入图片 fileToken"
                )
                continue

            key = (size, dpi, colour, device_type, orientation, module, scene)
            if key in self._entries:
                prev = self._entries[key]
                raise RuntimeError(
                    f"基准图表存在重复键 {key}：\n"
                    f"  原条目: 「{prev['sheet']}」第{prev['row']}行\n"
                    f"  新条目: 「{sheet_name}」第{sheet_row}行\n"
                    f"  请删除重复行后重试"
                )
            self._entries[key] = {
                "file_token": tokens[0],
                "row": sheet_row,
                "sheet": sheet_name,
            }

    def _save_to_cache(self) -> None:
        """将基准图条目元数据写入缓存（不预下载图片，按需下载）。"""
        cache_payload = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "entries": {
                "|".join(k): v for k, v in self._entries.items()
            },
        }
        self._resolve_cache_root()
        meta_path = self._cache_root / "entries.json"
        meta_path.write_text(
            json.dumps(cache_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_from_cache(self) -> bool:
        self._resolve_cache_root()
        meta_path = self._cache_root / "entries.json"
        if not meta_path.exists():
            return False
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        entries = payload.get("entries", {})
        if not entries:
            return False
        for k_str, v in entries.items():
            parts = k_str.split("|")
            if len(parts) != 7:
                continue
            self._entries[tuple(parts)] = v
        logger.info(f"基准图加载完成（缓存）: 共 {len(self._entries)} 条")
        return True

    # ---- 查询 ----

    def lookup(self, size: str, dpi, colour: str, device_type: str,
               orientation: str, module: str, scene: str) -> str:
        """严格匹配查找基准图本地路径；未命中或下载失败抛 RuntimeError。"""
        self._ensure_loaded()
        size_n = _norm(size)
        dpi_n = _norm_dpi(dpi)
        colour_n = _norm(colour)
        device_type_n = _norm(device_type)
        orientation_n = _norm(orientation)
        module_n = _norm(module)
        scene_n = _norm(scene)
        key = (size_n, dpi_n, colour_n, device_type_n, orientation_n, module_n, scene_n)

        if key not in self._entries:
            avail = [
                f"({k[0]}/{k[1]}/{k[2]}/{k[3]}/{k[4]})"
                for k in self._entries
                if k[5] == module_n and k[6] == scene_n
            ]
            avail_text = "、".join(avail) if avail else "(无)"
            raise RuntimeError(
                f"基准图未找到 模块={module_n} 场景={scene_n} "
                f"设备={size_n}/{dpi_n}/{colour_n}/{device_type_n}/{orientation_n}。\n"
                f"  该模块/场景下已有的设备组合: {avail_text}\n"
                f"  请在基准图电子表格中补充对应行"
            )

        entry = self._entries[key]
        return self._ensure_downloaded(key, entry)

    def _ensure_downloaded(self, key: tuple, entry: dict) -> str:
        from boox_automation.core.feishu import download_media

        self._resolve_cache_root()
        size, dpi, colour, device_type, orientation, module, scene = key
        cache_subdir = self._cache_root / f"{size}_{dpi}_{colour}_{device_type}_{orientation}" / module
        cache_subdir.mkdir(parents=True, exist_ok=True)

        index = self._load_index()
        idx_key = "|".join(key)
        cached = index.get(idx_key)
        if cached and cached.get("file_token") == entry["file_token"]:
            local_path = Path(cached.get("path", ""))
            if local_path.exists():
                return str(local_path)

        # 下载到 {scene} 名（扩展名由 Content-Type 决定）
        full = download_media(entry["file_token"], str(cache_subdir), scene)
        index[idx_key] = {
            "file_token": entry["file_token"],
            "path": full,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_index(index)
        return full

    def list_all(self) -> list:
        """调试用：列出所有基准图条目。"""
        self._ensure_loaded()
        return [
            {"size": k[0], "dpi": k[1], "colour": k[2], "device_type": k[3],
             "orientation": k[4], "module": k[5], "scene": k[6],
             "file_token": v["file_token"],
             "sheet": v["sheet"], "row": v["row"]}
            for k, v in self._entries.items()
        ]
