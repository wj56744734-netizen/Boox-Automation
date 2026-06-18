"""更新元素表所有 sheet 注释行为完整使用说明（6 列元素 + 5 列预期结果）。

模块名来自 test_case_sheets 配置，"通用"始终自动包含。
"""
import logging

from boox_automation.core.feishu import get_sheet_id, write_sheet_values, list_sheet_names
from boox_automation.core.config import feishu_elements_token, test_case_sheets

logger = logging.getLogger(__name__)

# ---- 元素表 6 列注释 ----

element_comments = [
    # 1. 模块 (A列)
    '\n'.join([
        '元素标识的前半部分，与匹配文本（B列）拼接 = 完整 key',
        '• key 格式: 模块.匹配文本（如 笔记首页.创建笔记按钮）',
        '• 模块 = 元素所属页面/功能区域（如 手写笔记、笔记首页）',
        '• 同一模块内可重复（不同页面可有同名元素）',
        '示例: 笔记首页',
    ]),
    # 2. 匹配文本 (B列)
    '\n'.join([
        '测试步骤中【】内的匹配文字，与模块（A列）拼接 = 元素标识',
        '• 必与步骤中的【】文字完全一致（含标点、空格）',
        '• 不同页面可有相同匹配文本，通过页面上下文自动消歧',
        '• 不填时自动用「定位元素」的纯文本值做匹配',
        '示例: 创建笔记按钮（对应步骤「点击【创建笔记按钮】」）',
    ]),
    # 3. 定位元素 (C列)
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
    # 4. 操作 (D列)
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
    # 5. 用途说明 (E列)
    '\n'.join([
        '人类可读的元素描述，纯备注字段，不影响执行:',
        '• 出现在失败日志: 元素用途: xxx',
        '• 出现在 Allure 截图标题',
        '• 出现在步骤日志: 点击「xxx」',
        '建议简短描述在业务流程中的角色',
        '示例: 手写笔记编辑页的返回按钮',
    ]),
    # 6. 序号 (F列)
    '\n'.join([
        '同页面同 match 出现多个元素时的序号',
        '• 1 = 第一个匹配的元素，2 = 第二个，以此类推',
        '• 默认 0 或空 = 取第一个',
        '• 用于区分同文字、不同位置的多个元素',
        '示例: 笔记列表页有多个「更多」按钮，用 index=1,2,3 区分',
    ]),
]

# ---- 预期结果 5 列注释 ----

exp_header = ["模块", "匹配文本", "定位元素", "xml页面", "用途说明"]

exp_comments = [
    # A: 模块
    '\n'.join([
        '预期结果标识的前半部分，与匹配文本（B列）拼接 = 完整 key',
        '• key 格式: 模块.匹配文本（如 手写笔记.创建页）',
        '• 模块 = 所属页面名（如 手写笔记、笔记首页）',
        '示例: 手写笔记',
    ]),
    # B: 匹配文本
    '\n'.join([
        '用例 I 列步骤中【】内的匹配文字，与模块（A列）拼接 = key',
        '• 与 I 列的【】文字完全一致（含标点、空格）',
        '• 用于自动关联步骤与预期结果',
        '• I 列后缀（toast提示/toast不出现/不可见/不存在）不影响匹配',
        '示例: 创建页',
    ]),
    # C: 定位元素
    '\n'.join([
        'XPath 检查元素，每行一个选择器（旧称 检查元素 / D列）',
        '• C/D 二选一，都填时 C 列优先执行',
        '• 无需全页面 XML，只需列关键元素的 XPath',
        '',
        '格式（支持多设备「键：」分块）:',
        '  //android.widget.TextView[@resource-id="com.onyx:id/title" and @text="手写笔记"]',
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
    # D: xml页面
    '\n'.join([
        '页面 XML，从 Appium Inspector 导出后精简粘贴',
        '• 用脚本提取: python boox_automation/scripts/extract_page_xml.py',
        '• C/D 二选一填写，都填时 C 列（定位元素）优先执行',
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
    # E: 用途说明
    '\n'.join([
        '人类可读的用途说明',
        '• 描述此预期结果对应的页面/场景',
        '• 出现在日志和失败报告中（不影响执行）',
        '示例: 笔记首页首次打开时的引导页，包含登录和创建笔记按钮',
    ]),
]


def main():
    token = feishu_elements_token()
    modules = ["通用"] + test_case_sheets()
    all_sheets = list_sheet_names(token)

    # 更新元素 sheet 注释行
    for module in modules:
        if module not in all_sheets:
            logger.warning(
                "元素 sheet【%s】不存在，跳过。可用: %s",
                module, sorted(all_sheets),
            )
            continue
        sid = get_sheet_id(token, module)
        write_sheet_values(token, sid, start_row=1, start_col=1, values=[element_comments])
        print(f"  OK 元素/{module} (注释行)")

    # 更新预期结果 sheet 注释行 + 表头
    for module in modules:
        sheet_name = f"预期结果【{module}】"
        if sheet_name not in all_sheets:
            logger.warning(
                "预期结果 sheet【%s】不存在，跳过。可用: %s",
                sheet_name, sorted(all_sheets),
            )
            continue
        sid = get_sheet_id(token, sheet_name)
        write_sheet_values(token, sid, start_row=1, start_col=1, values=[exp_comments])
        print(f"  OK 预期结果/{sheet_name} (注释行)")
        write_sheet_values(token, sid, start_row=2, start_col=1, values=[exp_header])
        print(f"  OK 预期结果/{sheet_name} (表头行)")

    print("\n注释行全部更新完成")


if __name__ == "__main__":
    main()
