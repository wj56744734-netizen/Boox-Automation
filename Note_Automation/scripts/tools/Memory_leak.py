import subprocess
import re
import time
import logging
import sys
import threading
from collections import deque
import argparse
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)
logger = logging.getLogger("MemoryMonitor")


def convert_to_mb(size: float, unit: str) -> float:
    """将内存单位转换为MB"""
    unit = unit.upper()
    if unit == 'KB':
        return size / 1024.0
    elif unit == 'MB':
        return size
    elif unit == 'GB':
        return size * 1024.0
    return size / (1024 * 1024.0)  # 默认按字节处理


class GCMonitor:
    """GC日志监控器 - 完全重构版本"""

    def __init__(self, threshold_mb: float = 50.0):
        self.threshold = threshold_mb
        self.running = False
        self.process = None
        self.thread = None
        self.device_id = Device_basic_information().get_connected_device_ids()

    def start(self):
        """启动GC监控"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(
            target=self._monitor_gc_logs,
            daemon=True
        )
        self.thread.start()
        logger.info(f"GC监控已启动 (阈值: {self.threshold}MB)")

    def stop(self):
        """停止GC监控"""
        self.running = False
        if self.process and self.process.poll() is None:
            self.process.terminate()
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("GC监控已停止")

    def _monitor_gc_logs(self):
        """核心GC日志监控逻辑"""
        try:
            # 清除旧日志缓存
            subprocess.run(['adb', '-s', self.device_id, 'logcat', '-c'], check=True)

            # 启动logcat进程（使用原始格式，不限制缓冲区）
            self.process = subprocess.Popen(
                ['adb', '-s', self.device_id, 'logcat'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # 持续读取日志
            while self.running and self.process.poll() is None:
                line = self.process.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue

                self._process_gc_line(line.strip())

        except Exception as e:
            logger.error(f"GC监控错误: {e}")
        finally:
            if self.process and self.process.poll() is None:
                self.process.terminate()

    def _process_gc_line(self, line: str):
        """处理单行GC日志"""
        try:
            # 检查是否是GC日志
            if "GC freed" not in line:
                return

            # 调试用：打印原始日志
            logger.debug(f"原始GC日志: {line}")

            # 解析GC类型
            gc_type = "Unknown"
            if match := re.search(r'(\w+(?:\s+\w+)*)\s+GC', line):
                gc_type = match.group(1).strip()

            alloc_count_str = ""
            alloc_size_str = ""
            los_count_str = ""
            los_size_str = ""
            free_percent_str = ""
            used_mb_str = ""
            total_mb_str = ""

            if match := re.search(r'(\d+)\(([\d.]+)([KM]B)\)\s+AllocSpace', line):
                alloc_count_str = match.group(1)
                alloc_size_str = match.group(2) + match.group(3)

            if match := re.search(r'(\d+)\(([\d.]+)([KM]B)\)\s+LOS', line):
                los_count_str = match.group(1)
                los_size_str = match.group(2) + match.group(3)

            if match := re.search(r'(\d+)% free,\s+(\d+)MB/(\d+)MB', line):
                free_percent_str = match.group(1)
                used_mb_str = match.group(2)
                total_mb_str = match.group(3)

            # 打印GC事件
            logger.info("GC事件详情:")
            logger.info(f"  GC类型: {gc_type}")
            logger.info(
                f"  回收信息: 回收释放了（{alloc_count_str}个）({alloc_size_str})分配空间对象、{los_count_str}个({los_size_str})LOS对象")
            logger.info(f"  内存状态: 空闲 {free_percent_str}%，{used_mb_str}MB/{total_mb_str}MB")


            # 示例：如果之前逻辑是基于总回收内存大小判断，这里可先根据拆分字符串重新计算总回收内存大小再判断
            total_reclaimed_mb = 0.0
            if alloc_size_str.endswith('KB'):
                total_reclaimed_mb += float(alloc_size_str[: -2]) / 1024.0
            elif alloc_size_str.endswith('MB'):
                total_reclaimed_mb += float(alloc_size_str[: -2])

            if los_size_str.endswith('KB'):
                total_reclaimed_mb += float(los_size_str[: -2]) / 1024.0
            elif los_size_str.endswith('MB'):
                total_reclaimed_mb += float(los_size_str[: -2])

            if total_reclaimed_mb >= 100:
                logger.warning("⚠️ 大规模GC回收!")
                logger.warning(f"  类型: {gc_type}")
                logger.warning(
                    f"  回收信息: 回收释放了（{alloc_count_str}个）({alloc_size_str})分配空间对象、{los_count_str}个({los_size_str})LOS对象")
                logger.warning(f"  内存状态: 空闲 {free_percent_str}%，{used_mb_str}MB/{total_mb_str}MB")
                logger.warning(f"  总计回收: {total_reclaimed_mb:.1f} MB ")
                logger.warning(f"  日志: {line[:200]}...")
                logger.warning("⚠️ 超过100MB GC回收阈值，可能存在内存泄漏风险")

        except Exception as e:
            logger.error(f"处理GC日志失败: {e}")
            logger.error(f"日志行: {line}")


class MemoryMonitor:
    """内存监控主类"""

    def __init__(self, package_name=None, interval=5, max_samples=10,
                 threshold=0.7, gc_threshold=50.0):
        self.package_name = package_name or "com.onyx.android.note"
        self.device_id = Device_basic_information().get_connected_device_ids()
        self.interval = interval
        self.max_samples = max_samples
        self.threshold = threshold
        self.memory_history = deque(maxlen=max_samples)

        # 获取系统总内存
        self.total_memory_mb = self._get_total_memory()
        logger.info(f"系统总内存: {self.total_memory_mb:.2f} MB")
        logger.info(f"开始监控应用内存: {self.package_name}")

        # 启动GC监控
        self.gc_monitor = GCMonitor(gc_threshold)
        if gc_threshold > 0:
            self.gc_monitor.start()

    def _get_total_memory(self) -> float:
        """获取系统总内存(MB)"""
        try:
            result = subprocess.run(
                ['adb', '-s', self.device_id, 'shell', 'cat', '/proc/meminfo'],
                capture_output=True, text=True, check=True
            )
            if match := re.search(r'MemTotal:\s+(\d+)\s+kB', result.stdout):
                return int(match.group(1)) / 1024.0
            return 4096.0  # 默认值
        except Exception as e:
            logger.error(f"获取总内存失败: {e}")
            return 4096.0

    def get_process_memory(self) -> float:
        """获取进程内存使用量(MB)"""
        try:
            result = subprocess.run(
                ['adb', '-s', self.device_id, 'shell', 'dumpsys', 'meminfo', self.package_name],
                capture_output=True, text=True, check=True
            )
            if match := re.search(r'TOTAL\s+PSS:\s+(\d+)', result.stdout, re.IGNORECASE):
                return int(match.group(1)) / 1024.0
            if match := re.search(r'TOTAL\s+(\d+)', result.stdout):
                return int(match.group(1)) / 1024.0
            logger.warning("无法解析内存信息")
            return 0.0
        except Exception as e:
            logger.error(f"获取进程内存失败: {e}")
            return 0.0

    def monitor(self):
        """主监控循环"""
        try:
            while True:
                mem_usage = self.get_process_memory()
                usage_percent = (mem_usage / self.total_memory_mb) * 100

                logger.info(
                    f"应用内存: {mem_usage:.2f}MB ({usage_percent:.1f}%)"
                )

                self.memory_history.append(mem_usage)

                if self._check_memory_leak():
                    logger.error("⚠️ 检测到内存泄漏！")
                    exit()

                time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info("监控已停止")
            exit()
        except Exception as e:
            logger.error(f"监控错误: {e}")
            exit()
        finally:
            self.gc_monitor.stop()

    def _check_memory_leak(self) -> bool:
        """检查内存泄漏"""
        if len(self.memory_history) < self.max_samples:
            return False

        increases = [self.memory_history[i] - self.memory_history[i - 1]
                     for i in range(1, len(self.memory_history))]

        avg_increase = sum(increases) / len(increases)
        growth_rate = sum(1 for inc in increases if inc > 0) / len(increases)
        current_mb = self.memory_history[-1]
        current_percent = (current_mb / self.total_memory_mb) * 100

        leak_detected = False

        if growth_rate > self.threshold and avg_increase > 0:
            logger.warning(
                f"内存持续增长: 平均增长 {avg_increase:.2f}MB/次 "
                f"(趋势: {growth_rate:.1%})"
            )
            leak_detected = True

        if current_percent > 90:
            logger.warning(
                f"内存使用过高: {current_percent:.1f}% "
                f"({current_mb:.2f}/{self.total_memory_mb:.2f}MB)"
            )
            leak_detected = True

        return leak_detected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='内存泄漏监控工具')
    parser.add_argument('-p', '--package', type=str,
                        help='监控的应用包名', default="com.onyx.android.note")
    parser.add_argument('-i', '--interval', type=int, default=5,
                        help='采样间隔(秒)')
    parser.add_argument('-s', '--samples', type=int, default=10,
                        help='内存样本数')
    parser.add_argument('-t', '--threshold', type=float, default=0.7,
                        help='内存增长阈值(0-1)')
    parser.add_argument('-g', '--gc-threshold', type=float, default=50.0,
                        help='GC警告阈值(MB)')
    parser.add_argument('--debug', action='store_true',
                        help='启用调试模式')

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("调试模式已启用")

    try:
        monitor = MemoryMonitor(
            package_name=args.package,
            interval=args.interval,
            max_samples=args.samples,
            threshold=args.threshold,
            gc_threshold=args.gc_threshold
        )
        monitor.monitor()
    except Exception as e:
        logger.error(f"启动失败: {e}")
        sys.exit(1)
