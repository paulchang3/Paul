"""
mouse_controller.py — 第一台手機 = 真實滑鼠（Windows 專屬）

用 ctypes 呼叫 Win32 SendInput 驅動真實游標，支援跨螢幕（含延伸螢幕）的
絕對座標移動、左鍵單擊 / 雙擊、滾輪上下捲動。

設計重點：
- 非 Windows 或缺少 user32 時，所有方法自動降級為「空操作」並回傳 False，
  不會丟例外 —— 因此後端與單元測試可在 Linux/雲端正常 import 與執行。
- 預設 active=False（安全）：必須由桌面 GUI 明確開啟，避免一啟動就被手機
  搶走游標而難以關閉。
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger("mouse_controller")

_IS_WINDOWS = sys.platform == "win32"

# ── Win32 常數 ────────────────────────────────────────────────────────────────
MOUSEEVENTF_MOVE        = 0x0001
MOUSEEVENTF_LEFTDOWN    = 0x0002
MOUSEEVENTF_LEFTUP      = 0x0004
MOUSEEVENTF_RIGHTDOWN   = 0x0008
MOUSEEVENTF_RIGHTUP     = 0x0010
MOUSEEVENTF_WHEEL       = 0x0800
MOUSEEVENTF_ABSOLUTE    = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000   # 絕對座標以「整個虛擬桌面」為基準（含延伸螢幕）
WHEEL_DELTA             = 120
INPUT_MOUSE             = 0

# ── ctypes 結構（僅在 Windows 建立）──────────────────────────────────────────
if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    ULONG_PTR = wintypes.WPARAM

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx",          wintypes.LONG),
            ("dy",          wintypes.LONG),
            ("mouseData",   wintypes.DWORD),
            ("dwFlags",     wintypes.DWORD),
            ("time",        wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class _INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("mi", _MOUSEINPUT)]
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    _user32 = ctypes.windll.user32


class MouseController:
    """真實滑鼠控制器（Windows）。非 Windows 時為安全空殼。"""

    def __init__(self) -> None:
        # active 由 GUI 切換；只有 active 且在 Windows 上才會真的動到游標
        self.active: bool = False
        self.available: bool = _IS_WINDOWS

    # ── 內部：送出一個 mouse input ─────────────────────────────────────────────
    def _send(self, dx: int = 0, dy: int = 0, flags: int = 0, data: int = 0) -> bool:
        if not (_IS_WINDOWS and self.active):
            return False
        try:
            mi = _MOUSEINPUT(dx, dy, data & 0xFFFFFFFF, flags, 0, 0)
            inp = _INPUT(type=INPUT_MOUSE)
            inp.mi = mi
            n = _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
            return n == 1
        except Exception as exc:           # pragma: no cover - 僅 Windows 例外路徑
            logger.warning("SendInput 失敗: %s", exc)
            return False

    # ── 對外 API ──────────────────────────────────────────────────────────────
    def move_to_normalized(self, nx: float, ny: float) -> bool:
        """
        以 [0,1] 正規化座標移動游標到虛擬桌面對應位置。
        (0,0)=所有螢幕的左上角；(1,1)=最右下角（含延伸螢幕）。
        """
        nx = 0.0 if nx < 0 else 1.0 if nx > 1 else nx
        ny = 0.0 if ny < 0 else 1.0 if ny > 1 else ny
        ax = int(round(nx * 65535))
        ay = int(round(ny * 65535))
        return self._send(
            ax, ay,
            MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
        )

    def move_to_logical(self, x: float, y: float, canvas_w: float, canvas_h: float) -> bool:
        """以邏輯畫布座標移動（自動換算成虛擬桌面正規化座標）。"""
        if canvas_w <= 0 or canvas_h <= 0:
            return False
        return self.move_to_normalized(x / canvas_w, y / canvas_h)

    def left_click(self) -> bool:
        """左鍵單擊（選擇）。"""
        a = self._send(flags=MOUSEEVENTF_LEFTDOWN)
        b = self._send(flags=MOUSEEVENTF_LEFTUP)
        return a and b

    def double_click(self) -> bool:
        """左鍵雙擊（啟動）。連續兩次 down/up，由系統判定為雙擊。"""
        return self.left_click() and self.left_click()

    def scroll(self, amount: int) -> bool:
        """
        滾輪捲動。amount 正值向上、負值向下，單位為「格」（自動乘上 WHEEL_DELTA）。
        """
        return self._send(flags=MOUSEEVENTF_WHEEL, data=int(amount) * WHEEL_DELTA)


# 全域單例（伺服器與 GUI 共用）
mouse_controller = MouseController()
