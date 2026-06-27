"""
元素用途目录（替代之前 YAML 的 desc/operation 字段）。

用途：
- 失败截图/日志里附上"这个 locator 是做什么用的"，便于排错
- 新增 locator 时按需补一行；未登记的 locator 在错误信息里不会附描述，不影响功能

约定：
- key 为完整 locator 字符串（com.onyx:id/xxx 或 android.widget.xxx）
- 仅对常见 / 通用 locator 写描述；非通用、跟具体业务强绑定的可不收录
"""

from __future__ import annotations

from __future__ import annotations

ELEMENT_DESCRIPTIONS: dict[str, str] = {
    # —— 笔记首页 / 通用列表 ——
    "com.onyx:id/create_icon": "笔记首页：创建按钮（有笔记状态）",
    "com.onyx:id/title": "笔记/文件夹标题（首页列表项文本）",
    "com.onyx:id/textviewItem": "笔记列表项文本",
    "com.onyx:id/tool": "笔记首页：工具栏容器",
    "com.onyx:id/tool_layout": "笔记首页：工具栏布局父容器",
    "com.onyx:id/more_menu": "笔记首页：更多菜单按钮",
    "com.onyx:id/page": "笔记列表：页码信息",
    "com.onyx:id/info": "列表项辅助信息",
    "com.onyx:id/total": "总数 / 计数显示",

    # —— 笔记画布（笔记编辑页）——
    "com.onyx.android.note:id/back_icon": "笔记画布：返回按钮",
    "com.onyx.android.note:id/tv_back": "笔记画布：返回文字按钮",
    "com.onyx.android.note:id/quit": "笔记画布：退出按钮",
    "com.onyx.android.note:id/title": "导入页/画布顶部标题",
    "com.onyx.android.note:id/note_name": "笔记名称（命名弹窗）",
    "com.onyx.android.note:id/tv_selected_bg": "模板选择：已选中背景",
    "com.onyx.android.note:id/btn_ok": "笔记画布：确定按钮",
    "com.onyx.android.note:id/btn_cancel": "笔记画布：取消按钮",
    "com.onyx.android.note:id/button_positive": "笔记画布：通用对话框-确定",
    "com.onyx.android.note:id/textView_message": "笔记画布：通用对话框-消息正文",
    "com.onyx.android.note:id/start_import": "导入笔记：开始导入按钮",
    "com.onyx.android.note:id/progress": "导入笔记：进度条",
    "com.onyx.android.note:id/tv_sub_title": "首次引导：副标题文本",
    "com.onyx.android.note:id/btn_ensure": "首次引导：确认按钮",

    # —— 通用对话框 / 弹窗 ——
    "com.onyx:id/button_positive": "通用对话框：确定按钮",
    "com.onyx:id/button_negative": "通用对话框：取消按钮",
    "com.onyx:id/btn_ok": "通用弹窗：确定按钮",
    "com.onyx:id/btn_close": "通用弹窗：关闭按钮",
    "com.onyx:id/textView_message": "通用对话框：消息正文",

    # —— 搜索 / 筛选 ——
    "com.onyx:id/search_et_input": "搜索：关键词输入框",
    "com.onyx:id/search_button": "搜索：触发按钮",
    "com.onyx:id/search_option": "搜索：选项筛选区",
    "com.onyx:id/imageView_clear": "搜索：清空输入按钮",
    "com.onyx:id/no_search": "搜索：无结果提示",
    "com.onyx:id/tag_checkbox": "筛选：标签维度 checkbox",
    "com.onyx:id/scribble_checkbox": "筛选：手写笔记 checkbox",
    "com.onyx:id/text_checkbox": "筛选：文本笔记 checkbox",
    "com.onyx:id/title_checkbox": "筛选：标题维度 checkbox",
    "com.onyx:id/all_library_checkbox": "筛选：全部库 checkbox",

    # —— 重命名 / 备份 / 恢复 ——
    "com.onyx:id/editText_new_name": "重命名：新名称输入框",
    "com.onyx:id/local_backup": "本地备份入口",
    "com.onyx:id/restore": "备份恢复入口",
    "com.onyx:id/tv_restore_title": "恢复：标题",
    "com.onyx:id/btn_goto_note": "恢复：进入笔记按钮",
    "com.onyx:id/append": "恢复：追加模式",
    "com.onyx:id/delete": "删除按钮",

    # —— 文件浏览器 ——
    "com.onyx:id/volume_name": "文件浏览器：存储卷名称",
    "com.onyx:id/text_title": "文件浏览器：文本标题",
    "com.onyx:id/textview_paste": "文件浏览器：粘贴入口",

    # —— ksync 同步 ——
    "com.onyx.android.ksync:id/account": "ksync 登录：账号输入框",
    "com.onyx.android.ksync:id/password": "ksync 登录：密码输入框",

    # —— 设备/系统 ——
    "com.onyx:id/dock": "Dock 栏",
    "com.onyx:id/imageView_cover_border": "封面边框",
    "com.onyx:id/style_iv": "样式 icon",
    "com.onyx:id/name": "通用名称字段",

    # —— Android 原生控件（仅作 by_method 类型标记，不写描述）——
    # "android.widget.ImageView": "",
    # "android.widget.TextView": "",
    # "android.widget.LinearLayout": "",
}


def describe(locator: str | None) -> str | None:
    """根据 locator 字符串返回中文描述；命中不到返回 None。"""
    if not locator:
        return None
    # 精确匹配优先
    if locator in ELEMENT_DESCRIPTIONS:
        return ELEMENT_DESCRIPTIONS[locator]
    # 子串匹配兜底（取最长的匹配，避免短串误匹配覆盖更精确的匹配）
    best = None
    best_len = 0
    for known, text in ELEMENT_DESCRIPTIONS.items():
        if known in locator and len(known) > best_len:
            best = text
            best_len = len(known)
    return best
