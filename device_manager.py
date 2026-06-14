"""
device_manager.py - 裝置（手機）管理模組
管理每個連線手機的狀態、座標、顏色、Session Token
"""

from __future__ import annotations

import asyncio
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from config import (
    CANVAS_WIDTH, CANVAS_HEIGHT, DOT_COLORS,
    SESSION_TOKEN_LENGTH, MAX_PACKET_SIZE,
)


@dataclass
class Device:
    """代表一台連線中的手機裝置"""
    device_id: str                    # UUID
    session_token: str                # 安全 Token
    ws_id: str                        # WebSocket 連線 ID
    color: str                        # 圓點顏色
    index: int                        # 連線序號（決定顏色）

    # 座標（浮點，對應畫布邏輯座標）
    x: float = 0.0
    y: float = 0.0

    # 裝置資訊（由 User-Agent 解析）
    user_agent: str = ""
    browser: str = "Unknown"
    os_name: str = "Unknown"
    ip_address: str = ""

    # 狀態
    connected: bool = True
    last_seen: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)

    # 顯示名稱（例如 "手機 A"）
    display_name: str = ""

    # 上傳照片版本（0 = 無照片；>0 為毫秒時間戳，變更時供前端快取失效）
    image_version: int = 0

    def touch(self) -> None:
        """更新最後活動時間"""
        self.last_seen = time.time()

    def move(self, dx: float, dy: float, speed: float = 1.0) -> None:
        """
        相對移動，限制在畫布邊界內。
        dx/dy 為方向向量，speed 為速度倍率。
        """
        step = 8.0 * speed
        new_x = self.x + dx * step
        new_y = self.y + dy * step
        self.x = max(0.0, min(float(CANVAS_WIDTH), new_x))
        self.y = max(0.0, min(float(CANVAS_HEIGHT), new_y))
        self.touch()

    def set_position(self, x: float, y: float) -> None:
        """絕對座標設定（拖曳模式）"""
        self.x = max(0.0, min(float(CANVAS_WIDTH), x))
        self.y = max(0.0, min(float(CANVAS_HEIGHT), y))
        self.touch()

    def to_dict(self) -> dict:
        """序列化為 JSON-serializable dict，供 WebSocket 廣播使用"""
        image_url = (
            f"/api/image/{self.device_id}?v={self.image_version}"
            if self.image_version > 0 else ""
        )
        return {
            "device_id":    self.device_id,
            "display_name": self.display_name,
            "color":        self.color,
            "x":            round(self.x, 2),
            "y":            round(self.y, 2),
            "connected":    self.connected,
            "browser":      self.browser,
            "os_name":      self.os_name,
            "ip_address":   self.ip_address,
            "index":        self.index,
            "image_url":    image_url,
        }


def _parse_user_agent(ua: str) -> tuple[str, str]:
    """簡易解析 User-Agent，回傳 (browser, os)"""
    ua_lower = ua.lower()
    # 瀏覽器
    if "edg" in ua_lower:
        browser = "Edge"
    elif "chrome" in ua_lower:
        browser = "Chrome"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    else:
        browser = "Browser"
    # OS
    if "android" in ua_lower:
        os_name = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os_name = "iOS"
    elif "windows" in ua_lower:
        os_name = "Windows"
    elif "mac" in ua_lower:
        os_name = "macOS"
    elif "linux" in ua_lower:
        os_name = "Linux"
    else:
        os_name = "Unknown"
    return browser, os_name


class DeviceManager:
    """
    全域裝置管理器（Singleton）
    負責：新增 / 移除裝置、驗證 Token、廣播狀態快照
    """

    def __init__(self) -> None:
        self._devices: Dict[str, Device] = {}       # device_id → Device
        self._ws_map:  Dict[str, str]    = {}        # ws_id     → device_id
        self._lock = asyncio.Lock()
        self._counter: int = 0                       # 累計連線數（決定顏色 index）

    # ── 連線管理 ──────────────────────────────────────────────────────────────

    async def register(
        self,
        ws_id: str,
        user_agent: str = "",
        ip_address: str = "",
    ) -> Device:
        """
        為新 WebSocket 連線建立 Device。
        同一 IP 再次連線視為新裝置（手機重新整理）。
        """
        async with self._lock:
            device_id     = str(uuid.uuid4())
            session_token = secrets.token_hex(SESSION_TOKEN_LENGTH)
            color_index   = self._counter % len(DOT_COLORS)
            color         = DOT_COLORS[color_index]

            # 命名：手機 A, B, C…
            letter = chr(ord("A") + (self._counter % 26))
            display_name = f"手機 {letter}"

            browser, os_name = _parse_user_agent(user_agent)

            device = Device(
                device_id     = device_id,
                session_token = session_token,
                ws_id         = ws_id,
                color         = color,
                index         = self._counter,
                x             = float(CANVAS_WIDTH)  // 2,
                y             = float(CANVAS_HEIGHT) // 2,
                user_agent    = user_agent,
                browser       = browser,
                os_name       = os_name,
                ip_address    = ip_address,
                display_name  = display_name,
            )

            self._devices[device_id] = device
            self._ws_map[ws_id]      = device_id
            self._counter           += 1
            return device

    async def disconnect(self, ws_id: str) -> Optional[Device]:
        """標記裝置離線，移除 ws_map 對應"""
        async with self._lock:
            device_id = self._ws_map.pop(ws_id, None)
            if device_id and device_id in self._devices:
                dev = self._devices[device_id]
                dev.connected = False
                # 保留 30 秒後清除（讓畫布顯示淡出效果）
                asyncio.get_event_loop().call_later(
                    30, self._devices.pop, device_id, None
                )
                return dev
        return None

    def get_by_ws(self, ws_id: str) -> Optional[Device]:
        """透過 ws_id 取得 Device"""
        device_id = self._ws_map.get(ws_id)
        if device_id:
            return self._devices.get(device_id)
        return None

    def get_by_id(self, device_id: str) -> Optional[Device]:
        return self._devices.get(device_id)

    # ── 安全驗證 ──────────────────────────────────────────────────────────────

    def verify_token(self, ws_id: str, token: str) -> bool:
        """驗證 session_token 是否匹配"""
        dev = self.get_by_ws(ws_id)
        if dev is None:
            return False
        return secrets.compare_digest(dev.session_token, token)

    def verify_by_id(self, device_id: str, token: str) -> Optional[Device]:
        """以 device_id + token 驗證（供 HTTP 上傳用）。成功回傳 Device。"""
        dev = self._devices.get(device_id)
        if dev is None or not token:
            return None
        if secrets.compare_digest(dev.session_token, token):
            return dev
        return None

    def validate_packet(self, data: dict, ws_id: str) -> bool:
        """
        驗證控制封包合法性：
        1. 封包大小
        2. device_id 與 ws_id 對應
        3. session_token 正確
        """
        if len(str(data)) > MAX_PACKET_SIZE:
            return False
        device_id = data.get("device_id", "")
        token     = data.get("token", "")
        dev = self.get_by_ws(ws_id)
        if dev is None:
            return False
        if dev.device_id != device_id:
            return False
        if not secrets.compare_digest(dev.session_token, token):
            return False
        return True

    # ── 狀態查詢 ──────────────────────────────────────────────────────────────

    @property
    def connected_count(self) -> int:
        return sum(1 for d in self._devices.values() if d.connected)

    def all_devices(self) -> list[Device]:
        return list(self._devices.values())

    # ── 第一台手機（= 滑鼠控制者）─────────────────────────────────────────────

    def first_device(self) -> Optional[Device]:
        """
        回傳「第一台」連線中的手機 = 連線序號 index 最小者。
        第一台離線後，下一台自動遞補成為第一台。
        """
        connected = [d for d in self._devices.values() if d.connected]
        if not connected:
            return None
        return min(connected, key=lambda d: d.index)

    def first_device_id(self) -> Optional[str]:
        dev = self.first_device()
        return dev.device_id if dev else None

    def is_first(self, device: Optional[Device]) -> bool:
        """判斷某裝置是否為目前的第一台手機。"""
        if device is None or not device.connected:
            return False
        first = self.first_device()
        return first is not None and first.device_id == device.device_id

    def snapshot(self) -> list[dict]:
        """取得所有裝置的序列化快照，供廣播使用"""
        return [d.to_dict() for d in self._devices.values()]


# 全域單例
device_manager = DeviceManager()
