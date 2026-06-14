"""
tests/test_server.py - FastAPI HTTP & WebSocket 整合測試
執行：python -m pytest tests/ -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from httpx import AsyncClient, ASGITransport
from server import app


# ── HTTP 測試 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_status_endpoint() -> None:
    """/api/status 應回傳 200 與 status=ok"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "connected" in data
    assert "ts" in data


@pytest.mark.asyncio
async def test_devices_endpoint() -> None:
    """/api/devices 應回傳裝置列表"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/devices")
    assert resp.status_code == 200
    data = resp.json()
    assert "devices" in data
    assert isinstance(data["devices"], list)


@pytest.mark.asyncio
async def test_index_returns_html() -> None:
    """/ 應回傳 HTML（手機控制器頁面）"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_screen_returns_html() -> None:
    """/screen 應回傳 HTML"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/screen")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_qrcode_not_found_before_generate() -> None:
    """QR Code 未產生時應回傳 404"""
    from config import QRCODE_PATH
    # 若已存在則跳過此測試
    if QRCODE_PATH.exists():
        pytest.skip("QR Code 已存在")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/qrcode.png")
    assert resp.status_code == 404
