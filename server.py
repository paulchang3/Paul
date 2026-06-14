"""
server.py - FastAPI 主伺服器
提供 HTTP API 與 WebSocket 端點
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from fastapi.staticfiles import StaticFiles

from config import (
    BASE_DIR, STATIC_DIR, TEMPLATES_DIR, QRCODE_PATH,
    CANVAS_WIDTH, CANVAS_HEIGHT,
)
from device_manager import device_manager
from websocket_manager import connection_pool
from mouse_controller import mouse_controller
from image_store import image_store

logger = logging.getLogger("server")

app = FastAPI(title="Multi-Mobile QR Controller", version="1.0.0")

# ── Static files ─────────────────────────────────────────────────────────────
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _render_html(template_name: str) -> str:
    """讀取 HTML 檔案並替換 {{ canvas_w }} / {{ canvas_h }} 佔位符"""
    path = TEMPLATES_DIR / template_name
    html = path.read_text(encoding="utf-8")
    html = html.replace("{{ canvas_w }}", str(CANVAS_WIDTH))
    html = html.replace("{{ canvas_h }}", str(CANVAS_HEIGHT))
    return html

# ── 全域廣播頻率控制 ──────────────────────────────────────────────────────────
_last_broadcast: float = 0.0
_BROADCAST_INTERVAL: float = 1.0 / 60  # 60 FPS


# ── HTTP 路由 ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """手機連線入口頁"""
    try:
        return HTMLResponse(_render_html("controller.html"))
    except Exception as exc:
        logger.error("controller.html 載入失敗: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/screen", response_class=HTMLResponse)
async def screen() -> HTMLResponse:
    """桌面測試畫布頁"""
    try:
        return HTMLResponse(_render_html("screen.html"))
    except Exception as exc:
        logger.error("screen.html 載入失敗: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/qrcode.png")
async def get_qrcode() -> FileResponse:
    """下載 QR Code 圖片"""
    if not QRCODE_PATH.exists():
        raise HTTPException(status_code=404, detail="QR Code 尚未產生")
    return FileResponse(str(QRCODE_PATH), media_type="image/png")


@app.get("/api/status")
async def api_status() -> JSONResponse:
    """Health check endpoint"""
    return JSONResponse({
        "status":     "ok",
        "connected":  device_manager.connected_count,
        "devices":    device_manager.snapshot(),
        "ts":         time.time(),
    })


@app.get("/api/devices")
async def api_devices() -> JSONResponse:
    return JSONResponse({"devices": device_manager.snapshot()})


@app.post("/api/image")
async def api_upload_image(request: Request) -> JSONResponse:
    """
    手機上傳照片，顯示在自己的圓圈裡。
    Body(JSON)：{ "device_id", "token", "data": "data:image/...;base64,..." }
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON 解析失敗")

    device_id = str(body.get("device_id", ""))
    token     = str(body.get("token", ""))
    data_url  = str(body.get("data", ""))

    device = device_manager.verify_by_id(device_id, token)
    if device is None:
        raise HTTPException(status_code=403, detail="device_id 或 token 不正確")

    if not image_store.set_data_url(device_id, data_url):
        raise HTTPException(status_code=400, detail="照片格式不支援或過大")

    # 更新版本並通知所有螢幕重繪
    device.image_version = image_store.version(device_id)
    await connection_pool.broadcast_to_screens({
        "type":    "update",
        "devices": device_manager.snapshot(),
        "ts":      time.time(),
    })
    return JSONResponse({"ok": True, "image_url": f"/api/image/{device_id}?v={device.image_version}"})


@app.get("/api/image/{device_id}")
async def api_get_image(device_id: str) -> Response:
    """取得某裝置上傳的照片。"""
    item = image_store.get(device_id)
    if item is None:
        raise HTTPException(status_code=404, detail="此裝置尚未上傳照片")
    content_type, raw = item
    return Response(content=raw, media_type=content_type,
                    headers={"Cache-Control": "max-age=3600"})


# ── WebSocket 端點 ─────────────────────────────────────────────────────────────

@app.websocket("/ws/mobile")
async def ws_mobile(websocket: WebSocket) -> None:
    """
    手機端 WebSocket。
    握手完成後：
    1. 登記裝置
    2. 回傳 init 訊息（含 device_id, token, color）
    3. 進入訊息迴圈
    """
    ws_id = str(uuid.uuid4())
    ua = websocket.headers.get("user-agent", "")
    ip = websocket.client.host if websocket.client else "unknown"

    accepted = await connection_pool.connect_mobile(ws_id, websocket)
    if not accepted:
        return

    device = await device_manager.register(ws_id, user_agent=ua, ip_address=ip)

    # 回傳初始化資訊給手機
    await connection_pool.send_to(ws_id, {
        "type":         "init",
        "device_id":    device.device_id,
        "token":        device.session_token,
        "color":        device.color,
        "display_name": device.display_name,
        "canvas_w":     CANVAS_WIDTH,
        "canvas_h":     CANVAS_HEIGHT,
        "x":            device.x,
        "y":            device.y,
        "is_first":     device_manager.is_first(device),
    })

    # 通知所有螢幕有新裝置加入
    await connection_pool.broadcast_to_screens({
        "type":    "device_joined",
        "devices": device_manager.snapshot(),
    })
    # 通知所有手機「誰是第一台（滑鼠）」
    await _broadcast_role()

    logger.info("Mobile init: %s (%s)", device.display_name, ip)

    try:
        async for raw in websocket.iter_text():
            await _handle_mobile_message(ws_id, raw)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Mobile WS error [%s]: %s", ws_id, exc)
    finally:
        dev = await device_manager.disconnect(ws_id)
        await connection_pool.disconnect(ws_id)
        if dev:
            image_store.remove(dev.device_id)
        # 通知螢幕端更新
        await connection_pool.broadcast_to_screens({
            "type":    "device_left",
            "devices": device_manager.snapshot(),
        })
        # 第一台可能已換人，重新廣播角色
        await _broadcast_role()
        if dev:
            logger.info("Mobile disconnected: %s", dev.display_name)


@app.websocket("/ws/screen")
async def ws_screen(websocket: WebSocket) -> None:
    """桌面螢幕端 WebSocket，接收全域廣播"""
    ws_id = str(uuid.uuid4())
    await connection_pool.connect_screen(ws_id, websocket)

    # 初始化時推送目前裝置快照
    await connection_pool.send_to(ws_id, {
        "type":    "init",
        "devices": device_manager.snapshot(),
        "canvas_w": CANVAS_WIDTH,
        "canvas_h": CANVAS_HEIGHT,
    })

    try:
        async for _ in websocket.iter_text():
            pass  # 螢幕端只接收，不需處理傳入訊息
    except WebSocketDisconnect:
        pass
    finally:
        await connection_pool.disconnect(ws_id)


# ── 訊息處理 ──────────────────────────────────────────────────────────────────

async def _broadcast_role() -> None:
    """告訴所有手機目前「第一台（= 滑鼠控制者）」是誰。"""
    await connection_pool.broadcast_to_mobiles({
        "type":            "role",
        "first_device_id": device_manager.first_device_id(),
    })


def _drive_cursor(device) -> None:
    """若該裝置是第一台且滑鼠控制已開啟，把真實游標移到它的位置。"""
    if mouse_controller.active and device_manager.is_first(device):
        mouse_controller.move_to_logical(device.x, device.y, CANVAS_WIDTH, CANVAS_HEIGHT)


async def _handle_mobile_message(ws_id: str, raw: str) -> None:
    """
    處理手機端傳入訊息。
    支援以下 type：move / set_position / pong / ping
    """
    global _last_broadcast, _BROADCAST_INTERVAL

    try:
        data: dict = json.loads(raw)
    except json.JSONDecodeError:
        logger.debug("Invalid JSON from %s", ws_id)
        return

    # 大小限制
    if len(raw) > 4096:
        logger.warning("Oversized packet from %s, ignored", ws_id)
        return

    msg_type = data.get("type", "")

    if msg_type == "pong":
        dev = device_manager.get_by_ws(ws_id)
        if dev:
            dev.touch()
        return

    if msg_type == "ping":
        await connection_pool.send_to(ws_id, {"type": "pong", "ts": time.time()})
        return

    # 安全驗證（move / set_position 都需要 token）
    if not device_manager.validate_packet(data, ws_id):
        logger.warning("Invalid packet from %s (type=%s)", ws_id, msg_type)
        return

    device = device_manager.get_by_ws(ws_id)
    if device is None:
        return

    if msg_type == "move":
        dx    = float(data.get("dx",    0))
        dy    = float(data.get("dy",    0))
        speed = float(data.get("speed", 1.0))
        speed = max(0.1, min(5.0, speed))  # 限制速度範圍
        device.move(dx, dy, speed)
        _drive_cursor(device)

    elif msg_type == "set_position":
        x = float(data.get("x", device.x))
        y = float(data.get("y", device.y))
        device.set_position(x, y)
        _drive_cursor(device)

    elif msg_type == "reset":
        device.set_position(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2)
        _drive_cursor(device)

    # ── 滑鼠動作（只有第一台手機 + 已開啟滑鼠控制才生效）──────────────────────
    elif msg_type in ("click", "dblclick", "scroll"):
        if mouse_controller.active and device_manager.is_first(device):
            if msg_type == "click":
                mouse_controller.left_click()
            elif msg_type == "dblclick":
                mouse_controller.double_click()
            else:  # scroll
                amount = int(max(-30, min(30, int(float(data.get("amount", 0))))))
                if amount:
                    mouse_controller.scroll(amount)
        # 滑鼠動作不需要廣播給螢幕
        return

    # 頻率限制廣播（最多 60 FPS）
    now = time.time()
    if now - _last_broadcast >= _BROADCAST_INTERVAL:
        _last_broadcast = now
        await connection_pool.broadcast_to_screens({
            "type":    "update",
            "devices": device_manager.snapshot(),
            "ts":      now,
        })


# ── 啟動 / 關閉事件 ────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    """啟動時建立心跳背景 Task"""
    asyncio.create_task(connection_pool.start_heartbeat())
    logger.info("FastAPI 伺服器已啟動")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("FastAPI 伺服器正在關閉")
