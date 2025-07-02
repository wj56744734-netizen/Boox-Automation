from datetime import datetime
from Note_Automation.config import driver
import logging
import pytest
import subprocess
from Note_Automation.conftest import get_device_info
import os

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

current_time = datetime.now().strftime("%Y%m%d%H%M%S")
results_dir = f"Test_report/Test_report/Test_{current_time}"
report_dir = f"Test_report/Test_report_html/Test_html_{current_time}"


def note_test_report(platform, test_scope="full"):
    """
    执行测试并生成报告

    Args:
        platform: 测试平台标识（china/abroad）
        test_scope: 测试范围，full=全量测试，incremental=增量测试
    """
    try:
        # 根据测试范围设置标记表达式
        if test_scope == "incremental":
            # 修改标记表达式，匹配实际的测试用例标记
            marker_expr = f"{platform} and increment"
        else:
            marker_expr = f"{platform} and full_amount"

        pytest_args = [
            "-s", "-v",
            "-m", marker_expr,
            "--reruns", "2",
            f"--alluredir={results_dir}"
        ]

        print(f"执行 {test_scope} 测试，平台: {platform}")
        pytest.main(pytest_args)

        # 生成Allure报告
        os.system(f"allure generate {results_dir} -o {report_dir} -c")

        # 仅在全量测试时打开报告
        # if test_scope == "full":
        os.system(f"allure open {report_dir}")

        driver.quit()
    except Exception as e:
        print(f"执行过程中出现异常: {e}")


if __name__ == '__main__':
    device_info = get_device_info()
    device_region = device_info.get('device_region')
    device_name = device_info.get('device_name')
    device_platform = device_info.get('device_platform')
    devices_reader = device_info.get('devices_reader')
    driver_colour = device_info.get('driver_colour')
    device_size = device_info.get('device_size')
    filtered_size = device_info.get('filtered_size')

    print("测试设备型号:", device_name)
    print("测试设备分辨率:", filtered_size)
    print("测试设备区域:", device_platform)
    print("测试设备平台:", device_region)
    print("测试设备类型：", devices_reader)
    print("测试设备尺寸:", device_size)
    print("测试设备显示:", driver_colour)

    # 控制执行全量测试还是增量测试
    # 可通过环境变量或命令行参数传入，这里简化为硬编码
    RUN_INCREMENTAL = True  # 设置为True则执行增量测试

    test_scope = "incremental" if RUN_INCREMENTAL else "full"

    if device_region == "国内":
        note_test_report("china", test_scope)
    else:
        note_test_report("abroad", test_scope)