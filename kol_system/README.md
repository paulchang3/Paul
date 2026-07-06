# KOL 管理系統 v2.0（Google Apps Script）

以「**被動曝光 × 主動曝光**」雙軌策略重新設計的 KOL 關係管理系統。
策略分析與設計依據請先讀 **[STRATEGY.md](STRATEGY.md)**。

## v2.0 相對 v1.0 新增了什麼

| 類別 | 功能 | 自動化方式 |
| --- | --- | --- |
| 被動曝光 | 內容行事曆（構想→草稿→已發布 管線） | 主控台「內容」分頁管理 |
| 被動曝光 | RSS 情報彙整：抓取「情報來源」分頁的 RSS，彙整寄給自己 | 每週一 08:00 觸發器 |
| 被動曝光 | **情報來源連線檢查（v2.1）**：逐一測試每個 RSS 的連線與格式，結果寫回「連線狀態」欄 | 主控台/選單一鍵；每週彙整也會自動更新狀態 |
| 被動曝光 | 法規動態季報文件自動生成（由範本複製到季報資料夾） | 每季首日 09:00 觸發器 + 一鍵 |
| 被動曝光 | 電子報群發：對「訂閱電子報=Y」的 A/B 級 KOL 個人化寄送，自動寫回接觸紀錄與最近接觸日 | 主控台一鍵（寄送前檢查 Gmail 額度） |
| 被動曝光 | 公開洞察頁（Web App）：自動列出「已發布」內容 + 季報訂閱入口 | 全自動（取代 Google Sites） |
| 主動曝光 | 跟進節奏引擎：記錄接觸即自動排下次跟進（A:14 / B:30 / C:90 天），「下一步」自動變成「下次跟進鉤子」 | 全自動 |
| 主動曝光 | 每日跟進摘要信：到期＋逾期＋關係降溫警示（A>30 / B>60 / C>120 天未接觸） | 每日 08:00 觸發器 |
| 主動曝光 | 開發信一鍵草稿：6 種話術模板自動代入姓名/公司/鉤子，直接建立 Gmail 草稿 | 主控台一鍵 |
| 主動曝光 | 跟進日同步 Google Calendar（未來 60 天，不重複建立） | 主控台一鍵 |
| 儀表板 | 總覽頁：等級分布、合作階段漏斗、逾期/降溫數、內容管線存量、電子報訂閱數 | 自動統計 |
| 系統 | 自我檢查涵蓋觸發器狀態；自動修復會補齊 v2 新分頁與新欄位（**v1 資料完全相容**） | 一鍵 |

## 檔案清單

- `Code.gs` — 主程式（初始化、雙軌曝光模組、觸發器、資料 API）
- `Dashboard.html` — 主控台 GUI（總覽 / KOL / 待跟進 / 內容 / 自動化 五個分頁）
- `Insights.html` — 公開洞察頁範本（被動曝光對外頁面）
- `appsscript.json` — 專案設定檔（含明確的 OAuth 權限清單）
- `STRATEGY.md` — 曝光策略分析（本次重新設計的依據）

## 部署步驟（約 10 分鐘）

1. 開一個新的 **Google 試算表**（或沿用 v1.0 的試算表，資料相容）。
2. 「擴充功能」→「Apps Script」開啟指令碼編輯器。
3. 把 `Code.gs` 全部內容貼進編輯器的 `Code.gs`（覆蓋舊版）。
4. 左側「＋」新增 HTML 檔 **Dashboard**（不加副檔名），貼上 `Dashboard.html`。
5. 再新增 HTML 檔 **Insights**，貼上 `Insights.html`。
6. 「專案設定」→ 勾選「顯示 appsscript.json」，貼上本專案的 `appsscript.json`（v2.0 需要 Gmail / Calendar / 外部連線權限，這一步**必要**）。
7. 儲存後回到試算表重新整理，選單出現「🗂 KOL管理系統」。
8. 點「🚀 一鍵部署 / 初始化系統」→ 授權（v2.0 會多要求 Gmail、日曆、外部連線權限，用途見下方權限說明）。
9. **從 v1.0 升級者**：再點「🛠 自動修復系統」，會自動補上新分頁（內容行事曆／情報來源／電子報發送紀錄）與 KOL 名單的新欄位（訂閱電子報／曝光來源）。
10. 開啟主控台 →「自動化」分頁 → 點「**啟用全部自動化**」。
11. 到試算表「情報來源」分頁確認／補上 RSS 網址（官方來源預設留空停用，請自行填入後把啟用改為 Y）。
12. 「自動化」分頁 →「寄件與洞察頁設定」填入你的姓名、簽名檔、洞察頁標題與聯絡 Email。

## 啟用後系統會自動做的事

| 時間 | 動作 |
| --- | --- |
| 每天 08:00 | 寄「今日跟進摘要」給你：到期 KOL＋鉤子＋降溫警示（沒事項就不寄） |
| 每週一 08:00 | 抓取啟用中的 RSS 情報源，寄「每週情報彙整」給你（LinkedIn 貼文素材來源） |
| 每季首日 09:00 | 自動從範本建立本季「法規動態季報」文件，寄連結提醒你填寫 |
| 每次記錄接觸 | 自動更新最近接觸日、依等級排下次跟進日、把「下一步」寫入鉤子 |
| 每次寄電子報 | 自動為每位收件人寫入接觸紀錄並更新最近接觸日 |

## 公開洞察頁的部署（被動曝光用，選用）

1. 指令碼編輯器 →「部署」→「新增部署作業」→ 類型「網頁應用程式」。
2. 執行身分：**我**；存取權：
   - 只想自己預覽 → 「僅限自己」
   - **要對外分享洞察頁 → 「任何人」**
3. 部署後得到網址；分享時加上 `?view=insights`。
4. 安全設計：匿名訪客（或任何非擁有者）一律只會看到洞察頁（已發布內容清單），**不會**看到主控台或任何 KOL 名單資料；只有你本人開啟才會載入主控台。

## 權限說明（為什麼 v2.0 要這些授權）

| 權限 | 用途 |
| --- | --- |
| Gmail | 寄跟進摘要/情報彙整給你自己、寄電子報給訂閱 KOL、建立開發信草稿 |
| Calendar | 把跟進日建立為全天事件 |
| 外部連線（UrlFetch） | 抓取 RSS 情報源 |
| Drive / Docs | 資料夾結構、季報範本與季報文件生成 |
| 觸發器（ScriptApp） | 建立/移除每日、每週、每季的自動排程 |

## 疑難排解

### Q1：打開主控台看到的是「原始碼」，沒有 GUI？

`Dashboard.html` 這類檔案**不能直接打開**——在 GitHub 頁面、Raw 連結、下載後雙擊、或 Apps Script 編輯器裡看到的，本來就是原始碼。GUI 只存在於兩個入口：

1. **試算表側邊欄**：Google 試算表上方選單「🗂 KOL管理系統」→「🖥 開啟管理主控台」（前提：`Dashboard` HTML 檔已貼入**該試算表綁定的** Apps Script 專案並儲存）。
2. **Web App 網址**：指令碼編輯器「部署」→「新增部署作業」→「網頁應用程式」後產生的 `https://script.google.com/macros/s/…/exec` 網址。

檢查順序：
- 選單裡沒有「🗂 KOL管理系統」→ Code.gs 沒貼好或沒存檔，重新整理試算表頁面。
- 點選單報「找不到 Dashboard」→ HTML 檔名必須是 `Dashboard`（無副檔名），且與 Code.gs 在同一個專案。
- 確認你是從試算表的「擴充功能 → Apps Script」進入的專案，而不是 Drive 新增的獨立 Apps Script 專案。
- v2.1 起，若你直接用瀏覽器開啟 HTML 檔，會看到帶橘色警示條的「預覽模式」介面（不連資料），提示你改用正式入口。

### Q2：某個情報來源連不上（例如 ITRUSST 官網沒有 RSS）？

先用連線檢查定位問題：主控台「自動化」分頁 →「📡 執行連線檢查」（或試算表選單「📡 檢查情報來源連線」）。每個來源會得到一個狀態並寫回「情報來源」分頁：

| 狀態 | 意義 | 處理 |
| --- | --- | --- |
| ✅ 正常（N 則） | 可連線、可解析 | 不用處理 |
| ❌ HTTP 404 | 網址不存在 | 檢查網址拼字，或該站已改版 |
| ❌ HTTP 403 | 站方拒絕程式存取 | 換來源或用轉RSS工具 |
| ❌ 非 RSS/Atom 格式 | 填的是一般網頁網址，不是 feed | 用下面三種替代方案 |
| ⏸ 未填網址 | 只是佔位列 | 填入網址後把啟用改 Y |

**網站沒有提供 RSS 時的三種替代方案（以 ITRUSST 為例）：**

1. **arXiv feed（推薦，可直接貼入「情報來源」）**——arXiv API 回傳標準 Atom，系統原生支援：
   - 關鍵字 ITRUSST：
     `https://export.arxiv.org/api/query?search_query=all:ITRUSST&sortBy=submittedDate&sortOrder=descending&max_results=10`
   - 關鍵字 Transcranial Ultrasonic Stimulation：
     `https://export.arxiv.org/api/query?search_query=all:%22transcranial+ultrasonic+stimulation%22&sortBy=submittedDate&sortOrder=descending&max_results=15`
   - 追蹤作者（格式 `au:姓氏_名字首字母`，例如 Jean-François Aubry / Lennart Verhagen / Kim Butts Pauly）：
     `https://export.arxiv.org/api/query?search_query=au:aubry_j&sortBy=submittedDate&sortOrder=descending&max_results=10`
     `https://export.arxiv.org/api/query?search_query=au:verhagen_l&sortBy=submittedDate&sortOrder=descending&max_results=10`
     （同名作者多時可加關鍵字縮小：`search_query=au:aubry_j+AND+all:ultrasound`）
   - v2.1 已把前兩條加入種子清單；舊系統點「＋ 補充建議來源」即可補進。
2. **Google Scholar Alert**：建立「ITRUSST」或「Transcranial Ultrasonic Stimulation」關鍵字通知。注意 Scholar **沒有 RSS**，只能寄 Email 通知到你的信箱，無法接進本系統的每週彙整信。
3. **網站轉 RSS 工具**：用 [rss.app](https://rss.app)、[FetchRSS](https://fetchrss.com)、[PolitePol](https://politepol.com) 等把 ITRUSST 官網頁面轉成自訂 feed，產生的網址貼入「情報來源」即可（此法同樣適用 NotebookLM / n8n / Make 等其他工作流）。免費方案通常有更新頻率與數量限制。

## 誠實的限制

- **LinkedIn 無法自動發文**（官方 API 不開放個人自動發文）。系統做到「素材自動彙整＋內容排程管理」，貼文的最後一步是你自己。
- **Google Sites 無法程式化排版**，以 Web App 洞察頁取代（全自動、可分享網址）。
- **Gmail 每日寄送額度**：一般帳號約 100 封／日、Workspace 約 1,500 封／日。寄電子報前系統會檢查剩餘額度，不足會擋下並提示。
- RSS 來源品質不一，抓取失敗的來源會在情報彙整信中列出，請到「情報來源」分頁修正網址。

## 日常使用節奏建議

- **每天早上**：看 08:00 摘要信 → 對到期 KOL 一鍵產生開發信草稿 → 個人化後寄出 → 回主控台記錄接觸。
- **每週一**：看情報彙整信 → 挑 1–2 則寫成 LinkedIn 貼文 → 在「內容」分頁登記（構想→草稿→已發布）。
- **每季**：收到季報文件提醒 → 填寫 → 「自動化」分頁寄送電子報給 A/B 級訂閱名單。
- **隨時**：總覽分頁看漏斗與降溫警示，逾期數保持 0。
