from Note_Automation.Note_Class.Note_class import Operation_method
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information
from Note_Automation.config import driver
import allure
import pytest
import subprocess
import logging
import time


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


def pytest_sessionstart():
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

# --------------------- 设备数据清理 ---------------------
def adb_clean_note(device_id):
    """根据设备类型清理应用数据"""
    adb_commands_reader = [
        f"adb -s '{device_id}' shell pm clear com.onyx.android.note",
        f"adb -s '{device_id}' shell pm clear com.onyx.android.ksync",
        f"adb -s '{device_id}' shell pm clear com.onyx"
    ]
    adb_commands_tablet = [
        f"adb -s '{device_id}' shell pm clear com.onyx.android.note",
        f"adb -s '{device_id}' shell pm clear com.onyx.android.ksync",
        f"adb -s '{device_id}' shell pm clear com.onyx"
    ]
    devices = Device_basic_information()
    device_info = devices.get_device_info()

    if device_info:
        # device_name = device_info.get('device_name')
        device_type = device_info.get('devices_reader')
        adb_commands = adb_commands_tablet if device_type == "平板" else adb_commands_reader

        for command in adb_commands:
            time.sleep(1)
            try:
                with subprocess.Popen(
                        command, shell=True, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, bufsize=1
                ) as process:
                    stdout, stderr = process.communicate()
                    if process.returncode != 0:
                        logging.critical(f"执行 {command} 命令失败，返回码: {process.returncode}，错误信息: {stderr}")
                        pytest.fail(f"清理设备数据失败，命令: {command}")
                    # logging.debug(f"{device_name}设备，测试前数据清理完毕")
            except Exception as e:
                logging.critical(f"执行命令时发生异常: {str(e)}")

# --------------------- 测试初始化fixture ---------------------
DEVICE_INFO_PRINTED = False


@pytest.fixture(scope='function', autouse=False)
def note_test_initial():
    """测试初始化fixture，包含设备信息和环境准备"""
    devices = Device_basic_information()
    method = Operation_method(driver)
    global DEVICE_INFO_PRINTED

    device_id = devices.get_connected_device_ids()

    # 清理设备数据
    adb_clean_note(device_id)

    if not DEVICE_INFO_PRINTED:
        """"" 打印设备信息 """""
        devices.basic_device_information(device_id)
        DEVICE_INFO_PRINTED = True

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
