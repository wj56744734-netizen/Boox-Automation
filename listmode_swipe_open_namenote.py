import time
from appium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

desired_caps = {
    "platformName": "Android",
    "deviceName": "huawei",
    "appPackage": "com.onyx.galaxy.note",
    "appActivity": ".category.ui.NoteListActivity",
    "automationName": "UiAutomator2",
    "noReset": True,
    "newCommandTimeout": 300,
    "autoGrantPermissions": True,

}
driver = webdriver.Remote("http://127.0.0.1:4723/wd/hub", desired_caps)

def list_text_click(target_note,scroll_attempts=0, max_scroll_attempts=15,note_found=False):
    print("当前为列表模式")

    # 当前是列表模式
    while scroll_attempts < max_scroll_attempts:

        note_name = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.ID, "com.onyx.galaxy.note:id/tv_name")))

        for name in note_name:

            if name.text == target_note:
                name.click()
                print(f"已点击'{target_note}'的缩略图打开该笔记")
                note_found = True
                break

        if note_found:
            break

        # 未找到目标，执行滚动操作
        driver.swipe(scroll_start_x, scroll_start_y, scroll_start_x, scroll_end_y, 800)
        time.sleep(1)
        print(f"未找到目标笔记，执行滚动操作 ({scroll_attempts + 1}/{max_scroll_attempts})")
        scroll_attempts += 1

     # 检查是否找到目标笔记
    if not note_found:
        raise Exception(f"滚动{max_scroll_attempts}次后仍未找到目标笔记：{target_note}")

def cover_text_click(target_note,scroll_attempts=0,max_scroll_attempts=15, note_found=False):
    print("当前为封面模式")

    while scroll_attempts < max_scroll_attempts:

        note_name = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.ID, "com.onyx.galaxy.note:id/tv_name")))

        for index, name in enumerate(note_name, start=0):

            if name.text == target_note:
                element_index = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.ID, "com.onyx.galaxy.note:id/v_note_thumbnail_broder")))

                element_index[index].click()

                print(f"已点击'{target_note}'的缩略图打开该笔记")
                note_found = True
                break

        if note_found:
            break

        # 未找到目标，执行滚动操作
        driver.swipe(scroll_start_x, scroll_start_y, scroll_start_x, scroll_end_y, 800)
        time.sleep(1)
        print(f"未找到目标笔记，执行滚动操作 ({scroll_attempts + 1}/{max_scroll_attempts})")
        scroll_attempts += 1

    # 检查是否找到目标笔记
    if not note_found:
        raise Exception(f"滚动{max_scroll_attempts}次后仍未找到目标笔记：{target_note}")

try:
    # 等待笔记列表页面加载完成
    print("等待笔记列表页面加载...")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "android.widget.TextView"))
    )

    target_note = "入学指南"
    print(f"查找并打开'{target_note}'笔记...")

    list_name = True

    try:
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.ID, "com.onyx.galaxy.note:id/iv_option"))
        )
    except Exception:
        list_name = False

        print("完成判断")

    # 获取屏幕尺寸用于滚动
    size = driver.get_window_size()
    width = size['width']
    height = size['height']

    # 定义滚动区域（避免触发表头或底部操作栏）
    scroll_start_x = width * 0.5
    scroll_start_y = height * 0.8  # 起始点：屏幕80%高度处（偏下）
    scroll_end_y = height * 0.45  # 结束点：屏幕45%高度处（偏上）

    # 定义变量标记是否找到目标笔记
    note_found = False
    if list_name:
        list_text_click(target_note)
    else:
        cover_text_click(target_note)

    print("返回笔记首页...")
    # 等待并点击“返回保存”按钮
    save_btn = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "com.onyx.galaxy.note:id/iv_back"))
    )
    save_btn.click()

    time.sleep(3)
    print("成功返回笔记首页", end="\n\n")

except Exception as e:
    print(f"测试过程中发生错误: {e}")
    # 可添加截图或其他调试信息
finally:
    if driver:
        print("关闭 Appium 会话...")
        driver.quit()
        print("会话已关闭")


