import logging
import subprocess
import sys
import os

# 统一日志格式：时间 | 级别 | 函数名 | 文件:行号 | 消息
LOG_FORMAT = '%(asctime)s [%(levelname)s] | %(funcName)s | %(filename)s:%(lineno)d | %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 配置 logging（与 conftest.py 保持一致）
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    stream=sys.stdout
)

from appium import webdriver
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information
from Note_Automation.framework.health import ensure_appium_server
from appium.options.android import UiAutomator2Options

class DriverProxy:
    """
    代理层：保证全项目通过 `from config import driver` 得到同一对象引用，
    底层 real driver 可在断连后热切换，避免导入绑定失效。
    """

    def __init__(self):
        self._driver = None

    def set_driver(self, real_driver):
        self._driver = real_driver

    def get_driver(self):
        return self._driver

    def clear_driver(self):
        self._driver = None

    def __bool__(self):
        return self._driver is not None

    def __getattr__(self, item):
        if self._driver is None:
            raise RuntimeError("Driver 尚未初始化，请先调用 init_driver()")
        return getattr(self._driver, item)


driver = DriverProxy()


def _compact_error_text(error_text):
    """压缩第三方异常文本，避免日志被超长堆栈淹没。"""
    if not error_text:
        return ""
    compact = str(error_text).split("Stacktrace:")[0].strip()
    compact = compact.replace("\n", " ").strip()
    return compact


def _friendly_driver_error(error_text):
    compact = _compact_error_text(error_text)
    lowered = compact.lower()
    if "Connection refused" in compact or "Max retries exceeded" in compact:
        return "Appium 未连接或不可用（已尝试自动连接），请确认 Appium Server 正常后再运行测试。"
    if (
        "could not proxy command to the remote server" in lowered
        or "socket hang up" in lowered
        or "the session identified by" in lowered
        or "nosuchdriverexception" in lowered
        or "cannot be proxied to uiautomator2 server" in lowered
        or "instrumentation process is not running" in lowered
    ):
        return "Appium 未连接或会话异常（已尝试自动连接），请先连接 Appium 后再开始测试。"
    if "UiAutomation not connected" in compact:
        return (
            "Driver 初始化失败：设备自动化通道未连接（UiAutomation not connected）。"
            "请重启目标设备的开发者选项/USB调试或重启 Appium 后重试。"
        )
    return f"Driver 初始化失败：{compact or error_text}"


def _build_driver_options():
    devices = Device_basic_information()
    device_info = devices.get_device_info()

    if device_info is None:
        device_id = devices.get_connected_device_ids()
        result = subprocess.run(
            ["adb", "-s", device_id, "shell", "getprop", "ro.product.model"],
            capture_output=True,
            text=True
        )
        raise ValueError(f"设备信息【 {result.stdout.strip()} 】获取结果为空，请检查Devices_list.py文件是否包含设备信息")

    if not all(key in device_info for key in ['android_version', 'device_name', 'device_id']):
        raise ValueError("未能正确获取设备信息，请检查Device_basic_information类")

    options = UiAutomator2Options()
    options.load_capabilities({
        "platformName": "Android",
        "deviceName": device_info['device_name'],
        "udid": device_info['device_id'],
        "automationName": "UiAutomator2",
        "newCommandTimeout": 3600,
        "adbExecTimeout": 120000,
    })
    return options


def init_driver(exit_on_fail=True):
    """初始化并绑定真实 driver 到代理层"""
    try:
        ensure_appium_server(auto_start=True)
        options = _build_driver_options()
        server_url = os.getenv(
            "APPIUM_SERVER_URL",
            f"http://{os.getenv('APPIUM_HOST', '127.0.0.1')}:{os.getenv('APPIUM_PORT', '4723')}"
        )
        real_driver = webdriver.Remote(command_executor=server_url, options=options)
        real_driver.implicitly_wait(10)
        driver.set_driver(real_driver)
        logging.info("Driver初始化成功")
        return real_driver
    except Exception as e:
        friendly_msg = _friendly_driver_error(str(e))
        logging.error(friendly_msg)
        if exit_on_fail:
            sys.exit(friendly_msg)
        raise RuntimeError(friendly_msg) from e


def ensure_driver_alive(reason=None):
    """探活 driver；未初始化时先尝试初始化，失败时直接抛错。"""
    real_driver = driver.get_driver()
    try:
        if real_driver is None:
            real_driver = init_driver(exit_on_fail=False)
        # 触发多次轻量请求验证会话可用性（覆盖 UiAutomator2 掉线场景）
        _ = real_driver.current_package
        _ = real_driver.current_activity
        _ = real_driver.get_window_size()
        return real_driver
    except Exception as e:
        friendly_msg = _friendly_driver_error(str(e))
        detail = f"{friendly_msg}（reason={reason}）" if reason else friendly_msg
        logging.warning(f"Driver 探活失败：{detail}")
        raise RuntimeError(friendly_msg) from None

