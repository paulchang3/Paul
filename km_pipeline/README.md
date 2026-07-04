# KM 知識輸入工作流 — 把文件拆解成一份多分頁知識 Excel

這是原本「Cornell / SMART / CODE 知識輸入表單」(HTML,寫入 Google Sheets)的
Python 版本。差別是:**不用手動填表**,直接把既有文件(PDF / Word / Excel /
HTML)丟進去,程式自動拆解成一份多分頁的 `.xlsx`,裡面同時包含:

- **WBS 樹狀結構**(知識的階層拆解)
- **行動樹**(偵測到的待辦/任務,含負責人、期限、優先級、狀態)
- **康乃爾筆記法、SMART 筆記法、CODE 筆記法** 三個分頁(沿用原表單的三種筆記法)

輸出的 `.xlsx` 欄位固定、有一份索引分頁說明結構,方便直接貼路徑給 Claude
讀取(用 `openpyxl` 或 `pandas.read_excel(sheet_name=None)` 一次讀六個分頁)。

## 運作原理

```
你的 .docx/.pdf/.html/.xlsx
        │
        ▼
  extract.py     ── 把不同格式統一轉成「區塊清單」(標題/段落/條列/表格列)
        │
        ▼
  decompose.py    ── 規則式拆解:依標題階層組 WBS、抓行動項目關鍵字、
        │             每個大章節產生康乃爾/SMART/CODE 筆記
        │
        ▼ (可選 --llm)
  llm_enhance.py  ── 呼叫本機 Ollama,把摘要/標籤/分類換成語意理解的結果
        │
        ▼
  build_excel.py  ── 寫出六個分頁的 .xlsx
```

**規則式拆解(預設)不需要任何外部服務,永遠能跑**,品質取決於文件本身的
標題/條列結構是否清楚。`--llm` 是加分項:失敗時(沒裝 Ollama、沒開機、
沒有模型)會印警告並保留規則式結果繼續跑,不會讓整個流程失敗。

## 快速開始(Windows,雙擊執行,零安裝門檻)

把 `.docx`/`.pdf`/`.html`/`.xlsx` 檔案**拖曳到 `km_pipeline/KM知識拆解.bat`**
上放開即可:

- 第一次執行會自動 `pip install` 必要套件(openpyxl、pypdf),並自動跑一次
  自我測試確認環境沒問題(裝失敗會印出訊息告訴你要手動裝什麼)。
- 通過後自動拆解你拖曳的檔案,產生同一個資料夾的「檔名_KM知識.xlsx」。
- 沒拖曳檔案、直接雙擊,只會顯示用法說明,不會出錯關掉視窗。

只想檢查環境(不處理任何檔案):雙擊執行前,先在資料夾內雙擊
`check_setup.py` 也可以(或見下方命令列方式)。

## 快速開始(命令列 / macOS / Linux)

```sh
pip install -r km_pipeline/requirements.txt   # openpyxl(必備)、pypdf(要處理 PDF 才需要)

python km_pipeline/check_setup.py             # 環境檢查:缺套件自動裝,並跑一次自我測試

python km_pipeline/main.py 我的文件.docx -o 輸出.xlsx
python km_pipeline/main.py 文件1.pdf 文件2.html 文件夾/ -o 輸出.xlsx   # 可混合多個檔案/資料夾

python km_pipeline/main.py 我的文件.docx -o 輸出.xlsx --llm            # 加開本機 Ollama 強化
```

## 輸出的六個分頁

| 分頁 | 內容 |
| --- | --- |
| `00_Index` | 產生時間、來源檔案、是否用了 LLM 強化,以及下面每個分頁的欄位說明(給 Claude 或協作者先看這頁) |
| `WBS_Tree` | `level1`~`level4` 是標題/條列的階層(愈右邊愈深,空白代表沒有更深層),`path` 是完整路徑,`content` 是該節點下的原文 |
| `Action_Tree` | `task`/`owner`/`deadline`/`priority`/`status`,抓不到的欄位留空 |
| `Cornell_Notes` | 每個大章節一列:`cues`(提示/問題)、`notes`(原文摘錄)、`summary`、`tags` |
| `SMART_Notes` | 從行動項目裡挑出「含可量化指標」的當作 SMART 目標候選;`achievable`/`relevant` 多半留白待人工補 |
| `CODE_Notes` | `capture`(原始摘錄)、`para`(PARA 分類猜測)、`distill`(關鍵洞見)、`express`/`express_type`(建議輸出草稿與形式) |

## 各格式怎麼被拆解

- **.docx**:讀 Word 的標題樣式(Heading 1~6)當作 WBS 層級,條列項目(`numPr`)
  當作子節點,表格轉成「儲存格 | 儲存格」的內容行。
- **.html**:`<h1>`~`<h6>` 當標題層級,`<ul>/<ol><li>` 當條列,`<table>` 逐列轉成內容行。
- **.xlsx**:每個工作表是一個 Level-1 節點;如果第一列看起來像任務清單的表頭
  (負責人/期限/狀態/優先級…),之後每一列會**直接**變成結構化的行動項目
  (不用再靠規則猜),這是 Excel 輸入最大的優勢。
- **.pdf**:用 `pypdf` 抽文字後,用「編號前綴(第X章/一、/1.1…)+ 短行/無句尾標點」
  猜標題。**已知限制**:沒有編號、又是純英文的短標題猜不出來(PDF 文字抽取
  拿不到字型大小資訊),這種文件會整份被當成一個節點,行動項目偵測仍正常運作。
  加密 PDF 與掃描影像型 PDF(整頁是圖片)一樣無法讀取文字。

## 行動項目怎麼被偵測到的

規則式偵測靠關鍵字與符號:條列符號(`- • ‣ ▪ ◦ □ ☐ [ ]`)、
「待辦/行動項目/TODO/需要/應於/截止/deadline」等字眼。抓到後再用正規表示式
猜負責人(`負責人:` `@`)、期限(日期格式或「本週/月底前」)、優先級
(緊急/高/低等字眼,預設中)、狀態(已完成/進行中/延期,預設待處理)。
**Excel 輸入的任務清單不吃這套規則**,只要表頭對得上就直接結構化擷取,
準確率高很多——如果你的來源允許,建議優先整理成 Excel 任務清單。

## 用 --llm 強化(選用)

需要本機已安裝並啟動 [Ollama](https://ollama.com)(可用倉庫根目錄的
`scripts/ollama-up.sh` 一鍵安裝啟動),預設模型 `qwen2.5:3b`,可用環境變數
`KM_LLM_MODEL` 或 `--llm-model` 覆寫:

```sh
ollama pull qwen2.5:3b
python km_pipeline/main.py 我的文件.docx -o 輸出.xlsx --llm
```

強化的是每個大章節的摘要、標籤、提問、PARA 分類、輸出形式建議——WBS 樹和
行動項目的擷取邏輯不受影響(那是結構性的,不需要語意理解)。

## 給 Claude 讀取

輸出檔案本身就是為了讓 LLM 好讀而設計的(固定欄位、`00_Index` 說明頁)。
把 `.xlsx` 路徑丟給 Claude,或請它用 `pandas`:

```python
import pandas as pd
sheets = pd.read_excel("輸出.xlsx", sheet_name=None)   # 一次讀六個分頁
sheets["WBS_Tree"]      # 知識樹
sheets["Action_Tree"]   # 行動項目
```

## 注意事項

- 如果 `-o` 指定的輸出路徑跟輸入資料夾同一個目錄,重跑時資料夾掃描
  (`main.py 資料夾/`)會把上一次的輸出 `.xlsx` 也當成輸入之一,建議輸出到
  另一個路徑,或每次用不同檔名。
- 規則式拆解的品質高度依賴文件的標題/條列結構;結構愈清楚,WBS 樹愈準。
- 這是啟發式(規則猜測)工具,不是語意理解,`achievable`/`relevant` 等
  需要判斷力的欄位預設留白,建議人工補齊或搭配 `--llm`。
