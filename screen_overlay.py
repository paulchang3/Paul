"""
screen_overlay.py — 跨螢幕、最上層、滑鼠穿透的圓圈覆蓋層（功能 1）

把每一台連線手機畫成一個圓，疊在「整個虛擬桌面」最上層 —— 包含所有延伸螢幕。
圓圈會跟著手機在整個桌面範圍自由移動，毫無邊界限制。

特性：
- 橫跨所有螢幕（union of QScreen.geometry()），含負座標的左側延伸螢幕。
- Frameless + WindowStaysOnTop + Tool（不佔工作列）。
- 半透明背景 + 滑鼠穿透（WA_TransparentForMouseEvents / WindowTransparentForInput），
  因此第一台手機用 SendInput 發出的點擊會「穿過」覆蓋層落到底下的應用程式。
- 圓內可顯示手機上傳的照片（裁切成圓形），否則顯示純色 + 名稱。
- 第一台手機（= 滑鼠）會以較粗白框 + 「滑鼠」標籤標示。

僅在桌面端（Windows，有 PySide6）執行；本模組只有被 gui.py 載入時才會 import。
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPixmap,
    QRadialGradient, QPainterPath, QGuiApplication,
)
from PySide6.QtWidgets import QWidget

from config import (
    CANVAS_WIDTH, CANVAS_HEIGHT,
    OVERLAY_DOT_RADIUS, OVERLAY_FPS, OVERLAY_SHOW_NAMES,
)
from device_manager import device_manager
from image_store import image_store

logger = logging.getLogger("overlay")


class ScreenOverlay(QWidget):
    """覆蓋整個虛擬桌面的透明圓圈層。"""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle("QR Controller Overlay")

        # 插值平滑用：device_id → (x, y)
        self._render: Dict[str, list[float]] = {}
        # 照片快取：device_id → (version, 圓形 QPixmap)
        self._pix_cache: Dict[str, Tuple[int, QPixmap]] = {}

        self._timer = QTimer(self)
        self._timer.setInterval(max(8, 1000 // max(1, OVERLAY_FPS)))
        self._timer.timeout.connect(self.update)

        # 螢幕配置變動時（插拔延伸螢幕）重新覆蓋整個虛擬桌面
        app = QGuiApplication.instance()
        if app is not None:
            app.primaryScreenChanged.connect(lambda *_: self.cover_virtual_desktop())
            for scr in QGuiApplication.screens():
                scr.geometryChanged.connect(lambda *_: self.cover_virtual_desktop())

    # ── 幾何：覆蓋整個虛擬桌面 ─────────────────────────────────────────────────
    def _virtual_geometry(self):
        """所有螢幕聯集的矩形（含延伸螢幕）。"""
        screens = QGuiApplication.screens()
        rect = screens[0].geometry()
        for scr in screens[1:]:
            rect = rect.united(scr.geometry())
        return rect

    def cover_virtual_desktop(self) -> None:
        rect = self._virtual_geometry()
        self.setGeometry(rect)

    # ── 顯示 / 隱藏 ────────────────────────────────────────────────────────────
    def start(self) -> None:
        self.cover_virtual_desktop()
        self.show()
        self.raise_()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    # ── 照片：載入並裁切成圓形（含快取）─────────────────────────────────────────
    def _circular_pixmap(self, device_id: str, diameter: int) -> Optional[QPixmap]:
        version = image_store.version(device_id)
        if version == 0:
            self._pix_cache.pop(device_id, None)
            return None
        cached = self._pix_cache.get(device_id)
        if cached and cached[0] == version and cached[1].width() == diameter:
            return cached[1]

        item = image_store.get(device_id)
        if item is None:
            return None
        _, raw = item
        src = QPixmap()
        if not src.loadFromData(raw):
            return None

        # 等比例填滿後置中裁切成正方形，再裁圓
        d = diameter
        scaled = src.scaled(
            d, d,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        out = QPixmap(d, d)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addEllipse(0, 0, d, d)
        p.setClipPath(path)
        ox = (d - scaled.width()) // 2
        oy = (d - scaled.height()) // 2
        p.drawPixmap(ox, oy, scaled)
        p.end()

        self._pix_cache[device_id] = (version, out)
        return out

    # ── 繪製 ──────────────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = max(1, self.width())
        h = max(1, self.height())
        sx = w / float(CANVAS_WIDTH)
        sy = h / float(CANVAS_HEIGHT)

        first_id = device_manager.first_device_id()

        devices = {d.device_id: d for d in device_manager.all_devices()}
        LERP = 0.3
        for dev_id, dev in devices.items():
            tx, ty = dev.x * sx, dev.y * sy
            if dev_id not in self._render:
                self._render[dev_id] = [tx, ty]
            r = self._render[dev_id]
            r[0] += (tx - r[0]) * LERP
            r[1] += (ty - r[1]) * LERP
            self._draw_circle(
                painter, r[0], r[1], dev,
                is_first=(dev_id == first_id),
            )

        # 清掉已離線裝置的插值暫存
        for old in list(self._render.keys()):
            if old not in devices:
                self._render.pop(old, None)
                self._pix_cache.pop(old, None)

    def _draw_circle(self, painter: QPainter, cx: float, cy: float, dev, is_first: bool) -> None:
        radius = float(OVERLAY_DOT_RADIUS)
        color = QColor(dev.color)
        center = QPointF(cx, cy)

        painter.save()
        if not dev.connected:
            painter.setOpacity(0.35)

        # 光暈
        grad = QRadialGradient(center, radius * 2.4)
        glow = QColor(color); glow.setAlpha(90)
        grad.setColorAt(0.0, glow)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, radius * 2.4, radius * 2.4)

        # 圓內：照片或純色
        pix = self._circular_pixmap(dev.device_id, int(radius * 2))
        if pix is not None:
            painter.drawPixmap(int(cx - radius), int(cy - radius), pix)
        else:
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, radius, radius)

        # 外框：第一台（滑鼠）用較粗白框，其餘用半透明白框
        if is_first:
            painter.setPen(QPen(QColor(255, 255, 255, 235), 5))
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 110), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius, radius)

        # 名稱 + 角色標籤
        if OVERLAY_SHOW_NAMES:
            label = dev.display_name
            if is_first:
                label += "（滑鼠）"
            painter.setPen(QColor(255, 255, 255, 240))
            font = QFont("Microsoft JhengHei", max(9, int(radius * 0.34)))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                QRectF(cx - radius, cy + radius + 2, radius * 2, radius * 0.9),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                label,
            )

        painter.restore()
