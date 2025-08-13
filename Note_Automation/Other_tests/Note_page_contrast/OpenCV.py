from skimage import io
import cv2
import numpy as np
from Note_Automation.config import driver
import os
import time
import logging

# 配置日志
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
        self.default_top = 60  # 默认顶部裁剪像素（检测失效时兜底）
        self.default_bottom = 120  # 默认底部裁剪像素（检测失效时兜底）
        self.debug_mode = False  # 调试模式：显示裁剪前后的图像

    def _detect_top_bar_boundary(self, image):
        """
        精准检测顶部横线与内容区的边界（通过行像素差异对比）
        返回：需要裁剪的顶部高度（横线的下边界）
        """
        if image is None:
            return 0
        h, w, _ = image.shape
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 顶部区域扫描范围（可根据实际调整）
        max_scan_rows = min(100, h)  # 最多扫描前100行
        diff_threshold = 30  # 相邻行像素差异阈值（值越大越宽松）

        for y in range(1, max_scan_rows):
            # 计算当前行与上一行的像素差异（均值）
            row_prev = gray[y - 1, :]
            row_curr = gray[y, :]
            diff = np.abs(row_curr - row_prev).mean()

            # 如果差异超过阈值，认为是横线与内容区的边界
            if diff > diff_threshold:
                logging.info(f"检测到顶部边界在第 {y} 行")
                return y  # 返回边界行作为裁剪高度

        # 未找到明显边界时，使用默认值
        logging.warning("未检测到顶部边界，使用默认顶部裁剪值")
        return self.default_top

    def _detect_bottom_navigation(self, image):
        """检测图片是否存在底部导航栏（基于边缘密度判断）"""
        if image is None:
            return False
        h, w, _ = image.shape
        # 取底部15%区域检测（导航栏通常在底部固定区域）
        bottom_region = image[int(h * 0.85):h, :]
        # 转换为灰度图并检测边缘
        gray = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        # 计算边缘像素占比（导航栏通常有明显按钮边缘）
        edge_density = cv2.countNonZero(edges) / (bottom_region.shape[0] * bottom_region.shape[1])
        # 边缘密度超过0.05则认为存在导航栏（可根据实际页面调整阈值）
        return edge_density > 0.05

    def crop_status_and_navigation(self, image):
        """
        动态裁剪顶部状态栏和底部导航栏
        仅依靠内容检测（移除分辨率判断逻辑）
        """
        if image is None:
            return None
        h, w, _ = image.shape

        # 1. 检测顶部需要裁剪的高度（依靠行像素差异）
        top_pixels = self._detect_top_bar_boundary(image)
        logging.info(f"确定顶部裁剪高度: {top_pixels}px")

        # 2. 检测底部导航栏
        has_bottom_nav = self._detect_bottom_navigation(image)
        bottom_pixels = self.default_bottom if has_bottom_nav else 0
        if not has_bottom_nav:
            logging.info("未检测到底部导航栏，不裁剪底部")
        else:
            logging.info(f"检测到底部导航栏，裁剪底部 {bottom_pixels}px")

        # 3. 执行裁剪（确保裁剪后区域有效）
        start_y = top_pixels
        end_y = h - bottom_pixels
        if start_y >= end_y:
            logging.warning(f"裁剪区域无效，返回原图")
            return image

        cropped = image[start_y:end_y, :]

        # 4. 调试模式：显示裁剪前后的图像（便于调整参数）
        if self.debug_mode:
            # 显示原图和裁剪区域的标记（绿色框表示精准裁剪区域）
            marked = image.copy()
            cv2.rectangle(marked, (0, 0), (w, start_y), (0, 255, 0), 2)  # 绿色框标记顶部裁剪区域
            cv2.rectangle(marked, (0, end_y), (w, h), (0, 0, 255), 2)  # 红色框标记底部裁剪区域

            # 调整窗口大小以适应显示
            cv2.namedWindow("Before Crop", cv2.WINDOW_NORMAL)
            cv2.namedWindow("After Crop", cv2.WINDOW_NORMAL)

            cv2.imshow("Before Crop", marked)
            cv2.imshow("After Crop", cropped)
            logging.info(f"按任意键继续...")
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        return cropped

    def compare_pictures(self, pictures1, pictures2, result_path='result.png'):
        """比较两张图片并标记差异区域"""
        if not os.path.exists(pictures1):
            logging.error(f"图片 {pictures1} 不存在")
            return -1
        if not os.path.exists(pictures2):
            logging.error(f"图片 {pictures2} 不存在")
            return -1

        # 加载图片
        img1, img2 = self.load_images(pictures1, pictures2)
        if img1 is None or img2 is None:
            return -1

        # 动态裁剪顶部状态栏和底部导航栏
        img1 = self.crop_status_and_navigation(img1)
        img2 = self.crop_status_and_navigation(img2)
        if img1 is None or img2 is None:
            logging.error("裁剪后图片为空")
            return -1

        original_img2 = img2.copy()

        # 模板匹配（如果图片有偏移，尝试对齐）
        region_from_full_image = self.template_matching(img1, img2)
        crop_offset_x, crop_offset_y = 0, 0

        if isinstance(region_from_full_image, int):
            # 模板匹配失败，直接使用原图
            img1 = self._crop_border(img1)
            img2 = self._crop_border(img2)
        else:
            # 模板匹配成功，使用匹配区域
            img1 = self._crop_border(img1)
            img2 = self._crop_border(region_from_full_image)
            top_left = cv2.minMaxLoc(cv2.matchTemplate(img1, img2, cv2.TM_CCOEFF_NORMED))[3]
            crop_offset_x, crop_offset_y = top_left[0], top_left[1]

        # 统一尺寸（确保两张图片大小一致）
        if img1.shape != img2.shape:
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]), interpolation=cv2.INTER_AREA)

        # 计算差异并标记
        thresh = self.calculate_image_difference(img1, img2)
        if thresh is None or isinstance(thresh, int):
            return -1

        try:
            # 查找差异轮廓并标记
            cnts, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            diff_found = False
            for c in cnts:
                if cv2.contourArea(c) < 500:  # 过滤小面积噪点
                    continue
                approx = cv2.approxPolyDP(c, 0.01 * cv2.arcLength(c, True), True)
                x, y, w, h = cv2.boundingRect(approx)
                # 映射回原始图片坐标
                x += crop_offset_x
                y += crop_offset_y
                if len(original_img2.shape) == 2:
                    original_img2 = cv2.cvtColor(original_img2, cv2.COLOR_GRAY2BGR)
                cv2.rectangle(original_img2, (x, y), (x + w, y + h), (0, 0, 255), 2)
                diff_found = True

            if diff_found:
                logging.info("检测到差异区域，已标记")
            else:
                logging.info("页面无差异")

            # 确保保存路径存在
            result_dir = os.path.dirname(result_path)
            if not os.path.exists(result_dir):
                os.makedirs(result_dir, exist_ok=True)

            # 检查文件扩展名
            valid_extensions = ['.png', '.jpg', '.jpeg']
            ext = os.path.splitext(result_path)[1].lower()
            if ext not in valid_extensions:
                result_path = os.path.splitext(result_path)[0] + '.png'

            # 保存结果图片
            cv2.imwrite(result_path, original_img2)
            return 0
        except Exception as e:
            logging.error(f"标记差异失败: {e}")
            return -1

    def load_images(self, path1, path2):
        """加载两张图片并转换为BGR格式"""
        try:
            img1 = io.imread(path1)
            img2 = io.imread(path2)
            if img1 is None or img2 is None:
                raise FileNotFoundError("图片读取为空")
            img1 = cv2.cvtColor(img1, cv2.COLOR_RGBA2BGRA)
            img2 = cv2.cvtColor(img2, cv2.COLOR_RGBA2BGRA)

            # 打印图片尺寸（用于调试）
            logging.info(f"图片1尺寸: {img1.shape[1]}x{img1.shape[0]}")
            logging.info(f"图片2尺寸: {img2.shape[1]}x{img2.shape[0]}")

            return img1, img2
        except Exception as e:
            logging.error(f"加载图片失败: {e}")
            return None, None

    def template_matching(self, img1, img2):
        """使用模板匹配找到两张图片的最佳匹配区域"""
        try:
            if img1.shape[0] > img2.shape[0] or img1.shape[1] > img2.shape[1]:
                logging.error("模板图尺寸大于原图")
                return -1
            result = cv2.matchTemplate(img1, img2, cv2.TM_CCOEFF_NORMED)
            max_val = cv2.minMaxLoc(result)[1]
            if max_val < 0.8:
                logging.info("模板匹配度不足")
                return 0
            top_left = cv2.minMaxLoc(result)[3]
            h, w, _ = img1.shape
            bottom_right = (min(top_left[0] + w, img2.shape[1]), min(top_left[1] + h, img2.shape[0]))
            region = img2[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]]
            return cv2.resize(region, (w, h)) if region.shape != img1.shape else region
        except Exception as e:
            logging.error(f"模板匹配失败: {e}")
            return -1

    def calculate_image_difference(self, img1, img2):
        """计算两张图片的差异图"""
        try:
            diff = cv2.absdiff(img1, img2)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        except Exception as e:
            logging.error(f"计算差异失败: {e}")
            return -1

    def _crop_border(self, image, border=6):
        """裁剪图片边缘（去除可能的干扰）"""
        h, w, _ = image.shape
        if h > 2 * border and w > 2 * border:
            return image[border:h - border, border:w - border]
        return image

    def screenshot(self, screenshot_route, screenshot_name):
        """截取当前页面并保存"""
        if not screenshot_route:
            logging.error("截图路径为空")
            return None
        try:
            time.sleep(1)  # 等待页面加载完成
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
    # 替换为实际图片路径
    pic1 = os.path.join(script_dir, "Page/7/Notes_home/Associated Notes.png")
    pic2 = os.path.join(script_dir, "Page_screenshot/7/Notes_home/Associated Notes.png")
    result_path = os.path.join(script_dir, "exception_page/result.png")

    comparator = OpenCV()

    # 运行图片比较
    result = comparator.compare_pictures(pic1, pic2, result_path)
    if result == 0:
        logging.info(f"图片比较完成，结果已保存至: {result_path}")
    else:
        logging.error("图片比较失败")