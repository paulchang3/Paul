"""
health_monitor.py - 系統健康監控與自我修復
每 HEALTH_CHECK_INTERVAL 秒執行一次全面檢查
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
from dataclasses import dataclass, field
from typing import Callable, Coroutine, Optional

import psutil

from config import (
    HEALTH_CHECK_INTERVAL,
    CPU_ALERT_THRESHOLD,
    RAM_ALERT_THRESHOLD,
    SERVER_PORT,
)

logger = logging.getLogger("health_monitor")


@dataclass
class HealthSnapshot:
    """單次健康檢查結果快照"""
    timestamp:     float = field(default_factory=time.time)
    cpu_percent:   float = 0.0
    ram_percent:   float = 0.0
    ram_used_mb:   float = 0.0
    port_open:     bool  = False
    ws_count:      int   = 0
    fps_actual:    float = 0.0
    errors:        list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return len(self.errors) == 0


class FPSCounter:
    """移動視窗 FPS 計算器"""

    def __init__(self, window: float = 1.0) -> None:
        self._window = window
        self._stamps: list[float] = []

    def tick(self) -> None:
        now = time.time()
        self._stamps.append(now)
        # 清除超出視窗的舊時間戳
        cutoff = now - self._window
        self._stamps = [t for t in self._stamps if t >= cutoff]

    @property
    def fps(self) -> float:
        return float(len(self._stamps))


# 全域 FPS 計數器（由 server.py 每幀呼叫 .tick()）
fps_counter = FPSCounter()


class HealthMonitor:
    """
    背景健康監控器。
    - 定期取樣 CPU / RAM / Port / WebSocket 狀態
    - 偵測異常時觸發 on_anomaly 回呼
    - 支援自訂修復策略（recovery_hooks）
    """

    def __init__(self) -> None:
        self._running: bool = False
        self._latest: Optional[HealthSnapshot] = None
        self._anomaly_callbacks: list[Callable[[HealthSnapshot], None]] = []
        self._recovery_hooks: list[Callable[[], Coroutine]] = []
        self._task: Optional[asyncio.Task] = None

    # ── 回呼註冊 ──────────────────────────────────────────────────────────────

    def on_anomaly(self, cb: Callable[[HealthSnapshot], None]) -> None:
        """註冊異常通知回呼（同步）"""
        self._anomaly_callbacks.append(cb)

    def add_recovery_hook(self, hook: Callable[[], Coroutine]) -> None:
        """註冊自動修復 async 函式"""
        self._recovery_hooks.append(hook)

    # ── 主迴圈 ────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """啟動監控背景 Task"""
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Health Monitor 已啟動（間隔 %ds）", HEALTH_CHECK_INTERVAL)

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                snapshot = await self._check()
                self._latest = snapshot
                if not snapshot.healthy:
                    logger.warning(
                        "健康異常: %s", ", ".join(snapshot.errors)
                    )
                    for cb in self._anomaly_callbacks:
                        try:
                            cb(snapshot)
                        except Exception as exc:
                            logger.error("Anomaly callback error: %s", exc)
                    # 執行修復
                    for hook in self._recovery_hooks:
                        try:
                            await hook()
                        except Exception as exc:
                            logger.error("Recovery hook error: %s", exc)
            except Exception as exc:
                logger.error("Health check exception: %s", exc)

            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

    async def _check(self) -> HealthSnapshot:
        snap = HealthSnapshot()

        # CPU
        snap.cpu_percent = psutil.cpu_percent(interval=0.1)
        if snap.cpu_percent > CPU_ALERT_THRESHOLD:
            snap.errors.append(f"CPU 使用率過高: {snap.cpu_percent:.1f}%")

        # RAM
        mem = psutil.virtual_memory()
        snap.ram_percent = mem.percent
        snap.ram_used_mb = mem.used / 1024 / 1024
        if snap.ram_percent > RAM_ALERT_THRESHOLD:
            snap.errors.append(f"RAM 使用率過高: {snap.ram_percent:.1f}%")

        # Port
        snap.port_open = _check_port(SERVER_PORT)
        if not snap.port_open:
            snap.errors.append(f"Port {SERVER_PORT} 未開啟")

        # FPS
        snap.fps_actual = fps_counter.fps

        return snap

    # ── 對外 API ──────────────────────────────────────────────────────────────

    @property
    def latest(self) -> Optional[HealthSnapshot]:
        return self._latest

    def get_stats(self) -> dict:
        """取得最新統計數據，供 GUI 顯示"""
        if self._latest is None:
            return {"cpu": 0.0, "ram": 0.0, "fps": 0.0, "port_ok": False}
        s = self._latest
        return {
            "cpu":       round(s.cpu_percent, 1),
            "ram":       round(s.ram_percent, 1),
            "ram_mb":    round(s.ram_used_mb, 1),
            "fps":       round(s.fps_actual, 1),
            "port_ok":   s.port_open,
            "healthy":   s.healthy,
            "errors":    s.errors,
            "ts":        s.timestamp,
        }


def _check_port(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """檢查本機 Port 是否正在監聽"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, OSError):
        return False


# 全域單例
health_monitor = HealthMonitor()
