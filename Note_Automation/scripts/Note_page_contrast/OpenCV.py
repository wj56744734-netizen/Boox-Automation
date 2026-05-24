from skimage import io
import cv2
import numpy as np
from Note_Automation.config import driver
import os
import time
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def handle_permission_error(operation, path, error):
    logging.error(f"{operation} {path} 时权限不足: {error}")
    return None


def handle_io_error(operation, path, error):
    logging.error(f"{operation} {path} 时出现 I/O 错误: {error}")
    return None


def handle_general_error(operation, error):
    logging.error(f"{operation} 时出现错误: {error}")
    return None


class OpenCV:
    def __init__(self):
        self.driver = driver
        self.default_top = 60
        self.default_bottom = 120
        self.debug_mode = False
        # 新增：MSE 阈值，小于此值认为无差异（可根据实际效果调整，建议 50~150）
        self.mse_threshold = 100

    def _build_result(self, success=False, has_diff=None, mse=None, diff_regions=0, reason="", result_path=None):
        return {
            "success": success,
            "has_diff": has_diff,
            "mse": mse,
            "diff_regions": diff_regions,
            "reason": reason,
            "result_path": result_path,
        }

    def _check_cv2_runtime(self):
        required_attrs = [
            "cvtColor", "equalizeHist", "GaussianBlur", "matchTemplate", "minMaxLoc",
            "ORB_create", "BFMatcher", "estimateAffinePartial2D", "warpAffine",
            "absdiff", "threshold", "findContours", "rectangle", "imwrite", "resize",
            "Canny", "countNonZero"
        ]
        missing = [name for name in required_attrs if not hasattr(cv2, name)]
        if missing:
            return False, f"cv2 运行环境异常，缺少能力: {', '.join(missing)}"
        return True, ""

    def _normalize_image_channels(self, image):
        """统一图像通道到 BGR/BGRA，避免不同来源截图导致异常。"""
        if image is None:
            return None
        if image.ndim == 2:
            return np.stack([image, image, image], axis=-1)
        if image.ndim != 3:
            return None

        channel = image.shape[2]
        if channel == 3:
            # skimage 默认 RGB，这里转 BGR
            return image[:, :, ::-1]
        if channel == 4:
            # RGBA -> BGRA
            return image[:, :, [2, 1, 0, 3]]
        return None

    def _normalize_resolution_pair(self, img_ref, img_target, ratio_tolerance=0.03):
        """
        分辨率归一化：在长宽比一致前提下，将目标图缩放到参考图尺寸，
        用于消除同尺寸设备不同分辨率带来的影响。
        """
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

    def _detect_top_bar_boundary(self, image):
        if image is None:
            return 0
        h, w, _ = image.shape
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        max_scan_rows = min(150, h)
        diff_threshold = 30
        for y in range(1, max_scan_rows):
            row_prev = gray[y - 1, :]
            row_curr = gray[y, :]
            diff = np.abs(row_curr - row_prev).mean()
            if diff > diff_threshold:
                logging.debug(f"检测到顶部边界在第 {y} 行")
                return y
        logging.debug("未检测到顶部边界，使用默认顶部裁剪值")
        return self.default_top

    def _detect_bottom_navigation(self, image):
        if image is None:
            return False
        h, w, _ = image.shape
        bottom_region = image[int(h * 0.85):h, :]
        gray = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = cv2.countNonZero(edges) / (bottom_region.shape[0] * bottom_region.shape[1])
        return edge_density > 0.05

    def crop_status_and_navigation(self, image):
        if image is None:
            return None
        h, w, _ = image.shape
        top_pixels = self._detect_top_bar_boundary(image)
        logging.debug(f"确定顶部裁剪高度: {top_pixels}px")
        has_bottom_nav = self._detect_bottom_navigation(image)
        bottom_pixels = self.default_bottom if has_bottom_nav else 0
        if not has_bottom_nav:
            logging.debug("未检测到底部导航栏，不裁剪底部")
        else:
            logging.debug(f"检测到底部导航栏，裁剪底部 {bottom_pixels}px")

        start_y = top_pixels
        end_y = h - bottom_pixels
        if start_y >= end_y:
            logging.warning("裁剪区域无效，返回原图")
            return image
        cropped = image[start_y:end_y, :]

        if self.debug_mode:
            marked = image.copy()
            cv2.rectangle(marked, (0, 0), (w, start_y), (0, 255, 0), 2)
            cv2.rectangle(marked, (0, end_y), (w, h), (0, 0, 255), 2)
            cv2.namedWindow("Before Crop", cv2.WINDOW_NORMAL)
            cv2.namedWindow("After Crop", cv2.WINDOW_NORMAL)
            cv2.imshow("Before Crop", marked)
            cv2.imshow("After Crop", cropped)
            logging.debug("按任意键继续...")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        return cropped

    # ---------- 优化后的模板匹配 ----------
    def template_matching(self, img1, img2):
        """
        将 img1 作为模板在 img2 中搜索匹配区域。
        返回匹配到的区域（img2 的子图），若失败返回 None。
        """
        try:
            if img1.shape[0] > img2.shape[0] or img1.shape[1] > img2.shape[1]:
                logging.error("模板图尺寸大于原图，无法匹配")
                return None

            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
            gray1 = cv2.equalizeHist(gray1)
            gray2 = cv2.equalizeHist(gray2)
            gray1 = cv2.GaussianBlur(gray1, (7, 7), 0)
            gray2 = cv2.GaussianBlur(gray2, (7, 7), 0)

            result = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            logging.debug(f"模板匹配最佳相似度: {max_val:.4f}")

            if max_val < 0.65:
                logging.debug("模板匹配度不足，无法可靠定位")
                return None

            top_left = max_loc
            h, w = gray1.shape
            bottom_right = (min(top_left[0] + w, img2.shape[1]),
                            min(top_left[1] + h, img2.shape[0]))
            region = img2[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]]
            if region.shape[:2] != img1.shape[:2]:
                region = cv2.resize(region, (img1.shape[1], img1.shape[0]), interpolation=cv2.INTER_AREA)
            return region
        except Exception as e:
            logging.error(f"模板匹配异常: {e}")
            return None

    # ---------- 新增：基于 ORB 特征匹配的图像对齐 ----------
    def _align_by_features(self, img_ref, img_target):
        try:
            gray_ref = cv2.cvtColor(img_ref, cv2.COLOR_BGR2GRAY)
            gray_target = cv2.cvtColor(img_target, cv2.COLOR_BGR2GRAY)

            orb = cv2.ORB_create(nfeatures=2000, scoreType=cv2.ORB_FAST_SCORE)
            kp1, des1 = orb.detectAndCompute(gray_ref, None)
            kp2, des2 = orb.detectAndCompute(gray_target, None)
            if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
                logging.warning("特征点不足，无法进行特征对齐")
                return None

            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des1, des2)
            matches = sorted(matches, key=lambda x: x.distance)
            good_matches = matches[:min(100, len(matches))]
            if len(good_matches) < 10:
                logging.warning("优质匹配点过少，放弃特征对齐")
                return None

            src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

            M, inliers = cv2.estimateAffinePartial2D(src_pts, dst_pts)
            if M is None:
                logging.warning("仿射变换矩阵计算失败")
                return None

            h, w = img_ref.shape[:2]
            aligned = cv2.warpAffine(img_target, M, (w, h), flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
            logging.debug("特征对齐成功")
            return aligned
        except Exception as e:
            logging.error(f"特征对齐异常: {e}")
            return None

    # ---------- 改进后的 compare_pictures（增加 MSE 预判） ----------
    def compare_pictures(self, pictures1, pictures2, result_path='result.png', context_name=None, return_details=False):
        ok, reason = self._check_cv2_runtime()
        if not ok:
            logging.error(reason)
            details = self._build_result(success=False, has_diff=None, mse=None, diff_regions=0, reason=reason,
                                         result_path=result_path)
            return details if return_details else -1

        if not os.path.exists(pictures1):
            logging.error(f"图片 {pictures1} 不存在")
            details = self._build_result(success=False, has_diff=None, mse=None, diff_regions=0, reason=f"图片不存在: {pictures1}",
                                         result_path=result_path)
            return details if return_details else -1
        if not os.path.exists(pictures2):
            logging.error(f"图片 {pictures2} 不存在")
            details = self._build_result(success=False, has_diff=None, mse=None, diff_regions=0, reason=f"图片不存在: {pictures2}",
                                         result_path=result_path)
            return details if return_details else -1

        img1, img2 = self.load_images(pictures1, pictures2)
        if img1 is None or img2 is None:
            details = self._build_result(success=False, has_diff=None, mse=None, diff_regions=0, reason="加载图片失败",
                                         result_path=result_path)
            return details if return_details else -1

        # 裁剪状态栏和导航栏
        img1_cropped = self.crop_status_and_navigation(img1)
        img2_cropped = self.crop_status_and_navigation(img2)
        if img1_cropped is None or img2_cropped is None:
            logging.error("裁剪后图片为空")
            details = self._build_result(success=False, has_diff=None, mse=None, diff_regions=0, reason="裁剪后图片为空",
                                         result_path=result_path)
            return details if return_details else -1

        # 分辨率归一化（重点用于同尺寸不同分辨率设备）
        img1_cropped, img2_cropped, normalize_reason = self._normalize_resolution_pair(img1_cropped, img2_cropped)
        if img1_cropped is None or img2_cropped is None:
            logging.error(f"分辨率归一化失败: {normalize_reason}")
            details = self._build_result(
                success=False, has_diff=None, mse=None, diff_regions=0,
                reason=f"分辨率归一化失败: {normalize_reason}", result_path=result_path
            )
            return details if return_details else -1

        # 保存原始 img2 用于最终标记差异
        original_img2 = img2.copy()

        # ========== 步骤1：尝试模板匹配 ==========
        region_from_full_image = self.template_matching(img1_cropped, img2_cropped)
        # ========== 步骤2：若模板匹配失败，尝试特征对齐 ==========
        if region_from_full_image is None:
            logging.debug("模板匹配失败，尝试使用特征对齐...")
            aligned = self._align_by_features(img1_cropped, img2_cropped)
            if aligned is not None:
                img1_proc = img1_cropped
                img2_proc = aligned
                crop_offset_x = 0
                crop_offset_y = 0
                logging.debug("使用特征对齐后的图像进行差分")
            else:
                logging.warning("特征对齐也失败，直接使用裁剪图比较（假设无偏移）")
                img1_proc = img1_cropped
                img2_proc = img2_cropped
                if img1_proc.shape != img2_proc.shape:
                    img2_proc = cv2.resize(img2_proc, (img1_proc.shape[1], img1_proc.shape[0]),
                                           interpolation=cv2.INTER_AREA)
                crop_offset_x = 0
                crop_offset_y = 0
        else:
            img1_proc = img1_cropped
            img2_proc = region_from_full_image

            top_crop_img2 = self._detect_top_bar_boundary(img2)
            h2_full, w2_full, _ = img2.shape
            h2_cropped, w2_cropped, _ = img2_cropped.shape
            top_offset_img2 = h2_full - h2_cropped

            gray1 = cv2.cvtColor(img1_proc, cv2.COLOR_BGR2GRAY)
            gray2_full = cv2.cvtColor(img2_cropped, cv2.COLOR_BGR2GRAY)
            gray1_eq = cv2.equalizeHist(gray1)
            gray2_eq = cv2.equalizeHist(gray2_full)
            res = cv2.matchTemplate(gray1_eq, gray2_eq, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, top_left = cv2.minMaxLoc(res)
            if max_val < 0.65:
                logging.warning("二次匹配相似度低，偏移量可能不准确")
            region_x_in_cropped, region_y_in_cropped = top_left[0], top_left[1]
            crop_offset_x = region_x_in_cropped
            crop_offset_y = region_y_in_cropped + top_offset_img2

        # ========== 新增：MSE 预判，忽略微小差异 ==========
        # 确保两张图片尺寸一致
        if img1_proc.shape != img2_proc.shape:
            img2_proc = cv2.resize(img2_proc, (img1_proc.shape[1], img1_proc.shape[0]),
                                   interpolation=cv2.INTER_AREA)

        # 计算 MSE（均方误差）
        mse = np.mean((img1_proc.astype("float") - img2_proc.astype("float")) ** 2)
        logging.debug(f"当前 MSE = {mse:.2f} (阈值 {self.mse_threshold})")
        if mse < self.mse_threshold:
            logging.debug(f"MSE 小于阈值，判定为无差异，跳过标记 (MSE={mse:.2f})")

            # 注意：即使无差异，也可选择保存原图或什么都不做
            # 为了行为一致，仍然保存 original_img2（不画框）
            result_dir = os.path.dirname(result_path)
            if not os.path.exists(result_dir):
                os.makedirs(result_dir, exist_ok=True)
            valid_extensions = ['.png', '.jpg', '.jpeg']
            ext = os.path.splitext(result_path)[1].lower()
            if ext not in valid_extensions:
                result_path = os.path.splitext(result_path)[0] + '.png'
            cv2.imwrite(result_path, original_img2)

            short_path = os.path.join(context_name, os.path.basename(pictures1))
            logging.info(f"{short_path} 页面无差异")

            details = self._build_result(success=True, has_diff=False, mse=float(mse), diff_regions=0,
                                         reason="MSE 低于阈值，无差异", result_path=result_path)
            return details if return_details else 0

        # ========== 差分计算与形态学处理（仅当 MSE 超过阈值时执行） ==========
        img1_blur = cv2.GaussianBlur(img1_proc, (5, 5), 0)
        img2_blur = cv2.GaussianBlur(img2_proc, (5, 5), 0)

        thresh = self.calculate_image_difference(img1_blur, img2_blur)
        if thresh is None or isinstance(thresh, int):
            details = self._build_result(success=False, has_diff=None, mse=float(mse), diff_regions=0,
                                         reason="差分计算失败", result_path=result_path)
            return details if return_details else -1

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.medianBlur(thresh, 3)

        try:
            cnts, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            diff_found = False
            diff_regions = 0
            for c in cnts:
                if cv2.contourArea(c) < 1800:
                    continue
                x, y, w, h = cv2.boundingRect(c)
                x_mapped = x + crop_offset_x
                y_mapped = y + crop_offset_y
                cv2.rectangle(original_img2, (x_mapped, y_mapped),
                              (x_mapped + w, y_mapped + h), (0, 0, 255), 2)
                diff_found = True
                diff_regions += 1

            if diff_found:
                short_path = os.path.join(context_name, os.path.basename(pictures1))
                logging.info(f"{short_path} 检测到差异区域，已标记")
            else:
                short_path = os.path.join(context_name, os.path.basename(pictures1))
                logging.info(f"{short_path} 页面无差异")

            result_dir = os.path.dirname(result_path)
            if not os.path.exists(result_dir):
                os.makedirs(result_dir, exist_ok=True)
            valid_extensions = ['.png', '.jpg', '.jpeg']
            ext = os.path.splitext(result_path)[1].lower()
            if ext not in valid_extensions:
                result_path = os.path.splitext(result_path)[0] + '.png'
            cv2.imwrite(result_path, original_img2)
            details = self._build_result(
                success=True,
                has_diff=diff_found,
                mse=float(mse),
                diff_regions=diff_regions,
                reason="检测完成",
                result_path=result_path
            )
            return details if return_details else 0
        except Exception as e:
            logging.error(f"标记差异失败: {e}")
            details = self._build_result(success=False, has_diff=None, mse=float(mse), diff_regions=0,
                                         reason=f"标记差异失败: {e}", result_path=result_path)
            return details if return_details else -1

    def load_images(self, path1, path2):
        try:
            img1 = io.imread(path1)
            img2 = io.imread(path2)
            if img1 is None or img2 is None:
                raise FileNotFoundError("图片读取为空")
            img1 = self._normalize_image_channels(img1)
            img2 = self._normalize_image_channels(img2)
            if img1 is None or img2 is None:
                raise ValueError("图片通道格式不支持，无法标准化为 BGR/BGRA")
            logging.debug(f"图片1尺寸: {img1.shape[1]}x{img1.shape[0]}")
            logging.debug(f"图片2尺寸: {img2.shape[1]}x{img2.shape[0]}")
            return img1, img2
        except Exception as e:
            logging.error(f"加载图片失败: {e}")
            return None, None

    def calculate_image_difference(self, img1, img2):
        try:
            diff = cv2.absdiff(img1, img2)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)
            return thresh
        except Exception as e:
            logging.error(f"计算差异失败: {e}")
            return -1

    def _crop_border(self, image, border=6):
        h, w, _ = image.shape
        if h > 2 * border and w > 2 * border:
            return image[border:h - border, border:w - border]
        return image

    def screenshot(self, screenshot_route, screenshot_name):
        if not screenshot_route:
            logging.error("截图路径为空")
            return None
        try:
            time.sleep(1)
            os.makedirs(screenshot_route, exist_ok=True)
            full_path = os.path.join(screenshot_route, f"{screenshot_name}.png")
            screenshot_data = self.driver.get_screenshot_as_png()
            with open(full_path, 'wb') as f:
                f.write(screenshot_data)
            return full_path
        except Exception as e:
            return handle_general_error("截图", e)


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pic1 = os.path.join("/Users/xiaoyu/Downloads/Screenshot_20260512_150309.png")
    pic2 = os.path.join("/Users/xiaoyu/Downloads/Screenshot_20260512_140935.png")
    result_path = os.path.join(script_dir, "exception_page/result.jpg")

    comparator = OpenCV()
    # 可调整 MSE 阈值（默认 100）
    comparator.mse_threshold = 120   # 例如更宽松
    result = comparator.compare_pictures(pic1, pic2, result_path)
    if result == 0:
        logging.debug(f"图片比较完成，结果已保存至: {result_path}")
    else:
        logging.error("图片比较失败")