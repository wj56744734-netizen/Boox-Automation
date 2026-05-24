from Note_Automation.config import driver
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information
from Note_Automation.framework.paths import new_allure_results_dir, new_allure_html_dir
from datetime import datetime
import subprocess
import re
import os


current_time = datetime.now().strftime("%Y%m%d%H%M%S")

results_dir = str(new_allure_results_dir(current_time))
report_dir = str(new_allure_html_dir(current_time))


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

    return full_output

def collect_tests_and_get_stats(args):
    """只运行 pytest 的收集阶段并获取测试统计信息"""
    collect_args = args + ["--collect-only"]

    print(f"正在收集测试用例: pytest {' '.join(collect_args)}")

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
            "-s", "-v",
            "-m", marker_expr,
            "--reruns", "2",
            f"--alluredir={results_dir}"
        ]

        collect_output = collect_tests_and_get_stats(pytest_args)
        stats = extract_test_stats(collect_output)


        print("\n========== 测试用例统计信息 ==========")

        print(f"执行 {test_scope} 用例测试")
        print(f"测试平台 {platform} 用例测试")

        print(f"收集的项目总数: {stats['collected']}")
        print(f"被筛选掉的项目数: {stats['deselected']}")
        print(f"最终选中的项目数: {stats['selected']}")
        print("=====================================\n")


        print("开始执行测试...\n")
        pytest_output = run_pytest_and_get_output(pytest_args)

        # 生成 Allure 报告
        print(f"生成 Allure 报告到目录: {report_dir}")
        os.system(f"allure generate {results_dir} -o {report_dir} -c")

        # 打开 Allure 报告
        print(f"打开 Allure 报告: {report_dir}")
        os.system(f"allure open {report_dir}")

        # 关闭驱动
        driver.quit()
    except Exception as e:
        print(f"执行过程中出现异常: {e}")

if __name__ == '__main__':
    print("开始执行测试脚本")
    devices = Device_basic_information()

    device_info = devices.get_device_info()

    device_region = device_info.get('device_region')

    RUN_INCREMENTAL = True  # 设置为True则执行增量测试
    test_scope = "incremental" if RUN_INCREMENTAL else "full"

    if device_region == "国内":

        note_test_report("china", test_scope)

    else:

        note_test_report("abroad", test_scope)

    print("测试脚本执行完毕")