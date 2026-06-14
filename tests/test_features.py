"""
tests/test_features.py — 260614 新增三大功能的 headless 測試

涵蓋可在雲端（無 GUI / 非 Windows）驗證的純邏輯：
- 照片上傳儲存區 image_store
- 第一台手機（= 滑鼠控制者）判定 first_device / is_first
- Device.to_dict 含 index / image_url
- mouse_controller 在非 Windows 安全降級（不丟例外、不誤動游標）
- /api/image 上傳與下載端點（含 token 驗證、格式檢查）

GUI 覆蓋層與真實 SendInput 滑鼠動作無法在此環境測試，需在 Windows 上實機驗證。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from httpx import AsyncClient, ASGITransport

from device_manager import DeviceManager, device_manager
from image_store import ImageStore
from mouse_controller import mouse_controller
from server import app

# 1x1 透明 PNG 的合法 data URL
_PNG_1x1 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


# ── image_store ───────────────────────────────────────────────────────────────

def test_image_store_set_get_remove() -> None:
    store = ImageStore()
    assert store.has("dev1") is False
    assert store.set_data_url("dev1", _PNG_1x1) is True
    assert store.has("dev1") is True
    ct, raw = store.get("dev1")
    assert ct == "image/png"
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert store.version("dev1") > 0
    store.remove("dev1")
    assert store.has("dev1") is False
    assert store.get("dev1") is None


def test_image_store_rejects_bad_input() -> None:
    store = ImageStore(max_bytes=50)
    assert store.set_data_url("d", "not-a-data-url") is False
    assert store.set_data_url("d", "data:text/plain;base64,QQ==") is False  # 非圖片
    assert store.set_data_url("d", _PNG_1x1) is False  # 超過 max_bytes
    assert store.has("d") is False


# ── 第一台手機判定 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_first_device_is_lowest_index() -> None:
    mgr = DeviceManager()
    a = await mgr.register(ws_id="ws-a")
    b = await mgr.register(ws_id="ws-b")
    c = await mgr.register(ws_id="ws-c")
    assert mgr.first_device().device_id == a.device_id
    assert mgr.is_first(a) is True
    assert mgr.is_first(b) is False
    # 第一台離線 → b 遞補
    await mgr.disconnect("ws-a")
    assert mgr.first_device().device_id == b.device_id
    assert mgr.is_first(b) is True
    assert mgr.is_first(c) is False


@pytest.mark.asyncio
async def test_first_device_none_when_empty() -> None:
    mgr = DeviceManager()
    assert mgr.first_device() is None
    assert mgr.first_device_id() is None
    assert mgr.is_first(None) is False


# ── Device.to_dict ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_to_dict_has_index_and_image_url() -> None:
    mgr = DeviceManager()
    d = await mgr.register(ws_id="ws-a")
    snap = d.to_dict()
    assert snap["index"] == 0
    assert snap["image_url"] == ""          # 尚未上傳
    d.image_version = 123456
    assert d.to_dict()["image_url"] == f"/api/image/{d.device_id}?v=123456"


# ── mouse_controller 安全降級 ─────────────────────────────────────────────────

def test_mouse_controller_safe_on_non_windows() -> None:
    # 即使 active=True，非 Windows 也不該真的動到游標，且絕不丟例外
    is_win = sys.platform == "win32"
    was_active = mouse_controller.active
    try:
        mouse_controller.active = True
        # 這些呼叫不可丟例外
        moved  = mouse_controller.move_to_normalized(0.5, 0.5)
        clicked = mouse_controller.left_click()
        scrolled = mouse_controller.scroll(3)
        if not is_win:
            assert mouse_controller.available is False
            assert moved is False and clicked is False and scrolled is False
    finally:
        mouse_controller.active = was_active

    # active=False 時一律 no-op
    mouse_controller.active = False
    assert mouse_controller.move_to_logical(500, 350, 1000, 700) is False


# ── /api/image 端點 ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_image_upload_and_download() -> None:
    # 用全域 device_manager（server 使用同一個單例）註冊一台裝置
    dev = await device_manager.register(ws_id="ws-http-1", ip_address="1.2.3.4")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 正確 token → 200
        r = await client.post("/api/image", json={
            "device_id": dev.device_id, "token": dev.session_token, "data": _PNG_1x1,
        })
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True

        # 下載回來 → 200 + PNG bytes
        img = await client.get(f"/api/image/{dev.device_id}")
        assert img.status_code == 200
        assert img.headers["content-type"].startswith("image/png")
        assert img.content[:8] == b"\x89PNG\r\n\x1a\n"

        # 錯 token → 403
        r = await client.post("/api/image", json={
            "device_id": dev.device_id, "token": "wrong", "data": _PNG_1x1,
        })
        assert r.status_code == 403

        # 壞資料 → 400
        r = await client.post("/api/image", json={
            "device_id": dev.device_id, "token": dev.session_token, "data": "xxx",
        })
        assert r.status_code == 400

        # 不存在的裝置照片 → 404
        img = await client.get("/api/image/no-such-device")
        assert img.status_code == 404

    await device_manager.disconnect("ws-http-1")


@pytest.mark.asyncio
async def test_mouse_actions_only_for_first_device(monkeypatch) -> None:
    """功能 2 路由：click/dblclick/scroll 只在『第一台 + 滑鼠開啟』時觸發。"""
    import json as _json
    import server

    dev = await device_manager.register(ws_id="ws-mouse-1")
    base = {"device_id": dev.device_id, "token": dev.session_token}
    calls: list = []

    monkeypatch.setattr(server.mouse_controller, "active", True)
    monkeypatch.setattr(server.mouse_controller, "left_click",   lambda: calls.append("click") or True)
    monkeypatch.setattr(server.mouse_controller, "double_click", lambda: calls.append("dbl") or True)
    monkeypatch.setattr(server.mouse_controller, "scroll",       lambda a: calls.append(("scroll", a)) or True)

    # 是第一台 → 應觸發
    monkeypatch.setattr(server.device_manager, "is_first", lambda d: True)
    await server._handle_mobile_message("ws-mouse-1", _json.dumps({**base, "type": "click"}))
    await server._handle_mobile_message("ws-mouse-1", _json.dumps({**base, "type": "dblclick"}))
    await server._handle_mobile_message("ws-mouse-1", _json.dumps({**base, "type": "scroll", "amount": -3}))
    assert calls == ["click", "dbl", ("scroll", -3)]

    # 不是第一台 → 不應觸發
    calls.clear()
    monkeypatch.setattr(server.device_manager, "is_first", lambda d: False)
    await server._handle_mobile_message("ws-mouse-1", _json.dumps({**base, "type": "click"}))
    assert calls == []

    await device_manager.disconnect("ws-mouse-1")
