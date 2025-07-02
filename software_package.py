import subprocess


def pip_import():
    # pytest - tui 是一个基于pytest的插件，它提供了一个文本用户界面（TUI），
    # 用于在运行测试时以交互方式查看测试进度、结果等信息，方便用户实时了解用例运行总数和运行情况。
    try:
        subprocess.run(["pip", "install", "pytest-tui"], check = True,
                                stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True)
    except subprocess.CalledProcessError as e:
        print(f"安装 pytest-tui 失败 {e}")

    # selenium 是一个用于Web应用程序测试的工具，版本4.9.0。
    # 它允许你通过编程方式控制浏览器，模拟用户操作，如点击按钮、填写表单等，常用于自动化测试Web应用。
    try:
        subprocess.run(["pip", "install", "selenium==4.9.0"])
    except subprocess.CalledProcessError as e:
        print(f"安装 selenium 失败 {e}")

    # allure - pytest 是一个与pytest集成的插件，版本2.12.0。
    # 它可以生成美观、详细且交互式的测试报告，方便团队成员查看测试结果和分析问题。
    try:
        subprocess.run(["pip", "install", "allure-pytest==2.12.0"])
    except subprocess.CalledProcessError as e:
        print(f"安装 allure-pytest 失败 {e}")

    # opencv - python 是OpenCV库的Python绑定，用于计算机视觉任务。
    # 它提供了各种图像处理和计算机视觉算法，如图像滤波、特征提取、目标检测等，常简称为cv2库。
    try:
        subprocess.run(["pip", "install", "opencv-python"])
    except subprocess.CalledProcessError as e:
        print(f"安装 opencv-python 失败 {e}")

    # scikit - image 是用于图像处理的Python库，它建立在SciPy之上，提供了大量简单而高效的图像处理算法和工具。
    # 可用于图像的读取、处理、分析和可视化等任务。
    try:
        subprocess.run(["pip", "install", "scikit-image"])
    except subprocess.CalledProcessError as e:
        print(f"安装 scikit-image 失败 {e}")

    # PyPDF2 是一个用于处理PDF文件的Python库。
    # 它可以实现诸如读取PDF内容、合并PDF文件、拆分PDF页面、添加水印等功能。
    try:
        subprocess.run(["pip", "install", "PyPDF2"])
    except subprocess.CalledProcessError as e:
        print(f"安装 PyPDF2 失败 {e}")

    # appium - python - client 是Appium的Python客户端库，版本2.9.0。
    # Appium是一个用于自动化移动应用测试的框架，此库允许Python开发者编写脚本来自动化测试移动应用（iOS或Android）。
    try:
        subprocess.run(["pip", "install", "appium-python-client==2.9.0"])
    except subprocess.CalledProcessError as e:
        print(f"安装 appium-python-client 失败 {e}")

    # pytest - rerunfailures 是pytest的插件，它允许在测试用例失败时自动重新运行。
    # 对于一些不稳定的测试用例（例如由于网络波动、资源竞争等原因导致偶尔失败的用例），可以使用该插件设置重试次数。
    try:
        subprocess.run(["pip", "install", "pytest-rerunfailures"])
    except subprocess.CalledProcessError as e:
        print(f"安装 pytest-rerunfailures {e}")


if __name__ == "__main__":
    pip_import()