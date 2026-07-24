"""截图基准对比：自动检测/涂黑动态区域，OpenCV 差分。

入口函数 compare(baseline_path, actual_path, result_path) 返回结构化字典。
"""
from __future__ import annotations

import logging
import os
import sys

# 兼容直接运行：将项目根目录（boox_automation/ 的父目录）加入 sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from typing import Optional

import numpy as np
import cv2

from boox_automation.core.config import (
    image_compare_auto_detect_mask,
    image_compare_fallback_top_ratio,
    image_compare_fallback_bottom_px,
    image_compare_mse_threshold,
    image_compare_template_match_threshold,
    image_compare_diff_min_area,
    image_compare_extra_ignore_regions,
)

logger = logging.getLogger(__name__)


def _build_result(success=False, has_diff=None, mse=None, diff_regions=0,
                  reason="", result_path=None) -> dict:
    return {
        "success": success,
        "has_diff": has_diff,
        "mse": mse,
        "diff_regions": diff_regions,
        "reason": reason,
        "result_path": result_path,
    }


def _check_cv2_runtime() -> tuple:
    required_attrs = [
        "cvtColor", "equalizeHist", "GaussianBlur", "matchTemplate", "minMaxLoc",
        "ORB_create", "BFMatcher", "estimateAffinePartial2D", "warpAffine",
        "absdiff", "threshold", "findContours", "rectangle", "imwrite", "resize",
        "Canny", "countNonZero",
    ]
    missing = [name for name in required_attrs if not hasattr(cv2, name)]
    if missing:
        return False, f"cv2 运行环境异常，缺少能力: {', '.join(missing)}"
    return True, ""


def _load_images(path1: str, path2: str):
    try:
        # cv2.imread 直接返回 BGR/BGRA，无需额外通道转换
        img1 = cv2.imread(path1, cv2.IMREAD_UNCHANGED)
        img2 = cv2.imread(path2, cv2.IMREAD_UNCHANGED)
        if img1 is None or img2 is None:
            raise FileNotFoundError("图片读取为空")
        img1 = _normalize_image_channels_bgr(img1)
        img2 = _normalize_image_channels_bgr(img2)
        if img1 is None or img2 is None:
            raise ValueError("图片通道格式不支持")
        return img1, img2
    except Exception as e:
        logger.error(f"加载图片失败: {e}")
        return None, None


def _normalize_image_channels_bgr(image):
    """统一为 3 通道 BGR（cv2 已是 BGR，但要处理灰度和 BGRA）。"""
    if image is None:
        return None
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim != 3:
        return None
    if image.shape[2] == 3:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return None


def _normalize_resolution_pair(img_ref, img_target, ratio_tolerance=0.03):
    if img_ref is None or img_target is None:
        return None, None, "输入图像为空"
    h1, w1 = img_ref.shape[:2]
    h2, w2 = img_target.shape[:2]
    if h1 == 0 or w1 == 0 or h2 == 0 or w2 == 0:
        return None, None, "图像尺寸非法"

    ratio1 = w1 / h1
    ratio2 = w2 / h2
    if abs(ratio1 - ratio2) / max(ratio1, 1e-6) > ratio_tolerance:
        return None, None, f"长宽比不匹配: ref={w1}x{h1}, target={w2}x{h2}"

    if (w1, h1) == (w2, h2):
        return img_ref, img_target, ""

    interp = cv2.INTER_AREA if (w2 > w1 or h2 > h1) else cv2.INTER_CUBIC
    target_resized = cv2.resize(img_target, (w1, h1), interpolation=interp)
    return img_ref, target_resized, ""


def _detect_top_bar_boundary(image) -> int:
    """检测顶部状态栏下边界（行标准差法，与分辨率/DPI/背景色无关）。

    状态栏的文字/图标行使行标准差远大于 0，纯背景行 std≈0。
    从顶部找第一个"内容带"，内容带结束位置即状态栏底。
    找不到内容带（沉浸式全屏无状态栏）→ 按高度比例兜底涂黑一小条。

    安全上限：状态栏高度不超 6%，防止状态栏与下方工具栏紧贴时过度涂黑。
    """
    if image is None:
        return 0
    h = image.shape[0]
    if image.ndim == 3 and image.shape[2] >= 3:
        gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    max_scan_rows = min(int(h * 0.12), 200)
    if max_scan_rows < 5:
        return int(h * image_compare_fallback_top_ratio())

    content_thresh = 8.0
    gap_tolerance = 3
    max_bar_px = max(int(h * 0.06), 1)

    row_std = np.array([float(gray[y].std()) for y in range(max_scan_rows)])
    content_rows = np.where(row_std > content_thresh)[0]
    if len(content_rows) == 0:
        return int(h * image_compare_fallback_top_ratio())

    first = int(content_rows[0])
    last = first
    gap = 0
    for y in range(first + 1, max_scan_rows):
        if row_std[y] > content_thresh:
            last = y
            gap = 0
        else:
            gap += 1
            if gap > gap_tolerance:
                break
    return min(last + 1, max_bar_px)


def _detect_bottom_navigation(image) -> bool:
    if image is None:
        return False
    h = image.shape[0]
    bottom_region = image[int(h * 0.85):h, :]
    if bottom_region.ndim == 3 and bottom_region.shape[2] >= 3:
        gray = cv2.cvtColor(bottom_region[:, :, :3], cv2.COLOR_BGR2GRAY)
    else:
        gray = bottom_region
    edges = cv2.Canny(gray, 50, 150)
    edge_density = cv2.countNonZero(edges) / (bottom_region.shape[0] * bottom_region.shape[1])
    return edge_density > 0.05


def _mask_bottom_nav_and_extra(image):
    """涂黑底部导航栏和额外忽略区域（保持图片尺寸不变）。"""
    if image is None:
        return None
    out = image.copy()
    h, w = out.shape[:2]

    if image_compare_auto_detect_mask():
        has_bottom_nav = _detect_bottom_navigation(image)
        bottom_pixels = image_compare_fallback_bottom_px() if has_bottom_nav else 0
    else:
        bottom_pixels = image_compare_fallback_bottom_px()

    if bottom_pixels > 0:
        out[h - bottom_pixels:h, :] = 0

    for region in image_compare_extra_ignore_regions():
        try:
            x1, y1, x2, y2 = region
            px1 = max(0, int(w * float(x1)))
            py1 = max(0, int(h * float(y1)))
            px2 = min(w, int(w * float(x2)))
            py2 = min(h, int(h * float(y2)))
            if px2 > px1 and py2 > py1:
                out[py1:py2, px1:px2] = 0
        except Exception as e:
            logger.warning(f"额外忽略区域配置错误 {region}: {e}")

    return out


def _mask_status_bar(baseline, actual):
    """涂黑顶部状态栏的时间和电池百分比区域，保留中间图标区域可见。

    状态栏布局：左侧时间 / 中间图标 / 右侧电池百分比。
    只遮盖左右两侧（动态文本），中间保留用于图标间距等对比。

    Returns:
        (涂黑后的对比图, 涂黑后的基准图)
    """
    top_px = _detect_top_bar_boundary(baseline)
    if top_px <= 0:
        logger.debug("状态栏未检测到，跳过涂黑")
        return actual, baseline
    out_actual = actual.copy()
    out_baseline = baseline.copy()
    h, w = out_actual.shape[:2]
    # 左侧遮盖（时间区域）：左侧 25%
    left_end = int(w * 0.25)
    # 右侧遮盖（电池百分比区域）：右侧 30%
    right_start = int(w * 0.70)
    for img in (out_actual, out_baseline):
        img[0:top_px, 0:left_end] = 0
        img[0:top_px, right_start:w] = 0
    logger.debug(f"状态栏边缘涂黑: top_px={top_px}, 左侧x=0-{left_end}, 右侧x={right_start}-{w}")
    return out_actual, out_baseline


def mask_status_and_navigation(image):
    """涂黑底部导航栏和额外忽略区域（状态栏由 _mask_status_bar 单独涂黑）。"""
    return _mask_bottom_nav_and_extra(image)


def _template_matching(img1, img2):
    """将 img1 作为模板在 img2 中搜索匹配区域，返回匹配区或 None。"""
    try:
        if img1.shape[0] > img2.shape[0] or img1.shape[1] > img2.shape[1]:
            logger.error("模板图尺寸大于原图，无法匹配")
            return None

        gray1 = cv2.cvtColor(img1[:, :, :3], cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2[:, :, :3], cv2.COLOR_BGR2GRAY)
        gray1 = cv2.equalizeHist(gray1)
        gray2 = cv2.equalizeHist(gray2)
        gray1 = cv2.GaussianBlur(gray1, (7, 7), 0)
        gray2 = cv2.GaussianBlur(gray2, (7, 7), 0)

        result = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val < image_compare_template_match_threshold():
            return None

        top_left = max_loc
        h, w = gray1.shape
        bottom_right = (min(top_left[0] + w, img2.shape[1]),
                        min(top_left[1] + h, img2.shape[0]))
        region = img2[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]]
        if region.shape[:2] != img1.shape[:2]:
            region = cv2.resize(region, (img1.shape[1], img1.shape[0]),
                                interpolation=cv2.INTER_AREA)
        return region
    except Exception as e:
        logger.error(f"模板匹配异常: {e}")
        return None


def _analyze_contours(img1_proc, img2_proc, mse, original_img2,
                      crop_offset_x, crop_offset_y, result_path,
                      binary_threshold=50, morph_kernel_size=5, min_area=None):
    """轮廓分析：差分 → 二值化 → 形态学 → 轮廓标记。

    Args:
        morph_kernel_size: 形态学核大小，局部差异路径用 3 避免腐蚀过大区域。
        min_area: 轮廓最小面积，None 则使用配置值。
    """
    img1_blur = cv2.GaussianBlur(img1_proc, (5, 5), 0)
    img2_blur = cv2.GaussianBlur(img2_proc, (5, 5), 0)

    diff = cv2.absdiff(img1_blur[:, :, :3], img2_blur[:, :, :3])
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, binary_threshold, 255, cv2.THRESH_BINARY)
    if thresh is None:
        return _build_result(success=False, mse=mse, reason="差分计算失败",
                             result_path=result_path)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (morph_kernel_size, morph_kernel_size))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.medianBlur(thresh, 3)

    try:
        cnts, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if min_area is None:
            min_area = image_compare_diff_min_area()
        diff_found = False
        diff_regions = 0
        marked = original_img2[:, :, :3].copy()
        for c in cnts:
            if cv2.contourArea(c) < min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            x_mapped = x + crop_offset_x
            y_mapped = y + crop_offset_y
            cv2.rectangle(marked, (x_mapped, y_mapped),
                          (x_mapped + w, y_mapped + h), (0, 0, 255), 2)
            diff_found = True
            diff_regions += 1

        if diff_found:
            cv2.imwrite(result_path, marked)
        else:
            result_path = None
        return _build_result(success=True, has_diff=diff_found, mse=mse,
                             diff_regions=diff_regions, reason="检测完成",
                             result_path=result_path)
    except Exception as e:
        logger.error(f"标记差异失败: {e}")
        return _build_result(success=False, mse=mse,
                             reason=f"标记差异失败: {e}",
                             result_path=result_path)


def _detect_local_concentrated_diff(img1, img2, pctl_threshold=15):
    """检查是否有集中在特定区域（顶部/底部）的差异。

    全局 MSE 低于阈值时调用：用 P95 百分位像素差检测，不被大面积零差稀释。
    均值会因"有差异行/总行数"比例低而被拉平（如 40 行状态栏差异 / 372 行总区域 = 均值仅 1.82），
    P95 只看差异最大的 5% 像素，对集中差异更敏感。

    Returns:
        dict(region, p95_diff) 有集中差异时返回，None 表示无集中差异。
    """
    if img1 is None or img2 is None:
        return None
    diff = cv2.absdiff(img1[:, :, :3], img2[:, :, :3])
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    regions = [
        ("顶部", 0, min(int(h * 0.15), h)),
        ("底部", max(0, int(h * 0.85)), h),
    ]
    for name, y1, y2 in regions:
        if y2 <= y1:
            continue
        region_gray = gray[y1:y2]
        nonzero = region_gray[region_gray > 0]
        if len(nonzero) == 0:
            continue
        p95 = float(np.percentile(nonzero, 95))
        if p95 >= pctl_threshold:
            mean_diff = float(region_gray.mean())
            return {"region": name, "p95_diff": p95, "mean_diff": mean_diff}
    return None


def _align_by_features(img_ref, img_target):
    try:
        gray_ref = cv2.cvtColor(img_ref[:, :, :3], cv2.COLOR_BGR2GRAY)
        gray_target = cv2.cvtColor(img_target[:, :, :3], cv2.COLOR_BGR2GRAY)

        orb = cv2.ORB_create(nfeatures=2000, scoreType=cv2.ORB_FAST_SCORE)
        kp1, des1 = orb.detectAndCompute(gray_ref, None)
        kp2, des2 = orb.detectAndCompute(gray_target, None)
        if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
            return None

        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        matches = sorted(matches, key=lambda x: x.distance)
        good_matches = matches[:min(100, len(matches))]
        if len(good_matches) < 10:
            return None

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        M, _ = cv2.estimateAffinePartial2D(src_pts, dst_pts)
        if M is None:
            return None

        h, w = img_ref.shape[:2]
        aligned = cv2.warpAffine(img_target, M, (w, h), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
        return aligned
    except Exception as e:
        logger.error(f"特征对齐异常: {e}")
        return None


def _calculate_image_difference(img1, img2):
    try:
        diff = cv2.absdiff(img1[:, :, :3], img2[:, :, :3])
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)
        return thresh
    except Exception as e:
        logger.error(f"计算差异失败: {e}")
        return None


def _get_status_bar_icon_regions(image, top_px, diff_mask=None):
    """返回状态栏中时间/电池文字区域（用于过滤差异报告）。

    自动从 diff_mask 中检测差异列的连续块，最左块=时间，最右块=电池，过滤这俩。
    中间的差异块（图标偏移等）保留不过滤。
    无 diff_mask 时回退到固定比例。
    """
    if top_px <= 0:
        return []
    h, w = image.shape[:2]
    if diff_mask is None:
        left_end = int(w * 0.20)
        right_start = int(w * 0.75)
        return [(0, 0, left_end, top_px), (right_start, 0, w, top_px)]
    # 在状态栏区域内找有差异的列，聚类为连续块
    bar_diff = diff_mask[0:top_px, :]
    col_has_diff = np.any(bar_diff > 0, axis=0)
    diff_cols = np.where(col_has_diff)[0]
    if len(diff_cols) == 0:
        return []
    # 聚类：间隙 > 10px 视为不同块
    clusters = []
    start = int(diff_cols[0])
    prev = start
    for c in diff_cols[1:]:
        if c - prev > 10:
            clusters.append((start, prev + 1))
            start = int(c)
        prev = int(c)
    clusters.append((start, prev + 1))
    if len(clusters) <= 2:
        return [(x1, 0, x2, top_px) for x1, x2 in clusters]
    # 超过 2 块：只过滤最左（时间）和最右（电池），中间保留
    lx1, lx2 = clusters[0]
    rx1, rx2 = clusters[-1]
    return [(lx1, 0, lx2, top_px), (rx1, 0, rx2, top_px)]


def _filter_status_bar_diff_regions(diff_regions, icon_regions):
    """过滤掉时间/电池文字区域的差异轮廓，只保留中间图标区域的差异。"""
    if not icon_regions:
        return diff_regions
    filtered = []
    for c in diff_regions:
        x, y, w, h = cv2.boundingRect(c)
        in_icon_region = False
        for ix1, iy1, ix2, iy2 in icon_regions:
            if x < ix2 and x + w > ix1 and y < iy2 and y + h > iy1:
                in_icon_region = True
                break
        if not in_icon_region:
            filtered.append(c)
    return filtered


def _analyze_contours_filtered(img1_proc, img2_proc, mse, original_img2,
                               crop_offset_x, crop_offset_y, result_path,
                               icon_regions=None,
                               binary_threshold=50, morph_kernel_size=5,
                               min_area=None):
    """轮廓分析 + 过滤状态栏文字区域。"""
    img1_blur = cv2.GaussianBlur(img1_proc, (5, 5), 0)
    img2_blur = cv2.GaussianBlur(img2_proc, (5, 5), 0)

    diff = cv2.absdiff(img1_blur[:, :, :3], img2_blur[:, :, :3])
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, binary_threshold, 255, cv2.THRESH_BINARY)
    if thresh is None:
        return _build_result(success=False, mse=mse, reason="差分计算失败",
                             result_path=result_path)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (morph_kernel_size, morph_kernel_size))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.medianBlur(thresh, 3)

    try:
        cnts, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if min_area is None:
            min_area = image_compare_diff_min_area()

        # 按面积过滤
        cnts = [c for c in cnts if cv2.contourArea(c) >= min_area]
        # 过滤状态栏文字区域
        if icon_regions:
            cnts = _filter_status_bar_diff_regions(cnts, icon_regions)

        diff_found = False
        diff_regions = 0
        marked = original_img2[:, :, :3].copy()
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            x_mapped = x + crop_offset_x
            y_mapped = y + crop_offset_y
            cv2.rectangle(marked, (x_mapped, y_mapped),
                          (x_mapped + w, y_mapped + h), (0, 0, 255), 2)
            diff_found = True
            diff_regions += 1

        if diff_found:
            cv2.imwrite(result_path, marked)
        else:
            result_path = None
        return _build_result(success=True, has_diff=diff_found, mse=mse,
                             diff_regions=diff_regions, reason="检测完成",
                             result_path=result_path)
    except Exception as e:
        logger.error(f"标记差异失败: {e}")
        return _build_result(success=False, mse=mse,
                             reason=f"标记差异失败: {e}",
                             result_path=result_path)


def compare(baseline_path: str, actual_path: str, result_path: str,
            mse_threshold: float | None = None) -> dict:
    """对比基准图与实际截图，返回 {success, has_diff, mse, diff_regions, reason, result_path}。

    Args:
        mse_threshold: 覆盖配置中的 mse_threshold，None 则使用配置值
    """
    ok, reason = _check_cv2_runtime()
    if not ok:
        logger.error(reason)
        return _build_result(reason=reason, result_path=result_path)

    if not os.path.exists(baseline_path):
        return _build_result(reason=f"基准图不存在: {baseline_path}",
                             result_path=result_path)
    if not os.path.exists(actual_path):
        return _build_result(reason=f"实际截图不存在: {actual_path}",
                             result_path=result_path)

    img1, img2 = _load_images(baseline_path, actual_path)
    if img1 is None or img2 is None:
        return _build_result(reason="加载图片失败", result_path=result_path)

    # 保存原始对比图（用于红框标记，保留原始状态栏）
    original_img2 = img2.copy()

    # 底部导航栏 + 额外忽略区域涂黑（状态栏不涂黑，由轮廓过滤处理）
    img1_masked = _mask_bottom_nav_and_extra(img1)
    img2_masked = _mask_bottom_nav_and_extra(img2)
    if img1_masked is None or img2_masked is None:
        return _build_result(reason="mask 处理失败", result_path=result_path)

    img1_masked, img2_masked, norm_reason = _normalize_resolution_pair(
        img1_masked, img2_masked)
    if img1_masked is None or img2_masked is None:
        return _build_result(reason=f"分辨率归一化失败: {norm_reason}",
                             result_path=result_path)

    region_from_full = _template_matching(img1_masked, img2_masked)
    if region_from_full is None:
        aligned = _align_by_features(img1_masked, img2_masked)
        if aligned is not None:
            img1_proc = img1_masked
            img2_proc = aligned
            crop_offset_x = 0
            crop_offset_y = 0
        else:
            img1_proc = img1_masked
            img2_proc = img2_masked
            if img1_proc.shape != img2_proc.shape:
                img2_proc = cv2.resize(
                    img2_proc, (img1_proc.shape[1], img1_proc.shape[0]),
                    interpolation=cv2.INTER_AREA)
            crop_offset_x = 0
            crop_offset_y = 0
    else:
        img1_proc = img1_masked
        img2_proc = region_from_full

        gray1 = cv2.cvtColor(img1_proc[:, :, :3], cv2.COLOR_BGR2GRAY)
        gray2_full = cv2.cvtColor(img2_masked[:, :, :3], cv2.COLOR_BGR2GRAY)
        gray1_eq = cv2.equalizeHist(gray1)
        gray2_eq = cv2.equalizeHist(gray2_full)
        res = cv2.matchTemplate(gray1_eq, gray2_eq, cv2.TM_CCOEFF_NORMED)
        _, _, _, top_left = cv2.minMaxLoc(res)
        crop_offset_x = top_left[0]
        crop_offset_y = top_left[1]

    if img1_proc.shape != img2_proc.shape:
        img2_proc = cv2.resize(
            img2_proc, (img1_proc.shape[1], img1_proc.shape[0]),
            interpolation=cv2.INTER_AREA)

    # MSE 检查：使用边缘遮盖（排除时间/电池干扰）
    mse = float(np.mean(
        (img1_proc.astype("float") - img2_proc.astype("float")) ** 2
    ))
    threshold = mse_threshold if mse_threshold is not None else image_compare_mse_threshold()
    logger.info("截图对比: 设备实际页面与基准图无差异" if mse < threshold else
                 f"截图对比: MSE={mse:.2f}（阈值{threshold}），进入轮廓分析")

    result_dir = os.path.dirname(result_path)
    if result_dir and not os.path.exists(result_dir):
        os.makedirs(result_dir, exist_ok=True)
    ext = os.path.splitext(result_path)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        result_path = os.path.splitext(result_path)[0] + ".png"

    if mse < threshold:
        # MSE 低于阈值，检查是否有局部集中差异
        local_diff = _detect_local_concentrated_diff(img1_proc, img2_proc)
        if local_diff is None:
            return _build_result(success=True, has_diff=False, mse=mse,
                                 diff_regions=0, reason="MSE 低于阈值，无差异",
                                 result_path=None)
        logger.info(f"截图对比: 全局MSE={mse:.2f}低于阈值，但检测到局部集中差异"
                    f"({local_diff['region']}，P95像素差={local_diff['p95_diff']:.1f})，进入轮廓分析")
        # 局部差异已确认，使用过滤版轮廓分析（排除时间/电池文字区域）
        diff_mask = cv2.cvtColor(cv2.absdiff(img1[:, :, :3], img2[:, :, :3]), cv2.COLOR_BGR2GRAY)
        top_px = _detect_top_bar_boundary(original_img2)
        icon_regions = _get_status_bar_icon_regions(original_img2, top_px, diff_mask)
        return _analyze_contours_filtered(
            img1_proc, img2_proc, mse, original_img2,
            crop_offset_x, crop_offset_y, result_path,
            icon_regions=icon_regions,
            binary_threshold=10, morph_kernel_size=3, min_area=500)

    # MSE 高于阈值，使用过滤版轮廓分析
    diff_mask = cv2.cvtColor(cv2.absdiff(img1[:, :, :3], img2[:, :, :3]), cv2.COLOR_BGR2GRAY)
    top_px = _detect_top_bar_boundary(original_img2)
    icon_regions = _get_status_bar_icon_regions(original_img2, top_px, diff_mask)
    return _analyze_contours_filtered(
        img1_proc, img2_proc, mse, original_img2,
        crop_offset_x, crop_offset_y, result_path,
        icon_regions=icon_regions,
        binary_threshold=50)


class OpenCV:
    """图片对比工具类，支持本地测试和程序化调用，MSE 阈值可配置。"""

    def __init__(self):
        self.mse_threshold: float | None = None

    def compare_pictures(self, pic1: str, pic2: str, result_path: str) -> int:
        """对比两张图片，有差异时在 result_path 生成红框标记图。

        Returns:
            0 = 对比完成（无差异或有差异均已标记）
            1 = 失败（图片不存在、加载失败或运行时异常）
        """
        result = compare(pic1, pic2, result_path, mse_threshold=self.mse_threshold)
        return 0 if result.get("success") else 1


if __name__ == '__main__':
    """本地调试入口：python -m boox_automation.engine.image_compare <基准图> <对比图> [MSE阈值]"""
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s  %(levelname)-5s  %(message)s")
    _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # ── 硬编码测试路径（填写后可直接运行，不填则需命令行传参） ──
    TEST_PIC1 = ""
    TEST_PIC2 = ""
    TEST_MSE = None  # None = 使用 config.yaml 阈值，或填数字如 120

    if len(sys.argv) >= 3:
        pic1 = sys.argv[1]
        pic2 = sys.argv[2]
        mse_val = float(sys.argv[3]) if len(sys.argv) > 3 else None
    elif TEST_PIC1 and TEST_PIC2:
        pic1 = TEST_PIC1
        pic2 = TEST_PIC2
        mse_val = TEST_MSE
        logger.info(f"使用硬编码测试路径: pic1={pic1}, pic2={pic2}")
    else:
        print(f"用法: python {__file__} <基准图路径> <对比图路径> [MSE阈值]")
        print(f"      或在脚本中设置 TEST_PIC1 / TEST_PIC2 硬编码路径后直接运行")
        sys.exit(1)

    result_dir = os.path.join(_project_root, "artifacts", "image_diff")
    os.makedirs(result_dir, exist_ok=True)
    result_path = os.path.join(result_dir, "debug_result.jpg")

    comparator = OpenCV()
    if mse_val is not None:
        comparator.mse_threshold = mse_val
    result_dict = compare(pic1, pic2, result_path)
    if result_dict.get("success"):
        if result_dict.get("has_diff"):
            logger.info(f"检测到 {result_dict.get('diff_regions', 0)} 处差异，结果已保存至: {result_path}")
        else:
            logger.info("截图对比: 设备实际页面与基准图无差异")
    else:
        logger.error(f"图片比较失败: {result_dict.get('reason', '未知错误')}")
