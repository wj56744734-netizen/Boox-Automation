"""飞书报告推送效果测试脚本。

用法:
  python boox_automation/scripts/test_feishu_report.py            # 仅发卡片
  python boox_automation/scripts/test_feishu_report.py --file     # 卡片 + 文件
  python boox_automation/scripts/test_feishu_report.py --chat-id oc_xxx  # 指定群聊
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from boox_automation.core.feishu_report import build_report_card
from boox_automation.core.feishu import send_card_message, upload_file_to_im, send_file_message
from boox_automation.core.config import feishu_chat_id


def main():
    parser = argparse.ArgumentParser(description="飞书报告推送效果测试")
    parser.add_argument("--file", action="store_true", help="同时测试文件上传")
    parser.add_argument("--chat-id", type=str, default=None, help="目标群聊 ID")
    args = parser.parse_args()

    chat_id = args.chat_id or feishu_chat_id()
    if not chat_id:
        print("❌ 未配置 chat_id，请通过 --chat-id 指定或设置 config.yaml feishu.chat_id")
        sys.exit(1)

    print(f"目标群聊: {chat_id}")

    sample_device = {
        "device_name": "NoteAir5C",
        "device_size": "10.3",
        "driver_colour": "彩色",
        "devices_reader": "平板",
        "device_platform": "6350",
        "device_region": "海外",
        "version_info": "dev",
        "build_type": "userdebug",
        "filtered_size": "1860x2480",
        "android_version": "12",
        "build_date_time": "2026-06-12_10-15_dev_f082a68c2",
        "device_id": "0123456789ABCDEF",
    }

    card = build_report_card(
        passed=12,
        failed=2,
        skipped=2,
        duration_sec=512,
        modules=["笔记", "通用"],
        failed_cases=["笔记.创建笔记", "笔记.导出"],
        skipped_cases=[
            ("通用.关于", "前置条件不满足：仅国内设备"),
            ("笔记.同步", "前置条件不满足：需登录账号"),
        ],
        device=sample_device,
    )

    print("发送卡片...")
    try:
        resp = send_card_message(chat_id, card)
        msg_id = resp.get("data", {}).get("message_id", "?")
        print(f"✅ 卡片已发送 (message_id={msg_id})")
    except Exception as e:
        print(f"❌ 卡片发送失败: {e}")
        sys.exit(1)

    if args.file:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            import zipfile
            with zipfile.ZipFile(f, "w") as zf:
                zf.writestr("index.html", "<html><body><h1>示例报告</h1></body></html>")
            zip_path = f.name

        try:
            print(f"上传文件: {zip_path} ...")
            file_key = upload_file_to_im(zip_path)
            print(f"✅ 文件已上传 (file_key={file_key})")
            send_file_message(chat_id, file_key)
            print("✅ 文件消息已发送")
        except Exception as e:
            print(f"❌ 文件发送失败: {e}")
        finally:
            Path(zip_path).unlink(missing_ok=True)

    print("\n请前往飞书群聊查看效果。")


if __name__ == "__main__":
    main()
