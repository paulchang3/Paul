# Evidence Log — Fingerprints Extracted from the Inputs

Every architectural claim in Phases 1–11 cites an evidence ID from this log.
Quotes are paraphrased/translated from the Riyalab website (`riyalab.com`) and
the *CloudEIP 使用手冊 v1.5* manual. Source column: **W** = website, **M** =
manual, **A** = API docs (manual §"CloudEIP 提供的 web service").

---

## 1. Deployment & cloud platform

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑CLOUD‑01 | "系統安裝在 Google 雲端平台" — installed on the Google cloud platform; customer buys no hardware | W | GCP hosting |
| E‑CLOUD‑02 | Trial domain `trial-cloudeip.appspot.com`; "預設使用的網域 appspot.com 在大陸是被屏蔽的" | M/A | **Google App Engine** (appspot.com is App Engine's domain) |
| E‑CLOUD‑03 | "超過 15 分鐘無人使用，便會自動 shutdown … 第一次使用 … 約 5~10 秒 … 重啟" | M | **App Engine standard, scale‑to‑zero** instance lifecycle + cold start |
| E‑CLOUD‑04 | "支援動態負載平衡，最高可同時啟動 20 個服務器" | W | App Engine automatic scaling (instance class / max‑instances) |
| E‑CLOUD‑05 | "將近十種伺服器 (DB Server、Web Server、Application Server…)" managed for you | W | Managed PaaS services, not customer‑run VMs |
| E‑CLOUD‑06 | "Google 保證 99.9%/月" uptime | W | App Engine SLA wording (99.95% in reality; marketing rounds it) |
| E‑CLOUD‑07 | "Google 沙箱架構，每家系統/資料完全區隔" | W | App Engine instance sandbox; **single‑tenant per customer** |
| E‑CLOUD‑08 | "一家公司專用一套獨立的雲端伺服器 … 獨立的資料庫" | W | **Single‑tenant** deployment model (one project/app per customer) |
| E‑CLOUD‑09 | "系統、資料皆即時同步備援至全球數十個 Google Data Centers" | W | Multi‑region managed replication (Datastore + Drive global) |
| E‑CLOUD‑10 | China edition needs a custom first‑level domain because appspot.com is blocked | M | Confirms App Engine default domain; custom‑domain mapping for CN |

## 2. Backend runtime & language

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑BACKEND‑01 | `getXml` returns `type=JDO_Resource` and `type=JDO_Member` | A | **JDO (Java Data Objects)** entity kinds → **Java** backend on Datastore |
| E‑BACKEND‑02 | Dates are "java 的時間數值，單位 1/1000 秒，從 1970-01-01 起算" (epoch millis) | M | JVM `System.currentTimeMillis()` semantics |
| E‑BACKEND‑03 | Validation regex described as "Java 的 regular expression (正則表示式)" | M | `java.util.regex` on the server |
| E‑BACKEND‑04 | `=`‑prefixed field formulas "交由 JavaScript 直譯器進行運算" | M | Embedded JS engine (Rhino/Nashorn on JVM, or client‑side JS) |
| E‑BACKEND‑05 | Web service base path `/ecm/webservice` | A | Servlet‑style endpoint ("ecm" = enterprise content mgmt module) |
| E‑BACKEND‑06 | Built on "CloudGears 雲端開發平台" using "CloudGears 的 XML 格式定義檔" | M | Proprietary **metadata/low‑code engine**; XML schema definitions |
| E‑BACKEND‑07 | Member data structure edited as XML: `<text>`, `<textbox>`, `<editor>` tags with `field`/`header`/`width` | M | Metadata‑driven schema; "毋須定義欄位型別" → dynamic typing over Datastore |

## 3. Datastore / persistence

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑DB‑01 | `JDO_*` kinds (see E‑BACKEND‑01) | A | **Google Cloud Datastore** (Firestore in Datastore mode) via JDO |
| E‑DB‑02 | "可隨時修改，新舊格式可同時並存，資料無需重整" — old & new form formats coexist, no migration | W/M | **Schema‑less document storage** (NoSQL), not table‑per‑form RDBMS |
| E‑DB‑03 | Form body shipped as JSON: `contentFields`, `dataFields`, `extraSheet1‑3`, `attachFiles` arrays | A | Document/aggregate persistence; one entity per form instance |
| E‑DB‑04 | "表單內容皆以 AES256 加密儲存於雲端 DB … 即使 Admin 也無法解密" | W | **Application‑layer AES‑256** on the JSON body before persist |
| E‑DB‑05 | "個人、企業屬性(含密碼) 均以 AES256 加密儲存" | W | Field‑level/credential encryption at app layer |
| E‑DB‑06 | Account key form `姓名(root/rd/rd0#account)`, dept `業務部(root/sales#dept)` | A | Hierarchical path used as identity key; org tree encoded in the ID |
| E‑DB‑07 | "可儲存管理上萬筆客戶資料" + strong full‑text → entities indexed, not joined | W | NoSQL entity model with search index, not relational joins |

## 4. Storage / files

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑FILE‑01 | "檔案儲存於 Google Drive … 數十個 Data Centers … 不佔用您的頻寬" | W | **Google Drive** as primary blob store; client streams from Google |
| E‑FILE‑02 | "文件附檔儲存於加密並隱藏的 Google 雲端硬碟，除非透過 CloudEIP 讀取，否則連系統管理員也不可視" | W | Service‑owned (hidden) Drive files; app‑mediated access |
| E‑FILE‑03 | Per‑file cap 7.5 MB on attach | M | Upload chunk/size policy (App Engine request limit era) |
| E‑FILE‑04 | "伺服器端 JPEG 壓縮 … 超過 300K 自動壓縮" + iPhone orientation fix | M | Server‑side image processing (Images API / ImageMagick) |
| E‑FILE‑05 | Built‑in "轉檔加密伺服器" converts to encrypted PDF | W | Headless document conversion service (Drive export or LibreOffice) |
| E‑FILE‑06 | Mobile reads from Google Drive / Dropbox / OneDrive / iCloud | W/M | Client‑side cloud file pickers (OAuth to 3rd‑party drives) |

## 5. Authentication & identity

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑AUTH‑01 | "使用 Google 帳號快速登入 … 認證交由 Google 執行" with OAuth popup | M | **Google OAuth / OpenID Connect** |
| E‑AUTH‑02 | Regular account+password login; password emailed on approval; AES‑256 stored | M/W | Local credential store (encrypted) alongside OAuth |
| E‑AUTH‑03 | Google login unlocks Google Calendar + Google Contacts read/write | M | OAuth scopes for Calendar/People APIs |
| E‑AUTH‑04 | Mobile app "綁定" stores an iOS/Android **Token** visible in 通訊錄 | M | **FCM registration token** bound to account |
| E‑AUTH‑05 | API key form `AIzaSyCzPwaYTxSrpXENaMnR97yxtyDyeFtE4yQ` | A | Google‑style API key (`AIza…`) used as tenant API key |
| E‑AUTH‑06 | Non‑email accounts allowed; account used as initial password | M | Username/password fallback identity |

## 6. Notifications / messaging

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑NOTIF‑01 | "即時通知是透過 Google 的 Firebase server 運作" | M | **Firebase Cloud Messaging (FCM)** |
| E‑NOTIF‑02 | WiFi ≈ instant; 3G/4G slower to save power | M | FCM priority/battery behaviour |
| E‑NOTIF‑03 | Tap notification → opens content without re‑login | W | Deep‑link + persisted session/token |
| E‑NOTIF‑04 | BPM forms send **email**; EIP functions do not; falls back to first email field | M | App Engine Mail API (or SendGrid) for transactional mail |
| E‑NOTIF‑05 | "每日工作提要/提醒" digest on event start/end days | M | Scheduled digest job (cron) |

## 7. Search

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑SEARCH‑01 | "全文檢索能力超強 … 一次搜尋出包含該關鍵字的所有類型資訊 … 任何欄位" | W | Cross‑entity inverted index over all form fields |
| E‑SEARCH‑02 | CloudISO "全文檢索可搜尋至檔案內容" | W | Document **content** extraction + indexing |
| E‑SEARCH‑03 | Combine full‑text + quick‑filter tags + info‑type filter | M | Faceted query over an index, not SQL LIKE |
| E‑SEARCH‑04 | Pure‑Google stack everywhere else | — | Most likely **App Engine Search API**; ElasticSearch less likely |

## 8. Async / scheduling / queueing

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑ASYNC‑01 | "流程處理是在雲端進行 … 填單人不需等待" (form dispatch is async) | M | Background task dispatch (Task Queue) after submit |
| E‑ASYNC‑02 | "系統每半點鐘進行一次逾時處理 … 從每天 8:00 到 23:30" | M | **Cron job** every 30 min for timeout/escalation sweep |
| E‑ASYNC‑03 | Deleted account's forms purged "當天晚上 11:00 後" | M | Nightly batch/cron cleanup |
| E‑ASYNC‑04 | Doc "於有效日期前一個月發出即將廢止通知" | M | Scheduled retention/expiry scan |

## 9. Frontend

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑FE‑01 | "全新世代的 SPA (Single‑Page Application) … 所有功能頁面皆不需 reload" | W | **SPA** architecture |
| E‑FE‑02 | "響應式網站技術 (Responsive Web Design)" auto‑adapts phone/tablet/desktop | W/M | RWD single codebase |
| E‑FE‑03 | Heavy tree/grid UI: 部門組織樹, 資源樹, 支出項目樹, data grids, popup windows ("彈出式視窗") | M | Widget‑toolkit UI (ExtJS / GWT / similar enterprise framework) |
| E‑FE‑04 | Client captures **GPS** at fill/sign via browser geolocation; disabled on http | M | Browser Geolocation API; HTTPS‑gated |
| E‑FE‑05 | Client drives camera/mic/video + cloud file pickers | W/M | HTML5 media capture + 3rd‑party SDKs |
| E‑FE‑06 | "使用說明會開啟在另一個新頁籤 … 不要關閉 … 直接切換" | M | SPA keeps state; help is a separate static site |
| E‑FE‑07 | Per‑user selectable "外觀" (skin/theme) | M | Theming layer in the client |

## 10. Security controls

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑SEC‑01 | HTTPS enforced; http disables GPS | W/M | TLS everywhere; secure‑context features |
| E‑SEC‑02 | "Client 與 Server 資料傳輸採用 TLS" | W | TLS in transit |
| E‑SEC‑03 | AES‑256 at rest for form bodies + credentials | W | App‑layer crypto (see E‑DB‑04/05) |
| E‑SEC‑04 | "通過 OWASP ZAP 完整的資安檢測" | W | DAST in the SDLC |
| E‑SEC‑05 | CloudISO reader: no‑download, **dynamic watermark**, **GPS lock**, **IP lock**, **time‑window lock**, minute‑accurate view logging | W | Controlled secure viewer (server‑rendered, policy‑gated) |
| E‑SEC‑06 | Digital signature = selfie + handwritten sign + GPS + time, "提升法律上不可否認效力" | M | Non‑repudiation evidence bundle per signature |

## 11. Workflow engine (detailed — see Phase 3)

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑WF‑01 | Step fields: 步驟/說明/簽核者/簽核條件/滑步條件/時限/數位簽章/保護/觸發程序 | M | Rich step descriptor model |
| E‑WF‑02 | Approver kinds: 特定人, 特定部門, 靜態角色, 動態角色, 填單人/部門/主管/上級, 簽核者上級, 內容欄位, 統計表格欄位, 留空(skip) | M | Polymorphic approver resolution |
| E‑WF‑03 | Dynamic role codes `sysCloudEipSender/Signer/Dept/Boss/SignerBoss` | M | Built‑in dynamic role registry |
| E‑WF‑04 | Conditions: 任一決, 任一通過決, 全員決, 徵詢任一, 徵詢全員, 過半同意, 超過¾同意 | M | Quorum/voting policy enum incl. **weighted/ratio** approval |
| E‑WF‑05 | Skip (滑步) expressions with `== != > >= < <= in !in`, ternary, `@resultValue/@psFields/@userFields/@fieldMax/@fieldMin/@fieldContains/@role/@applicant/@signerId/@approvers` | M | Expression language interpreter for routing |
| E‑WF‑06 | Timeout: auto‑approve / auto‑reject / mark‑overdue; abs datetime, time‑of‑day, n.n days (min 0.005d≈7min) | M | Escalation/timeout sub‑model |
| E‑WF‑07 | Reject to **any** earlier step; in‑progress (處理中) state; withdraw (抽單) notifies superior | M | Non‑linear state transitions |
| E‑WF‑08 | Sign‑time flow mutation (異動流程): add‑sign/cc/insert/reorder, **unlimited nesting**, fully logged with backup | M | Runtime‑editable process instance + immutable audit |
| E‑WF‑09 | Sign‑time content edit (修改內容 / 修改內容並同意), logged with original backup | M | Versioned content mutation under audit |
| E‑WF‑10 | Form‑as‑approver: 母單觸發子單; external program approval `appendResponse` | M/A | Sub‑process orchestration + external task agents |
| E‑WF‑11 | Trigger events distinguish 通過 (approved) vs 完畢 (approved or rejected) | M | Event taxonomy for post‑step hooks |
| E‑WF‑12 | Proxy/agent (代理管理) lets a delegate sign as a departed user, marked as proxy | M | Delegation model with attribution |

## 12. Form engine (detailed — see Phase 4)

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑FORM‑01 | Sections: 內容欄位(master, vertical, 1 row), 統計表格欄位(repeating, for stats), 額外表格1‑3 | M | Master‑detail + up to 3 extra detail tables per form |
| E‑FORM‑02 | Controls: 文字訊息, 單行/多行文字, 數字, 日期, 日期時間, 勾選框, 單選鈕, 下拉選單, 多項選擇器, 數位簽章, 檔案上傳, 選項編輯器, 標籤編輯器, 文件目錄, 客戶選擇器, 支出項目樹, 資源樹, 部門組織樹, 連結表單 | M | ~20 control types |
| E‑FORM‑03 | `@fn()` = compute once at fill; `=expr` = recompute on change via JS | M | Two formula evaluation phases |
| E‑FORM‑04 | Field props: 樞紐(pivot), 控制項, 預設內容, 參數選項, 標題, 欄位寬度(px), 必填, 保護, 統計欄位, 單位 | M | Field descriptor schema |
| E‑FORM‑05 | Validation rules incl. 統一編號/身分證/email, regex, min‑len, comparators, step targets `#fill`/`#sign`, reverse | M | Declarative validation block |
| E‑FORM‑06 | Dropdown options from `url=` external program or `sheetId=` Google Sheet; cascade via `trigger=` | M | External + Sheet‑backed option providers; dependent fields |
| E‑FORM‑07 | Customer selector binds to Google Sheet (`sheetId/page/searchCol/idCol/fields`) auto‑filling other fields | M | Lookup‑and‑populate from Sheets |
| E‑FORM‑08 | Encoded value formats: `名稱(識別碼#unknown)`, `[名稱(識別碼)]/n…` | A | Self‑describing value encoding inside JSON strings |
| E‑FORM‑09 | Print/mail‑merge via Google Sheet template (`template` tab) with `#formName/#sender/#content/#data()/#signature()/#step()/#formula()` tags → xlsx/PDF | M | Template‑driven document generation |
| E‑FORM‑10 | Import/export forms by `formId`; importing an existing id overwrites | M | Form definition portability |

## 13. Integration (detailed — see Phase 6)

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑INT‑01 | Web service `/ecm/webservice` with `apiKey/function/sender`, GET or POST | A | Single‑endpoint RPC‑over‑HTTP API |
| E‑INT‑02 | Functions: `getSubjectData, createSmartForm, updateSmartForm, showParameters, getXml, testGetOptions, appendCustomer, appendResponse` | A | Published API surface ("幾乎所有功能都支援 web service") |
| E‑INT‑03 | `callBackUrl` returns `function=flowReturn, subjectId, result(1/-1)` on completion | A | Webhook callback on flow completion |
| E‑INT‑04 | Trigger "呼叫外部 service" GET/POST; auto‑sends `sender/subjectId/result` | M | Outbound webhooks per step |
| E‑INT‑05 | Google Sheets read (stats) + write/delete rows; Drive; Firebase | M | Native Google Workspace connectors |
| E‑INT‑06 | "提供完整的 API 與異質系統 (ERP、HR、CRM…) 介接" | W | Positioned for EAI |
| E‑INT‑07 | Dynamic params to external URLs: `#accountId/#accountName/#companyId/#companyName` | M | Context propagation to integrations |

## 14. Mobile

| ID | Evidence | Source | What it implies |
|----|----------|--------|-----------------|
| E‑MOB‑01 | Native iOS + Android apps; primary job = receive push + bind account + quick‑launch | M | Thin native shell over the responsive web app |
| E‑MOB‑02 | "全功能都可在手機運行"; web handles all features responsively | W | Web‑first; app is a wrapper + push client |
| E‑MOB‑03 | Separate "大中華版" APK without Google base services (China) | M | China build avoids Google Play Services/FCM |
| E‑MOB‑04 | Device features: camera/mic/video, SD card, cloud drives | W/M | Hybrid/web capabilities, not heavy native logic |
| E‑MOB‑05 | Mobile web hides the 系統管理 area "for security" | M | Capability gating by client form factor |

---

### Cross‑cutting reading of the evidence

The evidence converges, with very little contradiction, on a **2014‑era
Google App Engine (Java) + Cloud Datastore + Drive + Firebase** monolith
generated by an in‑house metadata engine (CloudGears). The few ambiguities —
exact frontend framework (E‑FE‑03), search backend (E‑SEARCH‑04), and whether
the embedded JS evaluator runs client‑ or server‑side (E‑BACKEND‑04) — are
carried forward with explicit confidence ranges rather than guessed away.
