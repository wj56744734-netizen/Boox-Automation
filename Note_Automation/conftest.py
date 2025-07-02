import allure
from selenium.common import TimeoutException, NoSuchElementException
from functools import wraps
from Note_Automation.Note_Class.Note_class import Operation_method
import pytest
import subprocess
import logging
import re
import time
from Note_Automation.config import get_device_info


# --------------------- pytest配置 ---------------------
def pytest_configure(config):
    """注册测试标记并禁用根日志器处理器"""
    config.addinivalue_line("markers", "abroad: 海外设备相关的测试用例")
    config.addinivalue_line("markers", "china: 国内设备相关的测试用例")
    config.addinivalue_line("markers", "test: 测试用例")

    # 禁用根日志器的所有处理器，解决重复日志问题
    root_logger = logging.getLogger()
    config._original_handlers = root_logger.handlers[:]  # 保存原始处理器
    root_logger.handlers = []  # 清空所有处理器


def pytest_unconfigure(config):
    """测试结束后恢复原始日志配置"""
    root_logger = logging.getLogger()
    root_logger.handlers = config._original_handlers  # 恢复原始处理器


def pytest_sessionstart(session):
    """测试会话开始前禁用第三方库日志（避免干扰）"""
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('appium').setLevel(logging.WARNING)


# --------------------- 测试标记装饰器 ---------------------
def note_mark_china(title):
    """国内设备测试用例标记装饰器"""

    def decorator(func):
        func = pytest.mark.abroad(func)
        func = pytest.mark.china(func)
        func = allure.title(title)(func)
        func = allure.step(title)(func)
        return func

    return decorator

def note_mark_abroad(title):
    """海外设备测试用例标记装饰器"""

    def decorator(func):
        func = pytest.mark.china(func)
        func = allure.title(title)(func)
        func = allure.step(title)(func)
        return func

    return decorator

def note_mark_increment(title):
    """海外设备测试用例标记装饰器"""

    def decorator(func):
        func = pytest.mark.increment(func)
        func = pytest.mark.full_amount(func)
        func = allure.title(title)(func)
        func = allure.step(title)(func)
        return func

    return decorator

def note_mark_full_amount(title):
    """海外设备测试用例标记装饰器"""

    def decorator(func):
        func = pytest.mark.full_amount(func)
        func = allure.title(title)(func)
        func = allure.step(title)(func)
        return func

    return decorator




# --------------------- 异常处理装饰器 ---------------------
def handle_errors(func):
    """统一异常处理装饰器"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except NoSuchElementException as e:
            logging.error(f"元素未找到: {e}")
            pytest.fail(f"测试失败: 元素未找到")
        except TimeoutException as e:
            logging.error(f"操作超时: {e}")
            pytest.fail(f"测试失败: 操作超时")
        except Exception as e:
            logging.error(f"未知错误: {e}")
            pytest.fail(f"测试失败: 未知错误")

    return wrapper


# --------------------- 设备信息获取 ---------------------
def get_wifi():
    """检查并显示Wi-Fi连接状态"""
    try:
        result = subprocess.run(
            ['adb', 'shell', 'dumpsys', 'connectivity'],
            capture_output=True,
            text=True
        )
        output = result.stdout

        wifi_info = re.search(r'NetworkAgentInfo\{.*?ni\{WIFI CONNECTED.*?\}.*?TransportInfo: <(.*?)>', output,
                              re.DOTALL)
        if not wifi_info:
            logging.info(f"Wi-Fi状态: 未连接 ")
            raise SystemExit(f"请连接Wi-Fi后！！！ 开始测试")

        transport_info = wifi_info.group(1)
        ssid = re.search(r'SSID: "([^"]+)"', transport_info).group(1) or "未知"
        ip = re.search(r'IP: /([^,]+)', transport_info).group(1) or "未分配"
        rssi = re.search(r'RSSI: (-?\d+)', transport_info).group(1) or "未知"
        link_speed = re.search(r'Link speed: (\d+Mbps)', transport_info).group(1) or "未知"

        logging.info(f"Wi-Fi状态: 已连接")
        logging.info(f"  SSID: {ssid}")
        logging.info(f"  IP地址: {ip}")
        logging.info(f"  信号强度: {rssi} dBm")
        logging.info(f"  连接速度: {link_speed}")

        if rssi != "未知":
            rssi_value = int(rssi)
            quality = " 优秀 " if rssi_value >= -50 else " 良好" if rssi_value >= -70 else " 一般 "
            logging.info(f"Wi-Fi信号质量: {quality}")

        return {"connected": True, "ssid": ssid, "ip": ip, "rssi": rssi, "link_speed": link_speed}

    except Exception as e:
        logging.error(f"检查Wi-Fi状态时出错: {e}")
        return {"connected": False}


def get_device_memory_info():
    """获取设备内存信息"""
    result = subprocess.run(
        ['adb', 'shell', 'cat /proc/meminfo'],
        capture_output=True,
        text=True
    )
    output = result.stdout

    mem_total = re.search(r'MemTotal:\s+(\d+)', output).group(1) if re.search(r'MemTotal:\s+(\d+)', output) else "未知"
    mem_free = re.search(r'MemFree:\s+(\d+)', output).group(1) if re.search(r'MemFree:\s+(\d+)', output) else "未知"
    mem_available = re.search(r'MemAvailable:\s+(\d+)', output).group(1) if re.search(r'MemAvailable:\s+(\d+)',
                                                                                      output) else "未知"

    mem_total_mb = round(int(mem_total) / (1024 * 1024), 2) if mem_total else 0
    mem_free_mb = round(int(mem_free) / (1024 * 1024), 2) if mem_free != "未知" else "未知"
    mem_available_mb = round(int(mem_available) / (1024 * 1024), 2) if mem_available != "未知" else "未知"

    logging.info(f"  总内存: {mem_total_mb}GB")
    logging.info(f"  空闲内存: {mem_free_mb}GB")
    logging.info(f"  可用内存: {mem_available_mb}GB")

    return {"total": f"{mem_total_mb} MB", "free": f"{mem_free_mb} MB", "available": f"{mem_available_mb} MB"}


def get_device_storage_info():
    """获取设备存储信息"""
    result = subprocess.run(
        ['adb', 'shell', 'df -h /sdcard'],
        capture_output=True,
        text=True
    )
    output = result.stdout

    if len(output.strip().split('\n')) > 1:
        parts = output.strip().split('\n')[1].split()
        total, used, available, percent = parts[1], parts[2], parts[3], parts[4]
        logging.info(f"  总容量: {total}B")
        logging.info(f"  已使用: {used}B ({percent})")
        logging.info(f"  可用空间: {available}B")
        return {"total": total, "used": used, "available": available, "percent_used": percent}
    logging.error("无法获取存储信息")
    return {"error": "无法获取存储信息"}


# --------------------- 设备数据清理 ---------------------
def adb_clean_note():
    """根据设备类型清理应用数据"""
    adb_commands_reader = [
        "adb shell pm clear com.onyx.android.note",
        "adb shell pm clear com.onyx.android.ksync",
        "adb shell pm clear com.onyx"
    ]
    adb_commands_tablet = [
        "adb shell pm clear com.onyx.android.note",
        "adb shell pm clear com.onyx.android.ksync"
    ]

    device_info = get_device_info()
    if device_info:
        device_name = device_info.get('device_name')
        device_region = device_info.get('device_region')
        adb_commands = adb_commands_tablet if device_region == "平板" else adb_commands_reader

        for command in adb_commands:
            try:
                with subprocess.Popen(
                        command, shell=True, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, bufsize=1
                ) as process:
                    stdout, stderr = process.communicate()
                    if process.returncode != 0:
                        logging.critical(f"执行 {command} 命令失败，返回码: {process.returncode}，错误信息: {stderr}")
                        return False
                    logging.info(f"{device_name}设备，测试前数据清理完毕")
            except Exception as e:
                logging.critical(f"执行命令时发生异常: {str(e)}")


# --------------------- 设备基础信息 ---------------------
def basic_device_information():
    """打印设备基础信息"""
    device_info = get_device_info()
    if device_info:
        logging.info(f"设备型号：{device_info.get('device_name')}")
        logging.info(f"设备平台：{device_info.get('device_platform')}")
        logging.info(f"设备区域：{device_info.get('device_region')}")
        logging.info(f"设备类型：{device_info.get('devices_reader')}")
        logging.info(f"设备尺寸：{device_info.get('device_size')}寸")
        logging.info(f"设备显示：{device_info.get('driver_colour')}")
        logging.info(f"设备分辨率：{device_info.get('filtered_size')}")
        logging.info(f"版本信息：{device_info.get('version_info')}")
        logging.info(f"构建类型：{device_info.get('build_type')}")
        logging.info(f"系统版本信息：{device_info.get('build_date_time')}")


# --------------------- 测试初始化fixture ---------------------
DEVICE_INFO_PRINTED = False


@pytest.fixture(scope='function', autouse=False)
def note_test_initial():
    """测试初始化fixture，包含设备信息和环境准备"""
    from Note_Automation.config import driver
    method = Operation_method(driver)
    global DEVICE_INFO_PRINTED

    # 清理设备数据
    adb_clean_note()

    # 打印设备信息（仅首次）
    if not DEVICE_INFO_PRINTED:
        logging.info("===== 设备基础信息 =====")
        basic_device_information()
        DEVICE_INFO_PRINTED = True

    logging.info(" ===== 系统信息 ===== ")
    time.sleep(3)

    # 记录内存和存储信息
    logging.info(f"【内存信息】")
    get_device_memory_info()
    logging.info(f"【存储信息】")
    get_device_storage_info()

    # 启动应用
    driver.press_keycode(3)  # HOME键
    start_time = time.time()
    timeout = 30
    while time.time() - start_time < timeout:
        if method.xpath_text_click("笔记", None):
            logging.info("笔记应用启动成功")
            break
        logging.info("正在加载应用...")
        time.sleep(2)
    else:
        pytest.fail("笔记应用启动超时")

    yield  # 测试执行点

    # 测试后返回主页
    driver.press_keycode(3)
    logging.info("测试完成，返回主页")
    