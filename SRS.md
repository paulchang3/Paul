# Multi-Mobile QR Controller — 軟體需求規格（SRS）

> 本文件說明程式「現在在做什麼」（主要 SRS）與 260614 新增的三大功能。

## 1. 目的與概念

在 Windows 桌面跑一個伺服器，產生 QR Code；同一個 Wi-Fi 下的多支手機掃描後，
用手機瀏覽器當「無線控制器」。每一台手機在桌面上對應一個彩色**圓圈**，
可即時移動。整套零安裝負擔（`installer.py` 會自動檢查並 pip 安裝相依套件）。

## 2. 系統架構

```
手機瀏覽器 (controller.html)
   │  WebSocket /ws/mobile（雙向）
   ▼
FastAPI + Uvicorn 伺服器（背景執行緒）  ──┐
   │  server.py 路由 / 訊息處理            │ HTTP /api/*, /qrcode.png
   ├── device_manager.py 裝置狀態/座標/Token │ HTTP / (controller), /screen
   ├── websocket_manager.py 連線池/廣播/心跳  │
   ├── image_store.py 上傳照片（記憶體）      │
   └── mouse_controller.py 真實滑鼠(SendInput)│
   ▼ 廣播 /ws/screen
桌面 GUI (gui.py, PySide6)           瀏覽器測試畫布 (screen.html)
   ├── 內嵌小地圖（QPainter 圓圈）
   └── 跨螢幕最上層覆蓋層 (screen_overlay.py)
```

主要執行流程（`main.py`）：環境檢查 → 取本機 IP → 產生 QR → 起 Uvicorn 背景執行緒
→ 等 Port 就緒 → 啟動健康監控 → 啟動 PySide6 GUI（主執行緒）。GUI 失敗會自動
退化成無頭模式，伺服器仍運作。

## 3. 元件職責

| 檔案 | 職責 |
| --- | --- |
| `config.py` | 全域常數（Port、畫布、顏色池、覆蓋層、安全參數）|
| `installer.py` | Python/pip/網路檢查、自動安裝相依套件、建立目錄 |
| `qrcode_manager.py` | 產生帶網址說明的 QR Code PNG |
| `device_manager.py` | 裝置 UUID/Token、顏色、座標、邊界裁切、第一台判定、照片版本 |
| `websocket_manager.py` | 連線池、每連線獨立傳送佇列、螢幕/手機廣播、心跳 ping/pong |
| `server.py` | HTTP 與 WebSocket 路由、手機訊息處理、滑鼠路由、照片上傳 |
| `health_monitor.py` | 每 5 秒取樣 CPU/RAM/Port/FPS，異常回呼與修復鉤子 |
| `gui.py` | 深色桌面 GUI：QR、連線數、效能、Log、小地圖、功能開關 |
| `screen_overlay.py` | 跨螢幕、最上層、滑鼠穿透的圓圈覆蓋層 |
| `mouse_controller.py` | Windows SendInput 驅動真實滑鼠（非 Windows 自動降級）|
| `image_store.py` | 上傳照片的記憶體儲存區（含型別/大小檢查）|

## 4. 通訊協定（WebSocket JSON）

**手機 → 伺服器**：`move{dx,dy,speed}`、`set_position{x,y}`、`reset`、`ping`/`pong`，
以及新增 `click`、`dblclick`、`scroll{amount}`。除 ping/pong 外都需附 `device_id`+`token`。

**伺服器 → 手機**：`init{device_id,token,color,display_name,canvas_w/h,x,y,is_first}`、
`ping`、`role{first_device_id}`。

**伺服器 → 螢幕**：`init/update/device_joined/device_left{devices:[...]}`；
每個裝置含 `x,y,color,display_name,connected,index,image_url`。

## 5. 既有需求（節錄）

- REQ-01 多手機同時連線（上限 `WS_MAX_CONNECTIONS=100`），各自一個彩色圓圈。
- REQ-02 三種控制：方向鍵 / 搖桿 / 拖曳。
- REQ-03 即時廣播（≤60FPS）給所有螢幕端，插值平滑。
- REQ-04 安全：每個控制封包需 device_id + session_token 比對，封包大小限制。
- REQ-05 心跳偵測斷線、座標邊界裁切、健康監控與自我修復鉤子。
- REQ-06 啟動自動裝環境；GUI 失敗退化為無頭模式不中斷服務。

## 6. 新增需求（260614）

- **REQ-N1 跨螢幕最上層移動**：每台手機的圓圈可在整個虛擬桌面（含延伸螢幕）
  最上層自由移動，無邊界限制。由 `screen_overlay.py` 以橫跨所有螢幕、最上層、
  半透明、**滑鼠穿透**的覆蓋層實作；GUI「螢幕覆蓋層」開關控制顯示。
- **REQ-N2 第一台手機 = 滑鼠**：連線序號最小（第一台）的手機可操控真實游標：
  - 觸控板滑動 → 移動游標（跨螢幕絕對座標 SendInput）。
  - **單擊** → 左鍵單擊（選擇）。
  - **雙擊** → 左鍵雙擊（啟動）。
  - **雙指上下滑動** → 滾輪上下捲動。
  第一台離線後，下一台自動遞補。安全預設為**關**，需在 GUI 勾選「第一台手機=滑鼠」。
  非 Windows 環境自動降級為無動作（方便雲端測試）。
- **REQ-N3 上傳照片當圓圈圖案**：手機 UI 可選照片上傳，前端先壓縮成 256×256，
  經 `POST /api/image`（需 token）存入記憶體，廣播後在小地圖、覆蓋層、`/screen`
  三處都把照片裁成圓形顯示。斷線即清除。

## 7. 測試

- `tests/test_device_manager.py`、`tests/test_server.py`：既有後端單元/整合測試。
- `tests/test_features.py`：新功能 headless 測試（照片儲存、第一台判定、滑鼠路由、
  上傳端點、非 Windows 安全降級）。
- 執行：`python -m pytest`（已附 `pytest.ini`，`asyncio_mode=auto`）。
- **無法在雲端/headless 驗證**：PySide6 GUI、跨螢幕覆蓋層、真實 SendInput 滑鼠動作 —
  需在 Windows 實機測試，步驟見 `WINDOWS_測試指南.md`。
