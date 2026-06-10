import logging
import sys
import os
import re
import fnmatch

# 关键：非 TTY 环境下强制 stdout 行缓冲，实现日志实时输出
sys.stdout.reconfigure(line_buffering=True)

from boox_automation.ui_ops.operations import Operation_method
from boox_automation.devices.info import Device_basic_information
from boox_automation.driver import driver, ensure_driver_alive
from boox_automation.core.health import ensure_adb_device_ready, run_adb_command_with_retry
import allure
import pytest
import time
from selenium.webdriver.common.by import By


def _compact_exc_text(exc):
    text = str(exc) if exc is not None else ""
    return text.split("Stacktrace:")[0].strip().replace("\n", " ")


# --------------------- 用例过滤工具 ---------------------
def _parse_deselect_patterns(raw):
    """解析忽略用例配置（支持逗号/分号/换行分隔）"""
    if not raw:
        return []
    return [item.strip() for item in re.split(r"[,\n;]+", raw) if item.strip()]


def _collect_deselect_patterns(config):
    """汇总环境变量和命令行参数中的忽略用例模式"""
    env_patterns = _parse_deselect_patterns(os.getenv("NOTE_DESELECT_NODEIDS", ""))
    cli_patterns = config.getoption("note_deselect") or []
    # 去重并保持顺序
    merged = []
    for pattern in env_patterns + cli_patterns:
        if pattern not in merged:
            merged.append(pattern)
    return merged


def _match_deselect_pattern(nodeid, pattern):
    """兼容不同 rootdir 下的 nodeid 表达差异"""
    if not pattern:
        return False
    if (
        pattern == nodeid or
        nodeid.startswith(pattern) or
        nodeid.endswith(pattern) or
        fnmatch.fnmatch(nodeid, pattern)
    ):
        return True

    # 常见差异：是否包含 "boox_automation/" 前缀
    normalized_nodeid = nodeid.removeprefix("boox_automation/")
    normalized_pattern = pattern.removeprefix("boox_automation/")
    if (
        normalized_pattern == normalized_nodeid or
        normalized_nodeid.startswith(normalized_pattern) or
        normalized_nodeid.endswith(normalized_pattern) or
        fnmatch.fnmatch(normalized_nodeid, normalized_pattern)
    ):
        return True
    return False


# --------------------- pytest配置 ---------------------
def pytest_addoption(parser):
    """注册项目自定义参数"""
    parser.addoption(
        "--note-deselect",
        action="append",
        default=[],
        help="忽略指定测试用例（支持 nodeid 或 fnmatch 模式，可重复传入）"
    )


def pytest_configure(config):
    """注册测试标记并配置日志"""
    config.addinivalue_line("markers", "abroad: 海外设备相关的测试用例")
    config.addinivalue_line("markers", "china: 国内设备相关的测试用例")
    config.addinivalue_line("markers", "test: 测试用例")
    config.addinivalue_line("markers", "increment: 增量测试用例")
    config.addinivalue_line("markers", "full_amount: 全量测试用例")

    # 配置日志级别（由 pytest.ini 的 log_cli 统一管理输出）
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # 清除已有的 handler（避免重复输出）
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    # 不要在这里添加 StreamHandler！pytest 的 log_cli 会自动捕获并实时输出

def pytest_collection_modifyitems(config, items):
    """统一过滤指定用例（兼容直接 pytest 与报告入口）"""
    patterns = _collect_deselect_patterns(config)
    if not patterns:
        return

    selected = []
    deselected = []
    for item in items:
        nodeid = item.nodeid
        hit = any(_match_deselect_pattern(nodeid, pattern) for pattern in patterns)
        if hit:
            deselected.append(item)
        else:
            selected.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
        logging.warning(
            f"[IGNORE] 按规则忽略用例 {len(deselected)} 条，剩余 {len(selected)} 条；规则：{patterns}"
        )


def _resolve_session_path(raw_path, session):
    """把命令行/nodeid 中的路径解析为磁盘上的真实路径。"""
    if os.path.isabs(raw_path):
        return raw_path if os.path.exists(raw_path) else None
    # 依次尝试 cwd / rootdir / rootdir 的父目录
    bases = [os.getcwd(), str(session.config.rootdir), str(session.config.rootpath.parent)]
    for base in bases:
        candidate = os.path.join(base, raw_path)
        if os.path.exists(candidate):
            return candidate
    return None


def _likely_needs_device(session):
    """判断本次 session 的目标路径里是否存在依赖 note_test_initial 的测试文件。"""
    args = session.config.args or [str(session.config.rootdir)]
    candidates = []
    for arg in args:
        # nodeid 形式：path::Class::test
        raw_path = arg.split("::", 1)[0]
        path = _resolve_session_path(raw_path, session)
        if path is None:
            continue
        if os.path.isfile(path):
            candidates.append(path)
        elif os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for f in files:
                    if f.endswith(".py") and f.startswith("test_"):
                        candidates.append(os.path.join(root, f))

    for p in candidates:
        try:
            with open(p, encoding="utf-8") as fh:
                if "note_test_initial" in fh.read():
                    return True
        except Exception:
            continue
    return False


def pytest_sessionstart(session):
    """会话开始：静音第三方日志 + 设备前置检查（无设备时干净退出）。"""
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
    logging.getLogger('appium').setLevel(logging.WARNING)

    # 仅在真正要执行用例时检查设备；--collect-only 不拦
    if getattr(session.config.option, "collectonly", False):
        return
    if not _likely_needs_device(session):
        return
    try:
        devices = Device_basic_information()
        device_id = devices.get_connected_device_ids()

        logging.info("=" * 60)
        logging.info("  笔记自动化测试")
        logging.info("=" * 60)

        devices.check_device_language(device_id)
        devices.get_wifi(device_id)

        # 验证设备型号是否在映射表中注册
        device_info = devices.get_device_info()
        if device_info is None:
            raise RuntimeError("设备型号未注册，请检查 devices/registry.py 中的 device_list 映射表")

        # 已禁用：不再强制要求设备预置测试文件目录
        # devices.check_test_files(device_id)

        logging.info("-" * 60)
    except RuntimeError as e:
        pytest.exit(
            f"前置检查失败 — {e}",
            returncode=1
        )


def pytest_sessionfinish(session, exitstatus):
    """测试会话结束后自动清理超期产物（仅保留最近 N 轮）"""
    try:
        from boox_automation.core.cleanup import cleanup_artifacts
        cleanup_artifacts()
    except Exception as e:
        logging.warning(f"自动清理产物失败: {e}")


# --------------------- 测试标记装饰器 ---------------------
def note_mark_china(title):
    """历史兼容：通用用例（同时打 china + abroad）"""

    def decorator(func):
        func = pytest.mark.abroad(func)
        func = pytest.mark.china(func)
        func = allure.title(title)(func)
        func = allure.step(title)(func)
        return func

    return decorator

def note_mark_abroad(title):
    """历史兼容：国内专属用例（名称保留，不改调用侧）"""

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

def adb_clean_note(device_id):
    """根据设备类型清理应用数据"""
    adb_commands_reader = [
        f'adb -s {device_id} shell pm clear com.onyx.android.note',
        f'adb -s {device_id} shell pm clear com.onyx.android.ksync',
        f'adb -s {device_id} shell pm clear com.onyx',
        f'adb -s {device_id} shell rm -rf /sdcard/note/*',
    ]
    adb_commands_tablet = [
        f'adb -s {device_id} shell pm clear com.onyx.android.note',
        f'adb -s {device_id} shell pm clear com.onyx.android.ksync',
        f'adb -s {device_id} shell pm clear com.onyx',
        f'adb -s {device_id} shell rm -rf /sdcard/note/*',
    ]
    devices = Device_basic_information()
    device_info = devices.get_device_info()

    if device_info:
        device_type = device_info.get('devices_reader')
        adb_commands = adb_commands_tablet if device_type == "平板" else adb_commands_reader

        try:
            ensure_adb_device_ready(device_id)
            for command in adb_commands:
                time.sleep(1)
                run_adb_command_with_retry(command)
        except Exception as e:
            logging.critical(f"执行命令时发生异常: {str(e)}")
            pytest.fail(f"清理设备数据失败: {str(e)}")

# --------------------- 测试初始化fixture ---------------------
DEVICE_INFO_PRINTED = False
_DRIVER_FAILURE_COUNT = 0
from boox_automation.core.config import driver_failure_threshold
_DRIVER_FAILURE_THRESHOLD = driver_failure_threshold()


@pytest.fixture(scope='function', autouse=False)
def note_test_initial():
    """测试初始化fixture，包含设备信息和环境准备"""
    global _DRIVER_FAILURE_COUNT
    devices = Device_basic_information()

    device_id = None
    device_error = None
    try:
        device_id = devices.get_connected_device_ids()
    except RuntimeError as e:
        device_error = str(e)
    if device_id is None:
        pytest.fail(f"未检测到已连接设备（{device_error}），请连接设备后再运行测试", pytrace=False)

    device_info = devices.get_device_info()

    # 默认值，避免未定义
    device_region = None
    version_info = None
    if device_info:
        device_region = device_info.get('device_region')
        version_info = device_info.get('version_info')

    global DEVICE_INFO_PRINTED

    # 清理设备数据
    adb_clean_note(device_id)

    # 启动测试前先探活 driver（带 session 重建），连续失败 N 次则终止 session
    try:
        ensure_driver_alive(reason="note_test_initial setup")
        _DRIVER_FAILURE_COUNT = 0  # 成功后重置计数器
    except Exception as e:
        _DRIVER_FAILURE_COUNT += 1
        if _DRIVER_FAILURE_COUNT >= _DRIVER_FAILURE_THRESHOLD:
            pytest.exit(
                f"Driver 连续 {_DRIVER_FAILURE_COUNT} 次重建失败，终止测试 session: {_compact_exc_text(e)}"
            )
        pytest.fail(str(e), pytrace=False)
    method = Operation_method(driver)
    from boox_automation.tests.helpers import Public_method
    public = Public_method()

    if not DEVICE_INFO_PRINTED:
        """"" 打印设备信息 """""
        devices.basic_device_information(device_id)
        DEVICE_INFO_PRINTED = True

    # 启动应用
    def press_home_with_recovery(stage):
        try:
            ensure_driver_alive(reason=f"{stage} HOME precheck")
            driver.press_keycode(3)  # HOME键
            return None
        except Exception as e:
            return f"{stage} 执行 HOME 失败：{_compact_exc_text(e)}"

    home_error = press_home_with_recovery("测试前")
    if home_error:
        pytest.fail(home_error, pytrace=False)
    from boox_automation.core.config import timeout_app_launch
    start_time = time.time()
    timeout = timeout_app_launch()
    while time.time() - start_time < timeout:

        if version_info is None:
            logging.warning("无法获取版本信息，跳过版本检查")
            version_str = None
        else:
            version_str = public.get_version(short=True)


        if device_region == "国内" and version_str == "4.2":
            try:
                ensure_driver_alive(reason="启动引导检查")
                start_buttons = driver.find_elements(By.XPATH, '//*[@text="开始使用"]')
                if start_buttons:
                    start_buttons[0].click()
            except Exception as e:
                logging.warning(f"启动引导检查失败，跳过开始使用点击：{e}")

        if method.xpath_text_click("笔记",should_click=False):
            logging.debug("笔记应用启动成功")
            break
        logging.info("正在加载应用...")
        time.sleep(2)
    else:
        pytest.fail("笔记应用启动超时")

    yield  # 测试执行点

    # 测试后返回主页
    teardown_home_error = press_home_with_recovery("测试后")
    if teardown_home_error:
        logging.warning(teardown_home_error)
    logging.debug("测试完成，返回主页")
