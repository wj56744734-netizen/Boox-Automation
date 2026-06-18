"""飞书表格列结构定义。所有表格读写操作通过此模块访问列索引（0-based）。

用例表列索引由 config.yaml 的 excel.columns 控制，此处为运行时辅助常量。
元素表和预期结果表列索引固定，直接使用。
"""

# ============ 元素表（表B — 元素 Sheet）6 列 ============
# 列序: 模块 | 匹配文本 | 定位元素 | 操作 | 用途说明 | 序号
ELEMENT_COL_MODULE = 0      # A列：模块
ELEMENT_COL_MATCH = 1       # B列：匹配文本
ELEMENT_COL_LOCATOR = 2     # C列：定位元素
ELEMENT_COL_ACTION = 3      # D列：操作
ELEMENT_COL_OPERATION = 4   # E列：用途说明
ELEMENT_COL_INDEX = 5       # F列：序号

# ============ 预期结果 Sheet 6 列 ============
# 列序: 模块 | 匹配文本 | 定位元素 | xml页面 | 操作 | 用途说明
EXPECTED_COL_MODULE = 0     # A列：模块
EXPECTED_COL_MATCH = 1      # B列：匹配文本
EXPECTED_COL_LOCATOR = 2    # C列：定位元素
EXPECTED_COL_XML = 3        # D列：xml页面
EXPECTED_COL_ACTION = 4     # E列：操作
EXPECTED_COL_OPERATION = 5  # F列：用途说明

# ============ 用例表（表A）列索引 — 委托 config.py ============
# 通过 case_column() 获取，支持 config.yaml 自定义列序。
