"""更新元素表所有 sheet 注释行为完整使用说明（6 列元素 + 5 列预期结果）。"""
from boox_automation.core.feishu import get_sheet_id, write_sheet_values
from boox_automation.core.config import feishu_elements_token

token = feishu_elements_token()
element_sheets = ["手写笔记", "笔记首页", "无边笔记", "会议笔记", "文本笔记", "其他"]

new_comments = [
    # 1. 元素标识
    '\n'.join([
        '元素唯一标识，格式: 页面名.元素名',
        '• 页面名 = 当前 Sheet 名（如 笔记首页、手写笔记）',
        '• 元素名 = 描述用途的名称（如 创建笔记、退出按钮）',
        '• 全局唯一不可重复，否则后加载的覆盖先加载的',
        '示例: 笔记首页.创建手写笔记',
    ]),
    # 2. 匹配文本
    '\n'.join([
        '测试步骤中【】内的匹配文字，用于自动关联步骤与元素',
        '• 必与步骤中的【】文字完全一致（含标点、空格）',
        '• 同页面 match 不可重复，重复时靠页面上下文自动消歧',
        '• 不填时自动用「定位方式」的纯文本值做匹配',
        '• XPath 型定位方式必须填此字段',
        '示例: 手写笔记（对应步骤「点击创建菜单中【手写笔记】」）',
    ]),
    # 3. 定位方式
    '\n'.join([
        '元素在界面上的定位表达式，支持 XPath 和纯文本两种写法:',
        '1) XPath 精确定位（推荐）:',
        '   • //*[@resource-id="com.onyx:id/xxx"]           ← ID 定位',
        '   • //*[@text="xxx"]                              ← 文本定位',
        '   • //android.widget.TextView[@text="xxx"]        ← 类型+文本',
        '   • //*[contains(@text, "xxx")]                   ← 模糊匹配',
        '2) 纯文本: 直接写界面上的文字，程序自动生成 XPath',
        '   • 简单但有歧义风险（同文字多元素时取第一个）',
        '',
        '支持多设备「键：」分块格式（和预期结果 C 列统一）:',
        '  默认 XPath（所有设备兜底，必填，放在最前面）',
        '',
        '  阅读器：',
        '  //*[@resource-id="com.onyx:id/btn_eink"]',
        '',
        '  海外：',
        '  //*[@text="Note"]',
        '',
        '支持的键: 国内 海外 全球 平板 阅读器 6 7.8 10.3 13.3 版本号',
        '匹配逻辑: 条件匹配最多的优先，无匹配回退默认',
        '仅有条件块无默认 → WARNING',
        '',
        '常用 resource-id 前缀: com.onyx.android.note:id/ 或 com.onyx:id/',
    ]),
    # 4. 操作类型
    '\n'.join([
        '元素的操作语义，决定步骤执行时的具体行为（填写中文）:',
        '  点击         = 点击元素（默认值，按钮/菜单项/图标，可省略）',
        '  输入         = 输入文本（输入框）',
        '  长按         = 长按元素（列表项长按弹出菜单）',
        '  校验toast    = 校验 Toast 提示（验证短暂弹出的消息）',
        '  点击坐标     = 按屏幕比例坐标点击（locator 填 x,y 如 0.5,0.3）',
        '  长按坐标     = 按屏幕比例坐标长按（locator 同上）',
        '• 不填自动推断: 含「toast/提示」→校验toast，其他→点击',
        '• 英文值兼容: click/input/long_press/assert_toast 仍可用',
        '• 页面/弹窗验证统一由 I 列预期结果完成',
    ]),
    # 5. 用途说明
    '\n'.join([
        '人类可读的元素描述，纯备注字段，不影响执行:',
        '• 出现在失败日志: 元素用途: xxx',
        '• 出现在 Allure 截图标题',
        '• 出现在步骤日志: 点击「xxx」',
        '建议简短描述在业务流程中的角色',
        '示例: 退出手写笔记（手写笔记编辑页的返回按钮）',
    ]),
    # 6. 序号
    '\n'.join([
        '同页面同 match 出现多个元素时的序号',
        '• 1 = 第一个匹配的元素，2 = 第二个，以此类推',
        '• 默认 0 或空 = 取第一个',
        '• 用于区分同文字、不同位置的多个元素',
        '示例: 笔记列表页有多个「更多」按钮，用 index=1,2,3 区分',
    ]),
]

for sheet_name in element_sheets:
    sid = get_sheet_id(token, sheet_name)
    write_sheet_values(token, sid, start_row=1, start_col=1, values=[new_comments])
    print(f"  OK {sheet_name}")

# 预期结果 sheet — 5 列格式 (A-E)
exp_comments = [
    # A: 元素标识
    '\n'.join([
        '预期结果唯一标识，格式: 页面.页面状态',
        '• 页面 = 所属页面名（如 笔记首页、手写笔记）',
        '• 状态 = 描述当前页面状态（如 引导页、创建页）',
        '• 全局唯一不可重复',
        '示例: 笔记首页.本地笔记引导',
    ]),
    # B: 匹配文本
    '\n'.join([
        '用例 K 列步骤中【】内的匹配文字',
        '• 与 K 列的【】文字完全一致（含标点、空格）',
        '• 用于自动关联步骤与预期结果',
        '• K 列后缀（toast提示/toast不出现/不可见/不存在）不影响匹配',
        '• 不可重复',
        '示例: 本地笔记引导',
    ]),
    # C: 页面XML
    '\n'.join([
        '页面 XML，从 Appium Inspector 导出后精简粘贴',
        '• 用脚本提取: python boox_automation/scripts/extract_page_xml.py',
        '• C/D 二选一填写，都填时 D 列优先执行',
        '',
        '填写方式（两种任选）:',
        '1) 内联文本 — 将 <hierarchy> XML 直接粘贴到单元格',
        '2) 本地文件 — C/D 都空时自动从 data/expected_pages/{key}.xml 读取',
        '',
        '支持多设备「键：」分块格式:',
        '  默认 XML（所有设备兜底，必填，放在最前面）',
        '  <hierarchy>...</hierarchy>',
        '',
        '  国内：',
        '  <hierarchy>...</hierarchy>',
        '',
        '  海外：',
        '  <hierarchy>...</hierarchy>',
        '',
        '支持的键: 国内 海外 全球 平板 阅读器 6 7.8 10.3 13.3 版本号',
        '匹配逻辑: 条件匹配最多的优先，无匹配回退默认',
        '仅有条件块无默认 → WARNING',
        '',
        '对比规则: 只比较 class + resource-id，text 差异仅 INFO 不阻塞',
    ]),
    # D: 检查元素
    '\n'.join([
        '元素级 XPath 检查，每行一个 XPath 选择器',
        '• C/D 二选一填写，都填时 D 列优先执行',
        '• 无需全页面 XML，只需列关键元素的 XPath',
        '',
        '格式（支持多设备「键：」分块）:',
        '  //android.widget.TextView[@resource-id="com.onyx:id/title" and @text="手写笔记"]',
        '  //android.widget.TextView[@resource-id="com.onyx:id/title" and @text="无边笔记"]',
        '',
        '  国内：',
        '  //android.widget.TextView[@resource-id="com.onyx:id/title" and @text="手写笔记"]',
        '',
        '  海外：',
        '  //android.widget.TextView[@resource-id="com.onyx:id/title" and @text="Handwriting"]',
        '',
        '执行逻辑:',
        '  visible 模式 — 所有 XPath 都能找到 → pass，任一找不到 → fail',
        '  not_visible 模式 — 所有 XPath 都找不到 → pass，任一找到 → fail',
    ]),
    # E: 用途说明
    '\n'.join([
        '人类可读的用途说明',
        '• 描述此预期结果对应的页面/场景',
        '• 出现在日志和失败报告中（不影响执行）',
        '示例: 笔记首页首次打开时的引导页，包含登录和创建笔记按钮',
    ]),
]

# 预期结果 5 列表头
exp_header = ["元素标识", "匹配文本", "页面XML", "检查元素", "用途说明"]

sid = get_sheet_id(token, "预期结果")
write_sheet_values(token, sid, start_row=1, start_col=1, values=[exp_comments])
print(f"  OK 预期结果 (注释行)")
write_sheet_values(token, sid, start_row=2, start_col=1, values=[exp_header])
print(f"  OK 预期结果 (表头行)")

print("\n注释行全部更新完成")
