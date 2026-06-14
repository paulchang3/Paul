"""
image_store.py — 手機上傳照片的記憶體儲存區

每台手機可上傳一張照片，顯示在它的圓圈裡。照片以 device_id 為鍵存在記憶體，
手機斷線時清除。後端 GUI / 覆蓋層（同行程）可直接讀 bytes；瀏覽器 /screen
則透過 GET /api/image/{device_id} 取得。

純標準函式庫，可在雲端 headless 測試。
"""

from __future__ import annotations

import base64
import re
import threading
import time
from typing import Dict, Optional, Tuple

# data URL 解析：data:image/png;base64,xxxx
_DATA_URL_RE = re.compile(r"^data:(?P<mime>image/[a-zA-Z0-9.+-]+);base64,(?P<data>.+)$", re.S)

_ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp", "image/gif"}


class ImageStore:
    """device_id → (content_type, bytes, version) 的執行緒安全儲存區。"""

    def __init__(self, max_bytes: int = 3_000_000) -> None:
        self._data: Dict[str, Tuple[str, bytes, int]] = {}
        self._max_bytes = max_bytes
        self._lock = threading.Lock()

    # ── 寫入 ──────────────────────────────────────────────────────────────────
    def set_bytes(self, device_id: str, content_type: str, raw: bytes) -> bool:
        """直接以 bytes 設定。回傳是否成功（型別/大小檢查）。"""
        if content_type not in _ALLOWED_MIME:
            return False
        if not raw or len(raw) > self._max_bytes:
            return False
        with self._lock:
            version = int(time.time() * 1000)
            self._data[device_id] = (content_type, raw, version)
        return True

    def set_data_url(self, device_id: str, data_url: str) -> bool:
        """以 data:image/...;base64,... 字串設定。"""
        if not data_url or len(data_url) > self._max_bytes * 2:
            return False
        m = _DATA_URL_RE.match(data_url.strip())
        if not m:
            return False
        mime = m.group("mime")
        try:
            raw = base64.b64decode(m.group("data"), validate=True)
        except Exception:
            return False
        return self.set_bytes(device_id, mime, raw)

    # ── 讀取 ──────────────────────────────────────────────────────────────────
    def get(self, device_id: str) -> Optional[Tuple[str, bytes]]:
        with self._lock:
            item = self._data.get(device_id)
        if item is None:
            return None
        content_type, raw, _ = item
        return content_type, raw

    def version(self, device_id: str) -> int:
        """回傳目前版本（毫秒時間戳）；無圖回 0。供快取失效判斷。"""
        with self._lock:
            item = self._data.get(device_id)
        return item[2] if item else 0

    def has(self, device_id: str) -> bool:
        with self._lock:
            return device_id in self._data

    # ── 清除 ──────────────────────────────────────────────────────────────────
    def remove(self, device_id: str) -> None:
        with self._lock:
            self._data.pop(device_id, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


# 全域單例
image_store = ImageStore()
