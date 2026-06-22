import logging
import sys
import os
import re
import fnmatch

# 确保项目根目录在 sys.path 中（兼容 VS Code 等不以项目根为 cwd 的运行方式）
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 关键：非 TTY 环境下强制 stdout 行缓冲，实现日志实时输出
sys.stdout.reconfigure(line_buffering=True)

from boox_automation.devices.info import Device_basic_information
from boox_automation.driver import driver, ensure_driver_alive, init_driver
from boox_automation.core.health import ensure_adb_device_ready, run_adb_command_with_retry, ensure_device_awake
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
    config.addinivalue_line("markers", "test: 测试用例")
    config.addinivalue_line("markers", "cleanup_app_data: 测试前清理应用数据（pm clear）")
    config.addinivalue_line("markers", "cleanup_storage_files: 测试前清理存储文件（rm -rf）")

    # 配置日志级别（由 pytest.ini 的 log_cli 统一管理输出）
    # NOTE_LOG_LEVEL 环境变量可覆盖（调试时设为 DEBUG）
    log_level = os.getenv("NOTE_LOG_LEVEL", "INFO").upper()
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))
    # 清除已有的 handler（避免重复输出），加 NullHandler 防止 lastResort
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    root_logger.addHandler(logging.NullHandler())

    # 动态设置 allure 结果目录
    try:
        from boox_automation.core.paths import new_allure_results_dir
        config.option.allure_report_dir = str(new_allure_results_dir())
    except Exception:
        pass

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
            f"[筛选跳过] 按规则忽略用例 {len(deselected)} 条，剩余 {len(selected)} 条；规则：{patterns}"
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
                if "note_test_initial" in fh.read() or "note_perf_initial" in fh.read():
                    return True
        except Exception:
            continue
    return False


_SESSION_START = None


def pytest_sessionstart(session):
    """会话开始：静音第三方日志 + 设备前置检查（无设备时干净退出）。"""
    global _SESSION_START
    _SESSION_START = time.time()

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
        logging.info("  Boox 自动化测试 ")
        logging.info("=" * 60)

        devices.check_device_language(device_id)
        devices.get_wifi(device_id)

        # 验证设备型号是否在映射表中注册
        device_info = devices.get_device_info()
        if device_info is None:
            raise RuntimeError("设备型号未注册，请检查 devices/registry.py 中的 device_list 映射表")

        logging.info("-" * 60)
    except RuntimeError as e:
        pytest.exit(
            f"前置检查失败 — {e}",
            returncode=1
        )


def pytest_sessionfinish(session, exitstatus):
    """测试会话结束：推送飞书报告 + 清理超期产物"""
    global _SESSION_START

    # 1. 推送飞书报告
    try:
        _send_feishu_report(session)
    except Exception as e:
        logging.warning(f"飞书报告推送异常: {e}")

    # 2. 清理超期产物
    try:
        from boox_automation.core.cleanup import cleanup_artifacts
        cleanup_artifacts()
    except Exception as e:
        logging.warning(f"自动清理产物失败: {e}")


def _send_feishu_report(session) -> None:
    """收集测试结果并推送飞书报告。"""
    global _SESSION_START

    # 获取 terminalreporter 统计
    terminalreporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if terminalreporter is None:
        return
    stats = terminalreporter.stats

    passed = len(stats.get("passed", []))
    failed = len(stats.get("failed", []))
    skipped = len(stats.get("skipped", []))

    if passed + failed + skipped == 0:
        return

    from boox_automation.core.feishu_report import build_report_card, push_report
    from boox_automation.devices.info import Device_basic_information
    from boox_automation.core.config import test_modules as cfg_test_modules
    from boox_automation.engine.result_store import get_cases
    from boox_automation.core.html_reporter import build_case_report, save_report
    from boox_automation.core.feishu import upload_file_to_im, send_file_message
    from boox_automation.core.config import feishu_chat_id, feishu_report_enabled
    from pathlib import Path

    duration_sec = time.time() - _SESSION_START if _SESSION_START else 0
    failed_cases = _extract_case_titles(stats.get("failed", []), max_items=10)
    skipped_cases = _extract_skipped_cases(stats.get("skipped", []), max_items=10)
    modules = cfg_test_modules() or None

    device = {}
    try:
        dbi = Device_basic_information()
        device = dbi.get_device_info() or {}
    except Exception:
        pass

    card = build_report_card(
        passed=passed, failed=failed, skipped=skipped,
        duration_sec=duration_sec,
        modules=modules,
        failed_cases=failed_cases or None,
        skipped_cases=skipped_cases or None,
        device=device,
    )

    # ── 生成 HTML 报告 ──
    cases = get_cases()
    html_path = None
    if cases:
        try:
            html = build_case_report(
                cases=cases,
                device_info=device,
                session_start=_SESSION_START,
                modules=modules,
            )
            from boox_automation.core.paths import ARTIFACTS_ROOT
            report_dir = ARTIFACTS_ROOT / "reports"
            html_path = save_report(html, report_dir)
            logging.info(f"HTML 测试报告已生成: {html_path}")
        except Exception as e:
            logging.error(f"HTML 报告生成失败: {e}")

    # ── 推送飞书：卡片 + HTML 文件 ──
    push_report(card, html_path)


def _extract_case_titles(reports, max_items: int = 10) -> list[str]:
    """从测试报告中提取用例标题。"""
    titles = []
    for rep in reports[:max_items]:
        title = _parse_case_title(rep.nodeid)
        if title:
            titles.append(title)
    return titles


def _extract_skipped_cases(reports, max_items: int = 10) -> list[tuple[str, str]]:
    """从跳过报告中提取 (标题, 原因)。"""
    cases = []
    for rep in reports[:max_items]:
        title = _parse_case_title(rep.nodeid)
        reason = ""
        if hasattr(rep, "longrepr") and rep.longrepr:
            reason = str(rep.longrepr).split("\n")[0].strip()
            # 去掉 pytest.skip 前缀噪音
            for prefix in ("Skipped: ", "[SKIP] ", "skip "):
                if reason.lower().startswith(prefix.lower()):
                    reason = reason[len(prefix):]
        if title:
            cases.append((title, reason or "跳过"))
    return cases


def _parse_case_title(nodeid: str) -> str:
    """从 nodeid 提取用例标题。"""
    if "[[" in nodeid:
        return ""
    bracket = nodeid.rfind("[")
    if bracket < 0:
        parts = nodeid.split("::")
        return parts[-1] if len(parts) > 1 else nodeid
    inner = nodeid[bracket + 1:].rstrip("]")
    # 去掉行号前缀 R{数字}-
    import re
    inner = re.sub(r'^R\d+[-]', '', inner)
    return inner


def _run_adb_cleanup_commands(device_id, commands: list[str], label: str):
    """执行一组 ADB 清理命令。"""
    if not commands:
        return
    try:
        ensure_adb_device_ready(device_id)
        for command in commands:
            time.sleep(1)
            run_adb_command_with_retry(command)
    except Exception as e:
        logging.critical(f"{label}失败: {e}")
        pytest.fail(f"{label}失败: {e}")


def adb_clean_app_data(device_id):
    """清理应用数据（pm clear），由前置条件【清理应用数据】触发。"""
    from boox_automation.core.config import adb_cleanup_app_data_packages
    packages = adb_cleanup_app_data_packages()
    commands = [f'adb -s {device_id} shell pm clear {pkg}' for pkg in packages]
    _run_adb_cleanup_commands(device_id, commands, "清理应用数据")


def adb_clean_storage_files(device_id):
    """清理存储文件（rm -rf），由前置条件【清理存储文件】触发。"""
    from boox_automation.core.config import adb_cleanup_storage_paths
    paths = adb_cleanup_storage_paths()
    commands = [f'adb -s {device_id} shell rm -rf {path}' for path in paths]
    _run_adb_cleanup_commands(device_id, commands, "清理存储文件")

def _extract_major_minor(version: str) -> str:
    """从版本字符串提取主版本号，如 '4.2.1-rel' → '4.2'。"""
    import re
    m = re.match(r'\d+\.\d+', version)
    return m.group(0) if m else ""

# --------------------- 测试初始化fixture ---------------------
DEVICE_INFO_PRINTED = False
_DRIVER_FAILURE_COUNT = 0
from boox_automation.core.config import driver_failure_threshold
_DRIVER_FAILURE_THRESHOLD = driver_failure_threshold()


@pytest.fixture(scope='function', autouse=False)
def note_test_initial(request):
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

    # 按前置条件或 marker 决定是否清理（默认不清理）
    needs_clean_app_data = False
    needs_clean_storage = False
    case = None
    if hasattr(request.node, 'callspec') and request.node.callspec:
        case = request.node.callspec.params.get('case')
    if case is not None:
        from boox_automation.engine.parser import has_cleanup
        needs_clean_app_data = has_cleanup(case.preconditions, 'app_data')
        needs_clean_storage = has_cleanup(case.preconditions, 'storage_files')
    else:
        # 非 Excel 用例（如性能脚本）通过 marker 控制
        needs_clean_app_data = request.node.get_closest_marker('cleanup_app_data') is not None
        needs_clean_storage = request.node.get_closest_marker('cleanup_storage_files') is not None

    if needs_clean_app_data:
        adb_clean_app_data(device_id)
    if needs_clean_storage:
        adb_clean_storage_files(device_id)

    # 确保设备唤醒后再探活 driver
    ensure_device_awake(device_id)

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

    # UI 沉降等待（HOME 键后给桌面/应用切换留出渲染时间）
    time.sleep(2)

    # 4.2 国内设备：首次启动可能有"开始使用"引导按钮，尝试点击跳过
    _ver_short = _extract_major_minor(version_info) if version_info else ""
    if device_region == "国内" and _ver_short == "4.2":
        try:
            ensure_driver_alive(reason="启动引导检查")
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.wait import WebDriverWait
            try:
                btn = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@text="开始使用"]'))
                )
                btn.click()
            except Exception:
                pass  # 无启动引导按钮则跳过
        except Exception as e:
            logging.warning(f"启动引导检查失败，跳过开始使用点击：{e}")

    yield  # 测试执行点

    # 测试后返回主页
    teardown_home_error = press_home_with_recovery("测试后")
    if teardown_home_error:
        logging.warning(teardown_home_error)
    logging.debug("测试完成，返回主页")


@pytest.fixture(scope='function')
def note_perf_initial(request):
    """性能测试专用 fixture：轻量探活，无飞书依赖，无 HOME precheck。

    与 note_test_initial 的区别：
    - 不做 ensure_driver_alive 重试（失败直接 init_driver 重建一次）
    - 不打印设备信息
    - 不处理"开始使用"引导
    - teardown 不做探活，HOME 失败只 WARNING
    """
    devices = Device_basic_information()

    device_id = None
    device_error = None
    try:
        device_id = devices.get_connected_device_ids()
    except RuntimeError as e:
        device_error = str(e)
    if device_id is None:
        pytest.fail(f"未检测到已连接设备（{device_error}），请连接设备后再运行测试", pytrace=False)

    # 清理由 marker 控制
    needs_clean_app_data = request.node.get_closest_marker('cleanup_app_data') is not None
    needs_clean_storage = request.node.get_closest_marker('cleanup_storage_files') is not None

    if needs_clean_app_data:
        adb_clean_app_data(device_id)
    if needs_clean_storage:
        adb_clean_storage_files(device_id)

    ensure_device_awake(device_id)

    # 仅一次探活，失败直接重建（不重试）
    try:
        driver.current_package
    except Exception:
        real_driver = init_driver()
        driver.set_driver(real_driver)

    driver.press_keycode(3)
    time.sleep(2)

    yield

    # 轻量 teardown：HOME 失败不重试
    try:
        driver.press_keycode(3)
    except Exception:
        logging.warning("性能测试后 HOME 失败（设备可能已掉线），不重试")
