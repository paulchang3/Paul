"""
main.py - 程式進入點
執行順序：
  1. 環境自我檢查（installer.py）
  2. 取得本機 IP、產生 QR Code
  3. 啟動 FastAPI + Uvicorn（背景執行緒）
  4. 啟動健康監控
  5. 啟動 PySide6 GUI（主執行緒）
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Optional

# ── 優先確保環境就緒 ──────────────────────────────────────────────────────────
from installer import ensure_environment
if not ensure_environment(verbose=True):
    print("[main] 環境初始化失敗，程式結束")
    sys.exit(1)

# ── 現在可以安全 import 第三方套件 ────────────────────────────────────────────
import uvicorn

from config import SERVER_HOST, SERVER_PORT, QRCODE_PATH, BASE_DIR, LOGS_DIR
from qrcode_manager import generate_qrcode
from health_monitor import health_monitor


# ── 日誌系統初始化 ────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    """建立 logs/ 目錄並設定多檔案日誌處理器"""
    import logging.handlers
    LOGS_DIR.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)-20s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # 系統日誌（每日輪替）
    for log_name in ("system", "error", "connection", "performance"):
        fh = logging.handlers.TimedRotatingFileHandler(
            filename=str(LOGS_DIR / f"{log_name}.log"),
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG if log_name != "error" else logging.ERROR)
        fh.setFormatter(fmt)
        root.addHandler(fh)


_setup_logging()
logger = logging.getLogger("main")


# ── 取得本機 IP ───────────────────────────────────────────────────────────────

def get_local_ip() -> str:
    """
    取得區網 IP。
    優先嘗試 netifaces，fallback 到 socket UDP trick。
    """
    # 方法 1：netifaces
    try:
        import netifaces
        gateways = netifaces.gateways()
        default_gw = gateways.get("default", {})
        iface_info = default_gw.get(netifaces.AF_INET)
        if iface_info:
            iface_name = iface_info[1]
            addrs = netifaces.ifaddresses(iface_name)
            ipv4 = addrs.get(netifaces.AF_INET, [])
            if ipv4:
                return ipv4[0]["addr"]
    except Exception:
        pass

    # 方法 2：UDP socket trick
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        pass

    return "127.0.0.1"


def get_wifi_info() -> dict:
    """取得 WiFi 名稱（Windows netsh）"""
    info: dict = {"ssid": "N/A", "mac": "N/A"}
    try:
        import subprocess
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if "SSID" in line and "BSSID" not in line:
                info["ssid"] = line.split(":", 1)[-1].strip()
            if "Physical address" in line or "實體位址" in line:
                info["mac"] = line.split(":", 1)[-1].strip()
    except Exception:
        pass
    return info


# ── Uvicorn 伺服器（背景執行緒）──────────────────────────────────────────────

_server_thread: Optional[threading.Thread] = None
_server_loop:   Optional[asyncio.AbstractEventLoop] = None


def _run_server() -> None:
    """在獨立執行緒中啟動 Uvicorn + asyncio event loop"""
    global _server_loop

    _server_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_server_loop)

    async def _startup() -> None:
        # 啟動健康監控
        await health_monitor.start()

        # 啟動 Uvicorn
        config = uvicorn.Config(
            "server:app",
            host=SERVER_HOST,
            port=SERVER_PORT,
            log_level="warning",
            loop="asyncio",
            ws_ping_interval=20,
            ws_ping_timeout=20,
        )
        server = uvicorn.Server(config)
        await server.serve()

    _server_loop.run_until_complete(_startup())


def start_server_thread() -> None:
    global _server_thread
    _server_thread = threading.Thread(target=_run_server, daemon=True, name="UvicornThread")
    _server_thread.start()
    logger.info("Uvicorn 執行緒已啟動")


def wait_for_server(timeout: float = 15.0) -> bool:
    """等待伺服器 Port 開啟，超時回傳 False"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", SERVER_PORT), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.3)
    return False


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("Multi-Mobile QR Controller 啟動中...")

    # 1. 取得本機 IP
    local_ip = get_local_ip()
    server_url = f"http://{local_ip}:{SERVER_PORT}"
    logger.info("本機 IP：%s，服務 URL：%s", local_ip, server_url)

    # WiFi 資訊
    wifi = get_wifi_info()
    logger.info("WiFi SSID：%s，MAC：%s", wifi["ssid"], wifi["mac"])

    # 2. 產生 QR Code
    qr_path = generate_qrcode(server_url, QRCODE_PATH)
    if qr_path:
        logger.info("QR Code 已產生：%s", qr_path)
    else:
        logger.warning("QR Code 產生失敗，將繼續啟動")

    # 3. 啟動 Uvicorn 背景執行緒
    start_server_thread()

    # 4. 等待伺服器就緒
    ready = wait_for_server(timeout=15.0)
    if not ready:
        logger.error("伺服器在 15 秒內未能啟動，程式結束")
        sys.exit(1)
    logger.info("伺服器已就緒：%s", server_url)

    # 5. 啟動 GUI（主執行緒）
    crash_log = BASE_DIR / "crash.log"
    try:
        logger.info("正在載入 GUI 模組...")
        from gui import run_gui
        logger.info("GUI 模組載入成功，啟動視窗...")
        run_gui(server_url)
        logger.info("GUI 視窗已關閉")
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        logger.error("GUI 啟動失敗：%s", exc)
        logger.error("詳細錯誤：\n%s", tb)
        # 同時寫入 crash.log 方便查閱
        try:
            crash_log.write_text(
                f"GUI Crash at {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{tb}",
                encoding="utf-8",
            )
            print(f"\n[崩潰記錄] 已寫入 {crash_log}")
        except Exception:
            pass
        # GUI 失敗時改為無頭模式繼續服務
        logger.info("改為無 GUI 模式繼續，伺服器仍在運行")
        logger.info("手機請瀏覽：%s", server_url)
        print(f"\n{'='*50}")
        print(f"  GUI 啟動失敗，但伺服器仍在運行！")
        print(f"  手機瀏覽：{server_url}")
        print(f"  錯誤詳情：{crash_log}")
        print(f"{'='*50}\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("使用者中斷，程式結束")


if __name__ == "__main__":
    main()
