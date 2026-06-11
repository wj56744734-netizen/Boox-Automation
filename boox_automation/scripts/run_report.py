from boox_automation.driver import driver
from boox_automation.devices.info import Device_basic_information
from boox_automation.core.paths import new_allure_results_dir, new_allure_html_dir
from datetime import datetime
from pathlib import Path
import subprocess
import re


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

current_time = datetime.now().strftime("%Y%m%d%H%M%S")

results_dir = str(new_allure_results_dir(current_time))
report_dir = str(new_allure_html_dir(current_time))


def _short(p: str) -> str:
    """将绝对路径转为相对于仓库根的短路径，失败则返回原路径。"""
    try:
        return str(Path(p).resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return p


def extract_test_stats(pytest_output):
    """从 pytest 输出中提取测试项目统计信息"""
    collected_pattern = r'collected (\d+) items'
    deselected_pattern = r'(\d+) deselected'
    selected_pattern = r'(\d+) selected'

    collected = 0
    deselected = 0
    selected = 0

    collected_match = re.search(collected_pattern, pytest_output)
    if collected_match:
        collected = int(collected_match.group(1))

    deselected_match = re.search(deselected_pattern, pytest_output)
    if deselected_match:
        deselected = int(deselected_match.group(1))

    selected_match = re.search(selected_pattern, pytest_output)
    if selected_match:
        selected = int(selected_match.group(1))

    return {
        'collected': collected,
        'deselected': deselected,
        'selected': selected
    }

def run_pytest_and_get_output(args):
    """运行 pytest 并实时捕获其输出"""
    process = subprocess.Popen(
        ['pytest'] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )

    output = []
    for line in iter(process.stdout.readline, ''):
        print(line, end='')  # 实时打印输出
        output.append(line)

    return_code = process.wait()
    full_output = ''.join(output)

    if return_code != 0:
        print(f"pytest 执行失败，返回码: {return_code}")

    return full_output, return_code

def collect_tests_and_get_stats(args):
    """只运行 pytest 的收集阶段并获取测试统计信息"""
    collect_args = args + ["--collect-only", "-q", "--no-header", "-o", "log_cli=false"]

    process = subprocess.Popen(
        ['pytest'] + collect_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )

    output = []
    for line in iter(process.stdout.readline, ''):
        if "collected" in line or "deselected" in line:
            print(line, end='')
        output.append(line)

    return_code = process.wait()
    full_output = ''.join(output)

    if return_code != 0:
        print(f"收集测试用例失败，返回码: {return_code}")

    return full_output

def note_test_report(platform,test_scope="full"):
    """执行测试并生成报告"""
    try:
        if test_scope == "incremental":
            marker_expr = f"{platform} and increment"
        else:
            marker_expr = f"{platform} and full_amount"

        pytest_args = [
            "-s", "-v", "--no-header",
            "-m", marker_expr,
            f"--alluredir={results_dir}"
        ]

        collect_output = collect_tests_and_get_stats(pytest_args)
        stats = extract_test_stats(collect_output)


        print(f"\n  测试用例: 共 {stats['collected']} 个 / 选中 {stats['selected']} 个 / 排除 {stats['deselected']} 个\n")


        print("开始执行测试...\n")
        pytest_output, return_code = run_pytest_and_get_output(pytest_args)

        # 生成 Allure 报告（无论测试成败都生成，失败时报告更关键）
        print(f"\npytest 返回码: {return_code}")
        print(f"生成 Allure 报告到目录: {_short(report_dir)}")
        subprocess.run(["allure", "generate", str(results_dir), "-o", str(report_dir), "-c"])

        # 打开 Allure 报告
        print(f"打开 Allure 报告: {_short(report_dir)}")
        subprocess.run(["allure", "open", str(report_dir)])

        # 关闭驱动
        driver.quit()
    except Exception as e:
        print(f"执行过程中出现异常: {e}")

if __name__ == '__main__':
    devices = Device_basic_information()
    device_id = devices.get_connected_device_ids(silent=True)

    # 仅获取设备区域，不触发完整设备信息日志（sessionstart 会统一打印）
    fingerprint = devices.get_device_fingerprint(device_id)
    if fingerprint:
        devices_name, _, _, _, _ = devices.parse_fingerprint(fingerprint)
        device_match = devices.match_device_info(devices_name)
        device_region = device_match.get('device_region') if device_match else '国内'
    else:
        print("前置检查失败 — 无法获取设备指纹信息")
        exit(1)

    if device_match is None:
        print("前置检查失败 — 设备型号未注册，请检查 device_list 映射表")
        exit(1)

    RUN_INCREMENTAL = True
    test_scope = "incremental" if RUN_INCREMENTAL else "full"
    platform = "china" if device_region == "国内" else "abroad"
    note_test_report(platform, test_scope)

    print("测试脚本执行完毕")