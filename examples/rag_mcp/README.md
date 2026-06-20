# RAG + MCP 範例：醫療器材法規知識庫

一個完整可執行的 **RAG（檢索增強生成）** + **MCP（Model Context Protocol）**
範例。封裝 ChromaDB + sentence-transformers 做語意檢索，並以標準 MCP server
（stdio）把知識庫包成 Claude Code / Cursor 可呼叫的工具。

> 設計重點：**沒有安裝任何套件也能跑**。缺 `chromadb` 時自動 fallback 到
> 記憶體儲存；缺 `sentence-transformers` 時退化為對中文友善的字元 bigram
> 關鍵字搜尋。`demo.py` 因此在任何 Python 3.10+ 環境都能直接執行。

## 檔案

| 檔案 | 說明 |
| --- | --- |
| `rag_backend.py` | RAG 核心引擎（`RAGBackend` 類別） |
| `rag_mcp_server.py` | 標準 MCP server（stdio）；`mcp` 不在則用 `fastmcp` |
| `demo.py` | 獨立演示腳本，不依賴 MCP |
| `mcp_config.json` | 供 Claude Code / Cursor 加入此 server 的配置 |
| `install_deps.bat` | Windows 一鍵安裝 + 自我檢查 |
| `check_setup.py` | 環境自我檢查 / 自動安裝 / 產生本機設定 |
| `run.bat` | Windows 啟動選單（Demo / 檢查 / 安裝 / 設定） |
| `create_desktop_shortcut.bat` | 在桌面建立「RAG 知識庫」捷徑（雙擊即可） |

## 環境需求

- Python 3.10+
- （選用）`chromadb`、`sentence-transformers`：啟用真正的向量檢索
- （選用）`mcp` 或 `fastmcp`：執行 MCP server
- （選用）`ollama` + 本機 Ollama 服務：`query_with_llm` 的 LLM 生成

## 安裝步驟

**Windows：** 直接執行

```bat
examples\rag_mcp\install_deps.bat
```

**任何平台（推薦，會順便做環境自我檢查）：**

```sh
python examples/rag_mcp/check_setup.py --install
```

**手動：**

```sh
pip install mcp fastmcp ollama chromadb sentence-transformers
```

> `all-MiniLM-L6-v2`（384 維）會在首次執行時自動下載（約 80 MB）。
>
> 此外，`rag_mcp_server.py` 在啟動時若偵測不到 `mcp`/`fastmcp`，會**自動 pip
> 安裝並重啟一次**，因此即使忘了先安裝，MCP server 通常也能自我修復。

## 執行 Demo

```sh
python examples/rag_mcp/demo.py
```

會索引 5 筆法規文件（ISO 13485 / IEC 62304 / ISO 14971 / IEC 82304），執行 3 個
語意查詢並印出統計。範例輸出：

```
[ADD]  ISO14971_4.1   → id: 5f3c1a9b
[SEARCH] 如何進行風險評估？
  1. (0.431) ISO14971_4.1: ISO 14971 第 4 章 風險分析：製造商須…
[STATS] 總文件: 5 | 模型: all-MiniLM-L6-v2 | 集合: rag_mcp_knowledge
```

> 分數含義依後端而定：安裝向量套件時為餘弦相似度，關鍵字後備模式則為
> bigram 重疊係數。

## 桌面捷徑（Windows，一鍵啟動選單）

1. 在檔案總管進入 `examples\rag_mcp\`，**雙擊 `create_desktop_shortcut.bat`**。
2. 桌面上會出現 **「RAG 知識庫」** 捷徑（圖示用 venv 的 `python.exe`）。
3. 之後雙擊該捷徑即開啟啟動選單 `run.bat`：

   ```
   [1] 執行 Demo      [2] 環境自我檢查
   [3] 安裝 / 更新套件  [4] 產生本機 MCP 設定
   ```

捷徑與選單都以 `%~dp0` 自動推導路徑（venv 在專案根目錄的 `.venv`），不寫死
磁碟代號，專案搬移後仍可用；找不到 venv 時自動改用系統 `python`。

> 也可不建捷徑，直接雙擊 `run.bat` 使用同一個選單。

## 在 Claude Code / Cursor 使用此 MCP server

把 `mcp_config.json` 中 `rag-knowledge-base` 這段，合併到用戶端的 MCP 設定
（Claude Desktop 為 `claude_desktop_config.json`），再重啟用戶端。請依你的
實際路徑調整 `command`、`args` 與 `PYTHONPATH`：

```json
{
  "mcpServers": {
    "rag-knowledge-base": {
      "command": "<專案>/.venv/Scripts/python.exe",
      "args": ["<專案>/examples/rag_mcp/rag_mcp_server.py"],
      "env": { "PYTHONPATH": "<專案>" }
    }
  }
}
```

- **Windows** 用 `.venv\Scripts\python.exe`；**macOS/Linux** 用
  `.venv/bin/python`。
- 資料庫預設存於 `{專案}/database/chroma/rag_example`，可用環境變數
  `RAG_DB_PATH` 覆寫。

## 可用 Tools

| Tool | 參數 | 說明 |
| --- | --- | --- |
| `add_document` | `content, source, tags` | 加入文件，回傳 `doc_id` |
| `search_knowledge` | `query, n_results=5` | 語意搜尋 |
| `list_documents` | `limit=20` | 列出文件（最新在前） |
| `delete_document` | `doc_id` | 刪除文件 |
| `get_stats` | — | 知識庫統計 |
| `query_with_llm` | `query, model="gemma4:latest"` | RAG + Ollama 聯合查詢 |

### Resources

- `knowledge://stats` — 即時統計 JSON
- `knowledge://recent` — 最近 10 筆文件

### Prompts

- `index_document_prompt` — 引導使用者提供文件並自動索引

### 範例呼叫（自然語言）

對連上此 server 的助理說：

- 「把這段內容加入知識庫，來源標 `ISO13485_7.3`」→ `add_document`
- 「知識庫裡關於風險評估的內容有哪些？」→ `search_knowledge`
- 「用 gemma4 根據知識庫回答：軟體安全分類怎麼分？」→ `query_with_llm`

## 疑難排解：MCP server 顯示「離線 / offline」

最快的方式是執行 `python examples/rag_mcp/check_setup.py`，它會逐項檢查並印出
修正建議與「套用本機路徑」的設定。常見原因：

1. **缺 `mcp` / `fastmcp` 套件（最常見）。** 本 server 啟動時會自動 pip 安裝並
   重啟一次；若仍失敗，請手動執行 `python check_setup.py --install` 或
   `pip install mcp fastmcp`。要關閉自動安裝可設環境變數
   `RAG_MCP_AUTO_INSTALL=0`。
2. **設定檔路徑錯誤。** `command` 必須指向你實際的直譯器：Windows 為
   `.venv\Scripts\python.exe`、macOS/Linux 為 `.venv/bin/python`。執行
   `python check_setup.py --config` 會直接印出套用本機路徑的設定，複製貼上即可。
3. **改完設定沒重啟用戶端。** Claude Desktop / Cursor 需完全重啟才會重新連線。
4. **第一次啟動較久。** 自動安裝或下載嵌入模型時，握手可能需數十秒；裝好後
   再重啟用戶端即可秒連。

## 與 Ollama 的關係

`query_with_llm` 會先以 `search_knowledge` 取得 context，再交給 Ollama 生成
回答；Ollama 不可用時只返回檢索到的 context。連線方式沿用本 repo 慣例的
`OLLAMA_HOST`（預設 `127.0.0.1:11434`），詳見根目錄
[`README.md`](../../README.md) 與 [`ollama_client.py`](../../ollama_client.py)。
