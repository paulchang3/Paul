"""
gui.py - PySide6 桌面 GUI 主視窗
包含：QR Code 顯示、連線列表、System Log、效能儀表板
畫布改用 Qt QPainter 直接繪製，避免 QWebEngineView 崩潰問題
"""

from __future__ import annotations

import logging
import sys
import time
import webbrowser
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QThread, Signal, QObject, QUrl, QPointF
from PySide6.QtGui import (
    QFont, QPixmap, QColor, QPainter, QPen, QBrush,
    QRadialGradient, QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QTextEdit, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QSizePolicy,
    QPushButton,
)

from config import SERVER_PORT, QRCODE_PATH, CANVAS_WIDTH, CANVAS_HEIGHT, DOT_RADIUS
from health_monitor import health_monitor
from device_manager import device_manager
from qrcode_manager import generate_qrcode

logger = logging.getLogger("gui")

# ── 調色板 ────────────────────────────────────────────────────────────────────
DARK_BG      = "#0D1117"
DARK_PANEL   = "#161B22"
DARK_BORDER  = "#30363D"
ACCENT_BLUE  = "#58A6FF"
ACCENT_GREEN = "#3FB950"
ACCENT_RED   = "#F85149"
TEXT_PRIMARY = "#E6EDF3"
TEXT_DIM     = "#8B949E"


# ── 全域信號橋 ────────────────────────────────────────────────────────────────
class _Signals(QObject):
    log_message   = Signal(str)
    stats_update  = Signal(dict)
    server_ready  = Signal(str)

signals = _Signals()


# ── Qt Canvas Widget（QPainter 版，取代 QWebEngineView）──────────────────────

class CanvasWidget(QWidget):
    """
    用 QPainter 繪製測試畫布，直接讀取 device_manager 狀態。
    每 16ms（~60FPS）由 QTimer 觸發重繪。
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #0A0E14; border: 1px solid #30363D; border-radius: 8px;")

        # 插值用暫存（平滑移動）
        self._render: dict[str, dict] = {}  # device_id → {x, y, color, name}

        # 60 FPS 重繪計時器
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)
        self._timer.start()

        # FPS 計算
        self._frame_count = 0
        self._fps_timer_start = time.time()
        self._fps_display = 0

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # 背景
        painter.fillRect(0, 0, w, h, QColor("#0A0E14"))

        # 網格
        painter.setPen(QPen(QColor("#1C2333"), 1))
        step = max(30, w // 20)
        for x in range(0, w, step):
            painter.drawLine(x, 0, x, h)
        step_h = max(30, h // 15)
        for y in range(0, h, step_h):
            painter.drawLine(0, y, w, y)

        # 取得裝置快照
        devices = {d.device_id: d for d in device_manager.all_devices()}
        scale_x = w / CANVAS_WIDTH
        scale_y = h / CANVAS_HEIGHT

        # 插值 & 繪製
        LERP = 0.25
        for dev_id, dev in devices.items():
            if dev_id not in self._render:
                self._render[dev_id] = {
                    "x": dev.x, "y": dev.y,
                    "color": dev.color, "name": dev.display_name,
                    "connected": dev.connected,
                }
            r = self._render[dev_id]
            r["x"]     = r["x"] + (dev.x - r["x"]) * LERP
            r["y"]     = r["y"] + (dev.y - r["y"]) * LERP
            r["color"] = dev.color
            r["name"]  = dev.display_name
            r["connected"] = dev.connected
            self._draw_dot(painter, r, scale_x, scale_y)

        # 清除已離線裝置
        active_ids = set(devices.keys())
        for old_id in list(self._render.keys()):
            if old_id not in active_ids:
                del self._render[old_id]

        # FPS overlay
        self._frame_count += 1
        elapsed = time.time() - self._fps_timer_start
        if elapsed >= 1.0:
            self._fps_display = int(self._frame_count / elapsed)
            self._frame_count = 0
            self._fps_timer_start = time.time()

        painter.setPen(QColor("#8B949E"))
        painter.setFont(QFont("Consolas", 10))
        painter.drawText(8, 18, f"FPS: {self._fps_display}  連線: {device_manager.connected_count}")

    def _draw_dot(
        self,
        painter: QPainter,
        r: dict,
        scale_x: float,
        scale_y: float,
    ) -> None:
        cx = r["x"] * scale_x
        cy = r["y"] * scale_y
        radius = DOT_RADIUS * min(scale_x, scale_y)
        color  = QColor(r["color"])

        painter.save()
        if not r.get("connected", True):
            painter.setOpacity(0.3)

        # 光暈
        grad = QRadialGradient(QPointF(cx, cy), radius * 2.5)
        glow = QColor(color)
        glow.setAlpha(80)
        grad.setColorAt(0, glow)
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), radius * 2.5, radius * 2.5)

        # 主圓點
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(255, 255, 255, 80), 2))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # 名稱文字
        painter.setPen(QColor("white"))
        font = QFont("Microsoft JhengHei", max(8, int(radius * 0.65)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            int(cx - radius), int(cy - radius),
            int(radius * 2), int(radius * 2),
            Qt.AlignmentFlag.AlignCenter,
            r.get("name", "?"),
        )

        painter.restore()


# ── LED 燈號 ──────────────────────────────────────────────────────────────────

class LedIndicator(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self.set_state(False)

    def set_state(self, on: bool) -> None:
        color = ACCENT_GREEN if on else ACCENT_RED
        self.setStyleSheet(f"background:{color}; border-radius:6px;")


# ── 主視窗 ────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self, server_url: str) -> None:
        super().__init__()
        self.server_url = server_url
        self.setWindowTitle("Multi-Mobile QR Controller")
        self.setMinimumSize(1280, 720)
        self._build_ui()
        self._connect_signals()

        # 每秒刷新左側面板
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self._periodic_refresh)
        self._refresh_timer.start()

        self._append_log(f"伺服器就緒：{server_url}")
        self._refresh_qrcode()

    # ── UI 建構 ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(8, 8, 8, 8)

        left = self._build_left_panel()
        left.setFixedWidth(300)
        root.addWidget(left)

        # 右側：Qt 原生畫布
        self.canvas = CanvasWidget()
        root.addWidget(self.canvas, 1)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        vbox  = QVBoxLayout(panel)
        vbox.setSpacing(8)
        vbox.setContentsMargins(0, 0, 0, 0)

        # 標題
        title = QLabel("Multi-Mobile\nQR Controller")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{ACCENT_BLUE};font-size:15px;font-weight:bold;padding:6px;")
        vbox.addWidget(title)

        vbox.addWidget(self._build_qrcode_group())
        vbox.addWidget(self._build_info_group())
        vbox.addWidget(self._build_stats_group())
        vbox.addWidget(self._build_device_list_group())
        vbox.addWidget(self._build_log_group(), 1)
        return panel

    def _build_qrcode_group(self) -> QGroupBox:
        box    = QGroupBox("掃描 QR Code 加入")
        layout = QVBoxLayout(box)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setFixedHeight(200)
        layout.addWidget(self.qr_label)

        self.url_label = QLabel(self.server_url)
        self.url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.url_label.setStyleSheet(f"color:{ACCENT_BLUE};font-size:11px;")
        self.url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.url_label)

        # 放大 QR Code 按鈕
        btn_qr = QPushButton("放大 QR Code")
        btn_qr.setStyleSheet(
            f"background:{DARK_PANEL};color:{ACCENT_BLUE};"
            f"border:1px solid {ACCENT_BLUE};border-radius:4px;padding:4px;"
        )
        btn_qr.clicked.connect(self._show_qr_popup)
        layout.addWidget(btn_qr)

        btn = QPushButton("在瀏覽器開啟控制器")
        btn.setStyleSheet(
            f"background:{DARK_PANEL};color:{TEXT_DIM};"
            f"border:1px solid {DARK_BORDER};border-radius:4px;padding:4px;"
        )
        btn.clicked.connect(lambda: webbrowser.open(self.server_url))
        layout.addWidget(btn)
        return box

    def _build_info_group(self) -> QGroupBox:
        box    = QGroupBox("伺服器資訊")
        layout = QHBoxLayout(box)

        left_v = QVBoxLayout()
        # WebSocket LED
        ws_row = QHBoxLayout()
        self.ws_led = LedIndicator()
        ws_row.addWidget(QLabel("WebSocket"))
        ws_row.addWidget(self.ws_led)
        ws_row.addStretch()
        left_v.addLayout(ws_row)

        # 連線數
        cnt_row = QHBoxLayout()
        cnt_row.addWidget(QLabel("連線數："))
        self.conn_label = QLabel("0")
        self.conn_label.setStyleSheet(f"color:{ACCENT_GREEN};font-size:18px;font-weight:bold;")
        cnt_row.addWidget(self.conn_label)
        cnt_row.addStretch()
        left_v.addLayout(cnt_row)

        layout.addLayout(left_v)
        return box

    def _build_stats_group(self) -> QGroupBox:
        box    = QGroupBox("系統效能")
        layout = QVBoxLayout(box)

        def _row(label: str):
            h = QHBoxLayout()
            lbl = QLabel(label); lbl.setFixedWidth(36)
            bar = QProgressBar(); bar.setRange(0, 100); bar.setFixedHeight(8)
            val = QLabel("0%"); val.setFixedWidth(36)
            h.addWidget(lbl); h.addWidget(bar, 1); h.addWidget(val)
            layout.addLayout(h)
            return bar, val

        self.cpu_bar, self.cpu_val = _row("CPU")
        self.ram_bar, self.ram_val = _row("RAM")

        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("FPS"))
        self.fps_label = QLabel("0")
        self.fps_label.setStyleSheet(f"color:{ACCENT_GREEN};font-size:18px;font-weight:bold;")
        fps_row.addWidget(self.fps_label)
        fps_row.addStretch()
        layout.addLayout(fps_row)
        return box

    def _build_device_list_group(self) -> QGroupBox:
        box    = QGroupBox("已連線裝置")
        layout = QVBoxLayout(box)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(100)

        self.dev_container = QWidget()
        self.dev_layout    = QVBoxLayout(self.dev_container)
        self.dev_layout.setContentsMargins(0, 0, 0, 0)
        self.dev_layout.setSpacing(2)
        self.dev_layout.addStretch()
        scroll.setWidget(self.dev_container)
        layout.addWidget(scroll)
        return box

    def _build_log_group(self) -> QGroupBox:
        box    = QGroupBox("系統 Log")
        layout = QVBoxLayout(box)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "background:#0A0E14;border:1px solid #30363D;"
            "color:#E6EDF3;font-family:Consolas;font-size:11px;"
        )
        layout.addWidget(self.log_text)
        return box

    # ── 信號 & 定時器 ─────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        signals.log_message.connect(self._append_log)
        signals.stats_update.connect(self._update_stats)

    def _periodic_refresh(self) -> None:
        cnt = device_manager.connected_count
        self.conn_label.setText(str(cnt))
        self.ws_led.set_state(True)  # 伺服器在就亮

        # 裝置列表
        devices = [d for d in device_manager.all_devices() if d.connected]
        self._update_device_list(devices)

        # 效能統計
        stats = health_monitor.get_stats()
        self._update_stats(stats)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _append_log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {msg}")

    def _update_device_list(self, devices: list) -> None:
        while self.dev_layout.count() > 1:
            item = self.dev_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        for dev in devices:
            row   = QHBoxLayout()
            dot   = QLabel("●")
            dot.setStyleSheet(f"color:{dev.color};font-size:14px;")
            name  = QLabel(f"{dev.display_name}  {dev.browser}/{dev.os_name}")
            name.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:11px;")
            row.addWidget(dot); row.addWidget(name); row.addStretch()
            w = QWidget(); w.setLayout(row)
            self.dev_layout.insertWidget(self.dev_layout.count() - 1, w)

    def _update_stats(self, stats: dict) -> None:
        cpu = int(stats.get("cpu", 0))
        ram = int(stats.get("ram", 0))
        fps = self.canvas._fps_display

        self.cpu_bar.setValue(cpu);  self.cpu_val.setText(f"{cpu}%")
        self.ram_bar.setValue(ram);  self.ram_val.setText(f"{ram}%")
        self.fps_label.setText(str(fps))

        alert = f"color:{ACCENT_RED};"
        ok    = f"color:{ACCENT_GREEN};"
        self.cpu_val.setStyleSheet(alert if cpu > 80 else ok)
        self.ram_val.setStyleSheet(alert if ram > 80 else ok)

    def _show_qr_popup(self) -> None:
        """彈出大尺寸 QR Code 視窗"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
        if not QRCODE_PATH.exists():
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("QR Code — 手機掃描加入")
        dlg.setStyleSheet(f"background:{DARK_BG};")
        layout = QVBoxLayout(dlg)
        lbl = QLabel()
        px  = QPixmap(str(QRCODE_PATH)).scaled(
            420, 420,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        lbl.setPixmap(px)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        url_lbl = QLabel(self.server_url)
        url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        url_lbl.setStyleSheet(f"color:{ACCENT_BLUE};font-size:14px;padding:8px;")
        url_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(lbl)
        layout.addWidget(url_lbl)
        dlg.exec()

    def _refresh_qrcode(self) -> None:
        if QRCODE_PATH.exists():
            px = QPixmap(str(QRCODE_PATH)).scaled(
                190, 190,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.qr_label.setPixmap(px)
        else:
            self.qr_label.setText("QR Code 產生中…")


# ── GUI Log Handler ───────────────────────────────────────────────────────────

class GUILogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            signals.log_message.emit(self.format(record))
        except Exception:
            pass


# ── 進入點 ────────────────────────────────────────────────────────────────────

def run_gui(server_url: str) -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    # 全域深色樣式
    app.setStyle("Fusion")
    app.setStyleSheet(f"""
        QWidget {{ background:{DARK_BG}; color:{TEXT_PRIMARY};
                   font-family:"Microsoft JhengHei","Segoe UI",sans-serif; font-size:13px; }}
        QGroupBox {{ background:{DARK_PANEL}; border:1px solid {DARK_BORDER};
                     border-radius:6px; margin-top:8px; padding:8px; }}
        QGroupBox::title {{ color:{ACCENT_BLUE}; subcontrol-origin:margin; left:10px; padding:0 4px; }}
        QProgressBar {{ background:{DARK_BORDER}; border:none; border-radius:3px; height:8px; }}
        QProgressBar::chunk {{ background:{ACCENT_BLUE}; border-radius:3px; }}
        QScrollBar:vertical {{ background:{DARK_BG}; width:6px; }}
        QScrollBar::handle:vertical {{ background:{DARK_BORDER}; border-radius:3px; }}
        QPushButton:hover {{ background:{DARK_BORDER}; }}
    """)

    # GUI log handler
    handler = GUILogHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)

    window = MainWindow(server_url)
    window.show()
    app.exec()
