#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import requests
import json
import os
from typing import List, Any

# ==================== 配置 ====================
APP_ID = "cli_a94cb2b1b1f81cb1"
APP_SECRET = "64CPVsf3cQmW4Af7iyq7jhR2ssz8pEgd"
NODE_TOKEN = "ZQQzwAjadiJmy5kRT82cJDYRndg"          # 知识库节点 token

TARGET_CASE_ID = "NoteHomePage-0001"                # 目标用例编号
OUTPUT_DIR = "./test_case_output"                   # 图片保存根目录
# ===============================================

class ImageExtractor:
    def __init__(self):
        self.access_token = None
        self.spreadsheet_token = None

    def _request(self, method, url, **kwargs):
        """统一的请求方法，自动添加 token 并处理错误"""
        headers = kwargs.pop('headers', {})
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        try:
            r = requests.request(method, url, headers=headers, timeout=10, **kwargs)
            r.raise_for_status()
            result = r.json()
            if result.get('code') != 0:
                logging.debug(f"❌ API 错误: code={result['code']}, msg={result.get('msg')}")
                return None
            return result
        except Exception as e:
            logging.debug(f"❌ 请求失败: {e}")
            return None

    def get_token(self, app_id, app_secret):
        """获取 tenant_access_token"""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        data = {"app_id": app_id, "app_secret": app_secret}
        result = self._request('POST', url, json=data)
        if result:
            self.access_token = result['tenant_access_token']
            logging.debug("✅ 获取 token 成功")
            return True
        return False

    def get_spreadsheet_token(self, node_token):
        """从知识库节点获取电子表格 token"""
        url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={node_token}"
        result = self._request('GET', url)
        if result:
            node = result.get('data', {}).get('node', {})
            if node.get('obj_type') != 'sheet':
                logging.debug(f"❌ 节点类型不是 sheet: {node.get('obj_type')}")
                return False
            self.spreadsheet_token = node['obj_token']
            logging.debug(f"✅ 获取 spreadsheet token: {self.spreadsheet_token}")
            return True
        return False

    def get_sheet_id_by_title(self, title: str) -> str:
        """根据工作表标题获取 sheet_id"""
        url = f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{self.spreadsheet_token}/sheets/query"
        result = self._request('GET', url)
        if not result:
            return None
        sheets = result.get('data', {}).get('sheets', [])
        for s in sheets:
            if s.get('title', '').strip() == title.strip():
                return s['sheet_id']
        # 如果没找到，返回第一个
        return sheets[0]['sheet_id'] if sheets else None

    def get_all_data(self, sheet_id: str) -> List[List]:
        """读取整个工作表的数据，保留图片的 formattedValue"""
        url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{self.spreadsheet_token}/values/{sheet_id}"
        params = {'read_format': 'formattedValue', 'major_dimension': 'ROWS'}
        result = self._request('GET', url, params=params)
        if result:
            return result.get('data', {}).get('valueRange', {}).get('values', [])
        return []

    def extract_file_tokens(self, cell_value: Any) -> List[str]:
        """递归提取单元格中的 fileToken（图片标识）"""
        tokens = []
        if isinstance(cell_value, dict):
            if 'fileToken' in cell_value:
                tokens.append(cell_value['fileToken'])
            for v in cell_value.values():
                tokens.extend(self.extract_file_tokens(v))
        elif isinstance(cell_value, list):
            for item in cell_value:
                tokens.extend(self.extract_file_tokens(item))
        elif isinstance(cell_value, str):
            if cell_value.strip().startswith('{'):
                try:
                    obj = json.loads(cell_value)
                    tokens.extend(self.extract_file_tokens(obj))
                except (json.JSONDecodeError, TypeError):
                    pass
        return tokens

    def download_image(self, file_token: str, save_path: str, custom_filename: str = None) -> bool:
        """
        通过 file_token 下载图片到本地
        :param file_token: 飞书素材 token
        :param save_path: 保存目录
        :param custom_filename: 自定义文件名（不含扩展名），优先级高于 file_token
        """
        # 1. 获取临时下载链接
        url = f"https://open.feishu.cn/open-apis/drive/v1/medias/batch_get_tmp_download_url?file_tokens={file_token}"
        result = self._request('GET', url)
        if not result:
            return False
        tmp_urls = result.get('data', {}).get('tmp_download_urls', [])
        if not tmp_urls:
            return False
        tmp_url = tmp_urls[0].get('tmp_download_url')
        if not tmp_url:
            return False

        # 2. 下载图片
        try:
            r = requests.get(tmp_url, stream=True, timeout=15)
            r.raise_for_status()
            content_type = r.headers.get('Content-Type', '')
            ext_map = {
                'image/jpeg': '.jpg', 'image/jpg': '.jpg',
                'image/png': '.png', 'image/gif': '.gif',
                'image/webp': '.webp', 'image/bmp': '.bmp'
            }
            ext = ext_map.get(content_type, '.png')

            # 确定文件名
            if custom_filename:
                filename = f"{custom_filename}{ext}"
            else:
                filename = f"{file_token}{ext}"

            filepath = os.path.join(save_path, filename)
            os.makedirs(save_path, exist_ok=True)
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.debug(f"   ✅ 图片已保存: {filepath}")
            return True
        except Exception as e:
            logging.debug(f"   ❌ 下载失败: {e}")
            return False

    def run(self, target_case_id, table_name, output_dir):
        """
        :param target_case_id: 用例编号，如 "NoteHomePage-0001"
        :param table_name: 工作表名称，如 "笔记首页"
        :param output_dir: 输出根目录
        :return: 保存图片的目录路径（output_dir/table_name）
        """
        logging.debug("=" * 60)
        logging.debug("飞书表格图片提取器（仅下载图片）")
        logging.debug("=" * 60)

        if not self.get_token(app_id=APP_ID, app_secret=APP_SECRET):
            return None
        if not self.get_spreadsheet_token(node_token=NODE_TOKEN):
            return None

        sheet_id = self.get_sheet_id_by_title(table_name)
        if not sheet_id:
            logging.debug("❌ 未找到工作表")
            return None
        logging.debug(f"📄 使用工作表 ID: {sheet_id}")

        rows = self.get_all_data(sheet_id)
        if len(rows) < 2:
            logging.debug("❌ 数据不足")
            return None

        header = rows[0]
        try:
            case_col = header.index("用例编号")
            expected_col = header.index("预期结果")
        except ValueError:
            logging.debug("❌ 表头缺少必要的列：'用例编号' 或 '预期结果'")
            logging.debug(f"实际表头: {header}")
            return None

        target_row = None
        for row in rows[1:]:
            if len(row) > case_col and str(row[case_col]).strip() == target_case_id:
                target_row = row
                break
        if not target_row:
            logging.debug(f"❌ 未找到用例编号: {target_case_id}")
            return None
        logging.debug(f"✅ 找到目标行: {target_case_id}")

        expected_cell = target_row[expected_col] if len(target_row) > expected_col else None
        if expected_cell is None:
            logging.debug("⚠️ 预期结果列为空")
            return None

        tokens = self.extract_file_tokens(expected_cell)
        if not tokens:
            logging.debug("⚠️ 预期结果单元格中没有发现图片 token")
            logging.debug(f"单元格内容类型: {type(expected_cell)}")
            logging.debug(f"内容预览: {str(expected_cell)[:200]}")
            return None

        logging.debug(f"📷 发现图片 token: {tokens}")

        # 使用表名作为目录，图片命名为用例编号（多张时加序号）
        save_dir = os.path.join(output_dir, table_name)
        success = 0
        total = len(tokens)
        for idx, token in enumerate(tokens, start=1):
            if total == 1:
                custom_name = target_case_id
            else:
                custom_name = f"{target_case_id}_{idx}"
            if self.download_image(token, save_dir, custom_filename=custom_name):
                success += 1

        logging.debug(f"\n✅ 下载完成: {success}/{total} 张图片")
        logging.debug(f"📁 图片保存在: {save_dir}")
        return save_dir

if __name__ == "__main__":
    extractor = ImageExtractor()
    # 示例调用：使用表名 "笔记首页"，输出到当前目录的 test_case_output
    result_dir = extractor.run(
        target_case_id=TARGET_CASE_ID,
        table_name="笔记首页",
        output_dir=OUTPUT_DIR
    )
    if result_dir:
        print(f"图片保存路径: {result_dir}")