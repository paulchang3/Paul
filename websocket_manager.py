"""
websocket_manager.py - WebSocket 連線池管理
負責：廣播、點對點傳訊、心跳、斷線清理
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect
from config import WS_HEARTBEAT_INTERVAL, WS_MAX_CONNECTIONS, WS_MESSAGE_QUEUE_SIZE

logger = logging.getLogger("ws_manager")


class ConnectionPool:
    """
    管理所有活動中的 WebSocket 連線。
    - 螢幕端 (screen)：桌面 GUI 內嵌頁面，接收全局廣播
    - 手機端 (mobile)：手機瀏覽器，雙向通訊
    """

    def __init__(self) -> None:
        # ws_id → WebSocket
        self._mobile_conns:  Dict[str, WebSocket] = {}
        self._screen_conns:  Dict[str, WebSocket] = {}
        # ws_id → asyncio.Queue（每條連線獨立訊息佇列）
        self._send_queues:   Dict[str, asyncio.Queue] = {}
        # ws_id → 傳送 Task
        self._sender_tasks:  Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    # ── 連線管理 ──────────────────────────────────────────────────────────────

    async def connect_mobile(self, ws_id: str, ws: WebSocket) -> bool:
        """
        接受手機端連線。
        超出最大連線數時拒絕並回傳 False。
        """
        async with self._lock:
            if len(self._mobile_conns) >= WS_MAX_CONNECTIONS:
                await ws.close(code=1008, reason="Server full")
                return False
            await ws.accept()
            self._mobile_conns[ws_id] = ws
            q: asyncio.Queue = asyncio.Queue(maxsize=WS_MESSAGE_QUEUE_SIZE)
            self._send_queues[ws_id] = q
            task = asyncio.create_task(self._sender_loop(ws_id, ws, q))
            self._sender_tasks[ws_id] = task
            logger.info("Mobile connected: %s (total=%d)", ws_id, len(self._mobile_conns))
            return True

    async def connect_screen(self, ws_id: str, ws: WebSocket) -> None:
        """接受螢幕端連線（不限數量）"""
        async with self._lock:
            await ws.accept()
            self._screen_conns[ws_id] = ws
            q: asyncio.Queue = asyncio.Queue(maxsize=WS_MESSAGE_QUEUE_SIZE)
            self._send_queues[ws_id] = q
            task = asyncio.create_task(self._sender_loop(ws_id, ws, q))
            self._sender_tasks[ws_id] = task
            logger.info("Screen connected: %s", ws_id)

    async def disconnect(self, ws_id: str) -> None:
        """清理指定連線的所有資源"""
        async with self._lock:
            self._mobile_conns.pop(ws_id, None)
            self._screen_conns.pop(ws_id, None)
            self._send_queues.pop(ws_id, None)
            task = self._sender_tasks.pop(ws_id, None)
            if task and not task.done():
                task.cancel()
        logger.info("Disconnected: %s", ws_id)

    # ── 傳送 ──────────────────────────────────────────────────────────────────

    async def _sender_loop(
        self, ws_id: str, ws: WebSocket, queue: asyncio.Queue
    ) -> None:
        """每條連線的獨立傳送協程，從 Queue 取出訊息後送出"""
        try:
            while True:
                msg: str = await queue.get()
                await ws.send_text(msg)
        except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
            pass
        except Exception as exc:
            logger.warning("Sender loop error [%s]: %s", ws_id, exc)

    def _enqueue(self, ws_id: str, payload: str) -> None:
        """把訊息放入指定連線的佇列（不等待）"""
        q = self._send_queues.get(ws_id)
        if q is not None:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                logger.debug("Queue full, dropping message for %s", ws_id)

    async def send_to(self, ws_id: str, data: dict) -> None:
        """點對點傳訊"""
        payload = json.dumps(data, ensure_ascii=False)
        self._enqueue(ws_id, payload)

    async def broadcast_to_screens(self, data: dict) -> None:
        """廣播給所有螢幕端"""
        if not self._screen_conns:
            return
        payload = json.dumps(data, ensure_ascii=False)
        for ws_id in list(self._screen_conns.keys()):
            self._enqueue(ws_id, payload)

    async def broadcast_to_all(self, data: dict) -> None:
        """廣播給所有連線（手機 + 螢幕）"""
        payload = json.dumps(data, ensure_ascii=False)
        for ws_id in list(self._mobile_conns) + list(self._screen_conns):
            self._enqueue(ws_id, payload)

    async def broadcast_to_mobiles(self, data: dict) -> None:
        """廣播給所有手機"""
        payload = json.dumps(data, ensure_ascii=False)
        for ws_id in list(self._mobile_conns.keys()):
            self._enqueue(ws_id, payload)

    # ── 心跳 ──────────────────────────────────────────────────────────────────

    async def start_heartbeat(self) -> None:
        """
        背景心跳 Task。
        每隔 WS_HEARTBEAT_INTERVAL 秒向所有手機發送 ping。
        """
        while True:
            await asyncio.sleep(WS_HEARTBEAT_INTERVAL)
            dead: list[str] = []
            ping_msg = json.dumps({"type": "ping", "ts": time.time()})
            for ws_id, ws in list(self._mobile_conns.items()):
                try:
                    self._enqueue(ws_id, ping_msg)
                except Exception:
                    dead.append(ws_id)
            for ws_id in dead:
                await self.disconnect(ws_id)

    # ── 統計 ──────────────────────────────────────────────────────────────────

    @property
    def mobile_count(self) -> int:
        return len(self._mobile_conns)

    @property
    def screen_count(self) -> int:
        return len(self._screen_conns)

    def all_mobile_ids(self) -> list[str]:
        return list(self._mobile_conns.keys())


# 全域單例
connection_pool = ConnectionPool()
