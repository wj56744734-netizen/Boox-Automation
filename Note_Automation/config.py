from appium import webdriver
from Note_Automation.Devices_list.Device_basic_information import Device_basic_information
from appium.options.android import UiAutomator2Options

# 初始化driver变量为None
driver = None

try:
    # 获取设备信息
    devices = Device_basic_information()
    device_info = devices.get_device_info()

    # 验证设备信息是否正确获取
    if not all(key in device_info for key in ['android_version', 'device_name', 'device_id']):
        raise ValueError("未能正确获取设备信息，请检查Device_basic_information类")

    android_version = device_info['android_version']
    device_name = device_info['device_name']
    device_id = device_info['device_id']

    # 创建选项对象
    options = UiAutomator2Options()

    # 配置Android设备参数
    options.load_capabilities({
        "platformName": "Android",
        "platformVersion": android_version,
        "deviceName": device_name,
        "udid": device_id,
        "automationName": "UiAutomator2",
        "newCommandTimeout": 600
    })

    # 初始化WebDriver - 明确只传递options参数
    driver = webdriver.Remote(
        command_executor="http://localhost:4723/wd/hub",
        options=options
    )

    # 设置隐式等待时间
    driver.implicitly_wait(10)
    print("Driver初始化成功")

except Exception as e:
    print(f"未知错误: {e}")
    # 打印详细的异常信息，帮助调试
    import traceback

    traceback.print_exc()
