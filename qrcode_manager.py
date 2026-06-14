"""
qrcode_manager.py - QR Code 產生與管理
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("qrcode_mgr")


def generate_qrcode(
    url: str,
    save_path: Path,
    box_size: int = 10,
    border: int = 4,
) -> Optional[Path]:
    """
    產生 QR Code 並儲存至 save_path。
    回傳儲存路徑，失敗回傳 None。
    """
    try:
        import qrcode
        from PIL import Image, ImageDraw, ImageFont

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=box_size,
            border=border,
        )
        qr.add_data(url)
        qr.make(fit=True)

        # 深色背景版本
        img: Image.Image = qr.make_image(
            fill_color="#FFFFFF",
            back_color="#1A1A2E",
        ).convert("RGBA")

        # 在 QR Code 下方加上說明文字
        total_h = img.height + 50
        canvas = Image.new("RGBA", (img.width, total_h), "#1A1A2E")
        canvas.paste(img, (0, 0))

        draw = ImageDraw.Draw(canvas)
        text = url
        try:
            # 嘗試使用系統字型
            from PIL import ImageFont
            font = ImageFont.truetype("arial.ttf", 14)
        except Exception:
            font = ImageFont.load_default()

        # 文字置中
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        x = (img.width - text_w) // 2
        draw.text((x, img.height + 10), text, fill="#00D4FF", font=font)

        canvas.save(str(save_path), "PNG")
        logger.info("QR Code 已儲存至 %s (URL=%s)", save_path, url)
        return save_path

    except ImportError as exc:
        logger.error("缺少 qrcode 或 Pillow 套件: %s", exc)
    except Exception as exc:
        logger.error("QR Code 產生失敗: %s", exc)
    return None


def get_qrcode_base64(save_path: Path) -> Optional[str]:
    """將已儲存的 QR Code 圖片轉為 Base64 字串（供 GUI 顯示用）"""
    try:
        import base64
        if save_path.exists():
            data = save_path.read_bytes()
            return "data:image/png;base64," + base64.b64encode(data).decode()
    except Exception as exc:
        logger.error("QR Code Base64 轉換失敗: %s", exc)
    return None
