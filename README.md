# Multi-Mobile QR Controller

掃 QR Code，讓多支手機變成桌面的無線控制器。每台手機在桌面上是一個彩色**圓圈**，
可即時移動；第一台手機還能當**真實滑鼠**，而且圓圈裡可以放你**上傳的照片**。

> 本分支 `multi-mobile-qr-controller-260614` 在原專案上新增三大功能（見下）。
> 程式理解與規格：[`SRS.md`](SRS.md)。Windows 實機測試步驟：[`WINDOWS_測試指南.md`](WINDOWS_測試指南.md)。

## 快速開始（Windows）

雙擊 `deploy.bat`，或：

```bat
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

手機連同一個 Wi-Fi → 掃描 GUI 上的 QR Code → 開始控制。

## 260614 新增三大功能

1. **跨螢幕最上層圓圈** — 每台手機的圓圈疊在整個桌面（含延伸螢幕）最上層、
   滑鼠穿透、無邊界移動。GUI「螢幕覆蓋層」開關控制。
2. **第一台手機 = 滑鼠** — 第一台手機可操控真實游標：滑動移動、**單擊**選擇、
   **雙擊**啟動、**雙指上下**捲動。GUI「第一台手機=滑鼠」開關控制（安全預設為關）。
3. **上傳照片當圓圈圖案** — 手機可上傳照片，裁成圓形顯示在自己的圓圈裡
   （小地圖、覆蓋層、`/screen` 三處同步）。

## 開發 / 測試

```sh
python -m pytest          # 後端與新功能 headless 測試（雲端可跑）
```

GUI、覆蓋層、真實滑鼠需在 Windows 實機驗證（headless 環境無法）。

## 架構一覽

`main.py` 啟動 → `installer.py` 裝環境 → `qrcode_manager.py` 出 QR →
`server.py`（FastAPI）跑 HTTP/WebSocket，協調 `device_manager` / `websocket_manager` /
`image_store` / `mouse_controller` → `gui.py`（PySide6）顯示 + `screen_overlay.py` 覆蓋層。
手機端為 `templates/controller.html`，瀏覽器測試畫布為 `templates/screen.html`。
完整說明見 [`SRS.md`](SRS.md)。
