"""
tests/test_device_manager.py - 裝置管理器單元測試
執行：python -m pytest tests/ -v
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 確保 import 路徑正確
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from device_manager import DeviceManager, Device


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def manager() -> DeviceManager:
    return DeviceManager()


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── 測試：基本連線 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_device(manager: DeviceManager) -> None:
    """測試裝置註冊"""
    device = await manager.register(
        ws_id="ws-001",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)",
        ip_address="192.168.1.100",
    )
    assert device.device_id is not None
    assert device.session_token is not None
    assert device.ws_id == "ws-001"
    assert device.os_name == "iOS"
    assert device.connected is True
    assert device.display_name == "手機 A"


@pytest.mark.asyncio
async def test_multiple_devices_get_different_colors(manager: DeviceManager) -> None:
    """測試多裝置取得不同顏色"""
    d1 = await manager.register(ws_id="ws-001")
    d2 = await manager.register(ws_id="ws-002")
    d3 = await manager.register(ws_id="ws-003")
    colors = {d1.color, d2.color, d3.color}
    assert len(colors) == 3, "前三台手機應該有不同顏色"


@pytest.mark.asyncio
async def test_disconnect(manager: DeviceManager) -> None:
    """測試裝置斷線"""
    device = await manager.register(ws_id="ws-001")
    dev = await manager.disconnect("ws-001")
    assert dev is not None
    assert dev.connected is False


@pytest.mark.asyncio
async def test_get_by_ws(manager: DeviceManager) -> None:
    """透過 ws_id 查找裝置"""
    await manager.register(ws_id="ws-abc")
    dev = manager.get_by_ws("ws-abc")
    assert dev is not None
    assert dev.ws_id == "ws-abc"


# ── 測試：安全驗證 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_token_verification(manager: DeviceManager) -> None:
    """正確 token 應通過驗證"""
    device = await manager.register(ws_id="ws-001")
    assert manager.verify_token("ws-001", device.session_token) is True
    assert manager.verify_token("ws-001", "wrong-token") is False


@pytest.mark.asyncio
async def test_validate_packet_correct(manager: DeviceManager) -> None:
    """合法封包驗證"""
    device = await manager.register(ws_id="ws-001")
    packet = {
        "type":      "move",
        "device_id": device.device_id,
        "token":     device.session_token,
        "dx": 1, "dy": 0,
    }
    assert manager.validate_packet(packet, "ws-001") is True


@pytest.mark.asyncio
async def test_validate_packet_wrong_device_id(manager: DeviceManager) -> None:
    """錯誤 device_id 應被拒絕"""
    device = await manager.register(ws_id="ws-001")
    packet = {
        "type":      "move",
        "device_id": "fake-device-id",
        "token":     device.session_token,
    }
    assert manager.validate_packet(packet, "ws-001") is False


# ── 測試：移動邊界 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_move_boundary(manager: DeviceManager) -> None:
    """移動不超出畫布邊界"""
    from config import CANVAS_WIDTH, CANVAS_HEIGHT
    device = await manager.register(ws_id="ws-001")
    # 向右移動超大距離
    for _ in range(1000):
        device.move(1, 0, speed=10.0)
    assert device.x <= float(CANVAS_WIDTH)

    # 向上移動超大距離
    for _ in range(1000):
        device.move(0, -1, speed=10.0)
    assert device.y >= 0.0


@pytest.mark.asyncio
async def test_set_position_boundary(manager: DeviceManager) -> None:
    """set_position 超出邊界時應被截斷"""
    from config import CANVAS_WIDTH, CANVAS_HEIGHT
    device = await manager.register(ws_id="ws-001")
    device.set_position(-999, 99999)
    assert device.x == 0.0
    assert device.y == float(CANVAS_HEIGHT)


# ── 測試：統計 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connected_count(manager: DeviceManager) -> None:
    """連線數統計"""
    assert manager.connected_count == 0
    await manager.register(ws_id="ws-001")
    await manager.register(ws_id="ws-002")
    assert manager.connected_count == 2
    await manager.disconnect("ws-001")
    assert manager.connected_count == 1


@pytest.mark.asyncio
async def test_snapshot(manager: DeviceManager) -> None:
    """快照格式正確"""
    device = await manager.register(ws_id="ws-001")
    snap = manager.snapshot()
    assert len(snap) == 1
    assert snap[0]["device_id"] == device.device_id
    assert "color" in snap[0]
    assert "x" in snap[0]
    assert "y" in snap[0]
