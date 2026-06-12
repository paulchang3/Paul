# GitHub 整理指南:命名、編碼、分類、關聯超連結與自動化

本倉庫的整理規則與教學。每月 1 日會自動執行整理(見[第 5 節](#5-自動化本倉庫已啟用)),
平時只要照本指南的慣例做,倉庫就不會亂。

## 1. 命名(Naming)

| 對象 | 規則 | 好例子 | 壞例子 |
| --- | --- | --- | --- |
| 倉庫 | 小寫英文 + 連字號,看名字就知道內容 | `ollama-fmea-expert` | `Paul`、`test123`、`MyProject` |
| 資料夾 | 固定慣例:`docs/`、`scripts/`、`src/`、`tests/` | `docs/` | `新增資料夾(2)/` |
| 檔案 | 小寫英文、用 `-` 或 `_`、**不用空格** | `build_knowledge.py` | `新 版本 final(真的最終版).py` |
| 分支 | `類型/簡短描述` | `feature/excel-export`、`fix/rpn-rounding` | `dev2`、`asdf` |
| Commit 訊息 | `類型: 做了什麼`(動詞開頭、一句話) | `feat: 新增 RPN 批次計算`、`fix: 修正表格抽取漏列` | `update`、`改一改` |

常用 commit 類型:`feat`(新功能)、`fix`(修錯)、`docs`(文件)、`chore`(雜務)、`refactor`(重構)。

中文檔名 GitHub 可以用,但容易造成連結編碼問題與跨平台困擾——
**程式與設定檔一律英文;** 給人看的文件(Word、報告)放在固定資料夾內可用中文,
但要有英文資料夾路徑,例如 `fmea_expert/my_docs/FMEA知識範例.docx`。

## 2. 編碼(Encoding)

「編碼」有兩個常被混用的意思,兩個都要管:

**(a) 字元編碼:一律 UTF-8**
- 所有文字檔(.py、.md、.txt、.csv)存成 UTF-8,中文才不會變亂碼。
- 例外:要給 Excel 直接開的 CSV,存成「UTF-8 with BOM」(Python:`encoding="utf-8-sig"`)。
- 換行符號交給 Git 處理:本倉庫已放 [.gitattributes](../.gitattributes)(`* text=auto`),
  Windows/macOS 混用也不會整個檔案被標成變更。

**(b) 文件編號系統**(做 ISO 14971/QMS 文件管理特別重要):
- 給文件固定前綴與流水號:`SOP-001`(程序書)、`WI-001`(作業指導書)、
  `FRM-001`(表單)、`REC-20260612-001`(紀錄,含日期)。
- 檔名格式建議:`SOP-001_風險管理程序_v2.docx` —— 編號在前(排序整齊)、
  版本在後、日期用 `YYYYMMDD`(字典序 = 時間序)。
- 一個資料夾放一類編號,例如 `qms/sop/`、`qms/forms/`。

## 3. 分類(Classification)

由大到小四層:

1. **一個專案一個倉庫**:不同主題不要塞同一個倉庫;小工具可以集中到一個
   `tools` 倉庫,但要靠 README 分區說明。
2. **倉庫的 About 區塊**(倉庫頁右上角齒輪):
   - **Description** 一句話說明,例:`本機 Ollama 工具組 + ISO 14971 FMEA 風險管理 AI 專家(RAG)`
   - **Topics** 加 3–6 個標籤方便搜尋,例:`ollama`、`rag`、`fmea`、`iso-14971`、`llm`、`traditional-chinese`
3. **個人首頁**:
   - **Pinned**(個人頁面 Customize your pins)釘選最重要的 4–6 個倉庫。
   - 建一個與帳號同名的倉庫(`paulchang3/paulchang3`),它的 README 會顯示在
     你的個人首頁,可當作所有專案的「目錄頁」,放各倉庫的超連結與一句話介紹。
4. **倉庫內固定結構**:程式碼、`docs/`(文件)、`scripts/`(工具腳本)、
   `tests/`(測試);根目錄保持乾淨,只放 README、LICENSE 等入口檔案。

## 4. 關聯超連結(Cross-linking)

| 寫法 | 效果 | 範例 |
| --- | --- | --- |
| `[文字](相對路徑)` | 連到同倉庫檔案,**搬倉庫不會斷** | `[FMEA 範例](../fmea_expert/README.md)` |
| `#編號` | 在 Issue/PR/commit 訊息中連到 Issue 或 PR | `修正 #3 回報的問題` |
| 完整網址 | 跨倉庫連結 | `https://github.com/paulchang3/Paul` |
| 檔案頁按 `y` 鍵 | 把網址變成「永久連結」(含 commit SHA),日後檔案改了連結內容不變 | 引用規範條文時必用 |
| 網址加 `#L10-L20` | 連到程式碼第 10–20 行 | 程式碼審查、回報問題時用 |
| 長文件開頭放目錄 | `[第 2 節](#2-編碼encoding)` 連到標題錨點 | 本文件就是範例 |

原則:**README 是每個倉庫的大廳**——任何人(包括三個月後的你)
應該能從 README 出發,兩次點擊內到達任何重要檔案。
本倉庫另有自動產生的 [INDEX.md](../INDEX.md) 作為完整檔案目錄。

## 5. 自動化(本倉庫已啟用)

**每月自動整理** — [.github/workflows/monthly-tidy.yml](../.github/workflows/monthly-tidy.yml)
每月 1 日 09:00(台北時間)自動執行 [scripts/tidy_repo.py](../scripts/tidy_repo.py):

1. 重新產生 [INDEX.md](../INDEX.md)(全檔案目錄 + 最後更新日期)並自動提交;
2. 檢查檔名規則與所有 Markdown 相對連結是否失效;
3. 檢查帳號所有公開倉庫是否缺描述、缺 topics;
4. 把結果開成一張「📋 每月整理報告」Issue —— 你每月只要看這張 Issue 照單處理。

想立刻試跑:倉庫頁 → **Actions** → **monthly-tidy** → **Run workflow**。
(注意:GitHub 對 60 天無活動的倉庫會自動停用排程,收到通知信去 Actions 點一下啟用即可。)

**AI 深度整理 skill** — [.claude/skills/tidy-github/SKILL.md](../.claude/skills/tidy-github/SKILL.md):
在 Claude Code 開啟本倉庫後輸入 `/tidy-github`,AI 會跑報告、修失效連結、
提改名與分類建議(改名一定先徵求你同意)。

**@claude 留言助理** — [.github/workflows/claude.yml](../.github/workflows/claude.yml)
已安裝 [anthropics/claude-code-action](https://github.com/anthropics/claude-code-action):
在任何 Issue / PR 留言 `@claude 請…` 即可呼叫 AI 回答問題、修 bug、開 PR。
需先在倉庫 Settings → Secrets and variables → Actions 設定 `ANTHROPIC_API_KEY`
(或 Claude Pro/Max 訂閱者用 `claude setup-token` 產生的 `CLAUDE_CODE_OAUTH_TOKEN`),
詳見該檔案開頭的註解。搭配每月整理報告 Issue 使用特別方便——
直接在報告底下留言「@claude 請處理這份報告裡的問題」。

## 6. 這個倉庫現在就能做的三件事(手動,各 30 秒)

1. **改倉庫名**:Settings → General → Repository name,
   把 `Paul` 改成 `ollama-fmea-expert`(舊網址 GitHub 會自動轉址,不會斷)。
2. **換預設分支**:Settings → General → Default branch → 切到 `main`
   (我已建好 `main` 分支;`claude/...` 是工作分支,名字不適合當門面)。
3. **補 About**:倉庫頁右上齒輪,貼上第 3 節給的 Description 與 Topics。
