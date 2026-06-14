# Multi-Mobile QR Controller project_260614

獨立的上傳／開發空間。這個分支**不掛在 `brave-thompson-cjo4c7` 底下**，
也不含 Ollama / FMEA 等其他內容 —— 切到這個分支只會看到你這個專案。

## 上傳你的程式碼（用瀏覽器，不用 git）

1. 點這個連結，直接進到上傳畫面（目標就是**本分支根目錄**）：
   <https://github.com/paulchang3/Paul/upload/multi-mobile-qr-controller-260614>
2. 把 `E:\113_製作\700_Python\011_開發中_2603\Multi-Mobile QR Controller project`
   裡的檔案**拖進來**（`.py` / `.html` / `.js` / `.css` / `requirements.txt` 等程式碼檔；
   先**不要**傳 `venv/`、大圖、影片這類大檔）。
3. ⚠️ 拉到頁面**最底下**，按綠色的 **Commit changes** 按鈕。
   上次檔案沒進來，最可能就是漏了這一步 —— 拖檔只是「準備」，按下去才算真的送出。
4. 回來跟我說一聲「**傳好了**」。

我收到後會：讀懂程式 → 寫出主要 **SRS** → 加 headless 自我檢測 → 實作下面三個功能，
全部就做在這個獨立分支上。

## 三個要實作的功能

1. 每台手機在整個桌面（含延伸螢幕）最上層自由移動的圓圈。
2. 第一台手機 = 滑鼠：單擊選取、雙擊啟動、雙指上下滑動 = 滾輪。
3. 手機 UI 可上傳照片，當作圓圈顯示的圖。

---

> 為什麼放在 `paulchang3/Paul` 倉庫裡，而不是全新的獨立倉庫？
> 因為這個雲端 session 的讀取權限被鎖定在 `paulchang3/Paul`，
> 全新的獨立倉庫我反而讀不到、沒辦法接手。
> 這個分支是 **orphan branch**：自成一格、與 `Paul` 其他分支互不相干，
> 是「我讀得到」且「跟 brave-thompson 完全分離」兩者兼顧的做法。
