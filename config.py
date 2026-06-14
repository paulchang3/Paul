"""
config.py - 全域設定檔
集中管理所有設定常數與預設值
"""

import os
from pathlib import Path

# ── 專案根目錄 ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

# ── 伺服器設定 ───────────────────────────────────────────────────────────────
SERVER_HOST: str = "0.0.0.0"
SERVER_PORT: int = 8000
SERVER_RELOAD: bool = False
SERVER_WORKERS: int = 1

# ── WebSocket 設定 ────────────────────────────────────────────────────────────
WS_HEARTBEAT_INTERVAL: int = 5       # 心跳間隔（秒）
WS_MAX_CONNECTIONS: int = 100        # 最大連線數
WS_MESSAGE_QUEUE_SIZE: int = 256     # 每條連線的訊息佇列大小

# ── 測試畫布設定 ──────────────────────────────────────────────────────────────
CANVAS_WIDTH: int = 1000
CANVAS_HEIGHT: int = 700
DOT_RADIUS: int = 18
FPS_TARGET: int = 60

# ── 健康監控設定 ──────────────────────────────────────────────────────────────
HEALTH_CHECK_INTERVAL: int = 5       # 秒
CPU_ALERT_THRESHOLD: float = 90.0    # %
RAM_ALERT_THRESHOLD: float = 90.0    # %

# ── 目錄路徑 ─────────────────────────────────────────────────────────────────
LOGS_DIR: Path = BASE_DIR / "logs"
STATIC_DIR: Path = BASE_DIR / "static"
TEMPLATES_DIR: Path = BASE_DIR / "templates"
QRCODE_PATH: Path = BASE_DIR / "qrcode.png"

# ── 預設點顏色池（按連線順序分配）────────────────────────────────────────────
DOT_COLORS: list[str] = [
    "#FF4757",  # 紅
    "#2ED573",  # 綠
    "#1E90FF",  # 藍
    "#FFA502",  # 橙
    "#A29BFE",  # 紫
    "#00CEC9",  # 青
    "#FD79A8",  # 粉
    "#FDCB6E",  # 黃
    "#6C5CE7",  # 深紫
    "#55EFC4",  # 薄荷
]

# ── 日誌設定 ─────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
LOG_MAX_BYTES: int = 10 * 1024 * 1024   # 10 MB
LOG_BACKUP_COUNT: int = 7

# ── 安全設定 ─────────────────────────────────────────────────────────────────
SESSION_TOKEN_LENGTH: int = 32
UUID_VERSION: int = 4
MAX_PACKET_SIZE: int = 65536         # bytes，拒絕超大封包
