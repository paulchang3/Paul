#!/usr/bin/env python3
"""RAG 知識庫 MCP Server（stdio 傳輸）。

優先使用官方 ``mcp`` SDK（low-level ``Server``）；若未安裝則改用
``fastmcp``（或 ``mcp`` 套件內建的 ``mcp.server.fastmcp``）。兩種後端都
提供相同的 6 個工具、2 個資源與 1 個提示模板。

注意：stdio MCP server 的 **stdout 專供 JSON-RPC**，所有診斷訊息一律寫往
stderr，否則會破壞與用戶端的協定握手。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rag_backend import DEFAULT_COLLECTION, RAGBackend, default_db_path  # noqa: E402


# --- 偵測可用的 MCP 後端 ----------------------------------------------------
_BACKEND: str | None = None
try:
    import asyncio

    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types

    _BACKEND = "mcp"
except Exception:
    try:
        from fastmcp import FastMCP

        _BACKEND = "fastmcp"
    except Exception:
        try:
            from mcp.server.fastmcp import FastMCP  # type: ignore

            _BACKEND = "fastmcp"
        except Exception:
            _BACKEND = None


# --- 共用知識庫實例（延遲初始化，避免 import 時就載入模型）-----------------
_RAG: RAGBackend | None = None


def rag() -> RAGBackend:
    global _RAG
    if _RAG is None:
        _RAG = RAGBackend(default_db_path(), DEFAULT_COLLECTION)
    return _RAG


# --- Ollama 輔助（套件優先，否則退回標準函式庫 HTTP）-----------------------
def _ollama_host() -> str:
    host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
    if "://" not in host:
        host = "http://" + host
    return host.rstrip("/")


def _ollama_answer(query: str, context: str, model: str) -> str | None:
    """以 Ollama 生成回答；不可用時回傳 None。"""
    system = "你是知識庫助理，只根據提供的參考資料回答；若資料不足請明確說明。"
    user = f"參考資料:\n{context}\n\n問題: {query}"

    # 1) 優先使用官方 ollama 套件
    try:
        import ollama  # type: ignore

        resp = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp["message"]["content"]
    except Exception:
        pass

    # 2) 退回標準函式庫 HTTP（與 repo 的 ollama_client.py 同樣使用 OLLAMA_HOST）
    try:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        req = urllib.request.Request(
            _ollama_host() + "/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.load(resp)["message"]["content"]
    except Exception:
        return None


# --- 工具實作（與框架無關，皆回傳字串）------------------------------------
def do_add_document(content: str, source: str, tags: str = "") -> str:
    """加入文件，回傳 doc_id。"""
    metadata = {"tags": tags} if tags else {}
    doc_id = rag().add_document(content, source, metadata)
    return json.dumps(
        {"ok": True, "doc_id": doc_id, "source": source}, ensure_ascii=False
    )


def do_search_knowledge(query: str, n_results: int = 5) -> str:
    """語意搜尋，回傳相關文件列表。"""
    hits = rag().search(query, n_results=n_results)
    return json.dumps({"query": query, "results": hits}, ensure_ascii=False, indent=2)


def do_list_documents(limit: int = 20) -> str:
    """列出知識庫文件。"""
    return json.dumps(rag().list_documents(limit=limit), ensure_ascii=False, indent=2)


def do_delete_document(doc_id: str) -> str:
    """刪除指定文件。"""
    ok = rag().delete_document(doc_id)
    return json.dumps({"ok": ok, "doc_id": doc_id}, ensure_ascii=False)


def do_get_stats() -> str:
    """知識庫統計。"""
    return json.dumps(rag().get_stats(), ensure_ascii=False, indent=2)


def do_query_with_llm(query: str, model: str = "gemma4:latest") -> str:
    """RAG + Ollama 聯合查詢：先檢索 context，再用 LLM 生成回答。

    Ollama 不可用時只返回 context。
    """
    context = rag().query_with_context(query, top_k=3)
    answer = _ollama_answer(query, context, model)
    if answer is None:
        return "（Ollama 不可用，僅返回檢索內容）\n\n" + context
    return answer


def do_resource_stats() -> str:
    return json.dumps(rag().get_stats(), ensure_ascii=False, indent=2)


def do_resource_recent() -> str:
    return json.dumps(rag().list_documents(limit=10), ensure_ascii=False, indent=2)


def do_index_prompt(topic: str = "") -> str:
    subject = topic.strip() or "（請使用者說明文件主題）"
    return (
        "你正在協助建立 RAG 知識庫。請依下列步驟，把使用者的文件加入知識庫：\n"
        f"1. 主題：{subject}\n"
        "2. 請使用者貼上文件內容（可中英混合，UTF-8）。\n"
        "3. 為文件指定簡短的 source 標籤（例如 ISO13485_7.3）。\n"
        "4. 呼叫 add_document(content, source, tags) 完成索引。\n"
        "5. 以 search_knowledge 驗證該文件可被檢索到。"
    )


# --- 後端一：官方 mcp SDK（low-level Server + stdio）-----------------------
def _serve_mcp() -> None:
    server = Server("rag-knowledge-base")

    @server.list_tools()
    async def list_tools() -> "list[types.Tool]":
        return [
            types.Tool(
                name="add_document",
                description="加入一筆文件到知識庫，回傳 doc_id。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "文件內容"},
                        "source": {
                            "type": "string",
                            "description": "來源標籤，如 ISO13485_7.3",
                        },
                        "tags": {
                            "type": "string",
                            "description": "逗號分隔標籤（可選）",
                        },
                    },
                    "required": ["content", "source"],
                },
            ),
            types.Tool(
                name="search_knowledge",
                description="語意搜尋知識庫，回傳相關文件列表。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "查詢字串"},
                        "n_results": {
                            "type": "integer",
                            "description": "返回筆數",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="list_documents",
                description="列出知識庫文件（最新在前）。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "最多列出筆數",
                            "default": 20,
                        }
                    },
                },
            ),
            types.Tool(
                name="delete_document",
                description="刪除指定 doc_id 的文件。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "doc_id": {"type": "string", "description": "要刪除的文件 id"}
                    },
                    "required": ["doc_id"],
                },
            ),
            types.Tool(
                name="get_stats",
                description="回傳知識庫統計（總數 / 模型 / 路徑）。",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="query_with_llm",
                description="RAG + Ollama 聯合查詢：先檢索 context，再用 LLM 生成回答。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "問題"},
                        "model": {
                            "type": "string",
                            "description": "Ollama 模型名稱",
                            "default": "gemma4:latest",
                        },
                    },
                    "required": ["query"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: "dict | None"
    ) -> "list[types.TextContent]":
        args = arguments or {}
        if name == "add_document":
            text = do_add_document(
                args["content"], args["source"], args.get("tags", "")
            )
        elif name == "search_knowledge":
            text = do_search_knowledge(args["query"], int(args.get("n_results", 5)))
        elif name == "list_documents":
            text = do_list_documents(int(args.get("limit", 20)))
        elif name == "delete_document":
            text = do_delete_document(args["doc_id"])
        elif name == "get_stats":
            text = do_get_stats()
        elif name == "query_with_llm":
            text = do_query_with_llm(args["query"], args.get("model", "gemma4:latest"))
        else:
            text = json.dumps({"error": f"未知工具：{name}"}, ensure_ascii=False)
        return [types.TextContent(type="text", text=text)]

    @server.list_resources()
    async def list_resources() -> "list[types.Resource]":
        return [
            types.Resource(
                uri="knowledge://stats",
                name="知識庫統計",
                description="即時統計 JSON",
                mimeType="application/json",
            ),
            types.Resource(
                uri="knowledge://recent",
                name="最近文件",
                description="最近 10 筆文件",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri) -> str:
        target = str(uri)
        if target == "knowledge://stats":
            return do_resource_stats()
        if target == "knowledge://recent":
            return do_resource_recent()
        raise ValueError(f"未知資源：{target}")

    @server.list_prompts()
    async def list_prompts() -> "list[types.Prompt]":
        return [
            types.Prompt(
                name="index_document_prompt",
                description="引導使用者提供文件並自動索引到知識庫。",
                arguments=[
                    types.PromptArgument(
                        name="topic", description="文件主題（可選）", required=False
                    )
                ],
            )
        ]

    @server.get_prompt()
    async def get_prompt(
        name: str, arguments: "dict | None"
    ) -> "types.GetPromptResult":
        topic = (arguments or {}).get("topic", "")
        return types.GetPromptResult(
            description="索引文件引導",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text", text=do_index_prompt(topic)
                    ),
                )
            ],
        )

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )

    asyncio.run(_run())


# --- 後端二：fastmcp（簡潔 decorator API）---------------------------------
def _serve_fastmcp() -> None:
    mcp = FastMCP("RAG-知識庫")

    @mcp.tool()
    def add_document(content: str, source: str, tags: str = "") -> str:
        """加入一筆文件到知識庫，回傳 doc_id。"""
        return do_add_document(content, source, tags)

    @mcp.tool()
    def search_knowledge(query: str, n_results: int = 5) -> str:
        """語意搜尋知識庫，回傳相關文件列表。"""
        return do_search_knowledge(query, n_results)

    @mcp.tool()
    def list_documents(limit: int = 20) -> str:
        """列出知識庫文件（最新在前）。"""
        return do_list_documents(limit)

    @mcp.tool()
    def delete_document(doc_id: str) -> str:
        """刪除指定 doc_id 的文件。"""
        return do_delete_document(doc_id)

    @mcp.tool()
    def get_stats() -> str:
        """回傳知識庫統計（總數 / 模型 / 路徑）。"""
        return do_get_stats()

    @mcp.tool()
    def query_with_llm(query: str, model: str = "gemma4:latest") -> str:
        """RAG + Ollama 聯合查詢：先檢索 context，再用 LLM 生成回答。"""
        return do_query_with_llm(query, model)

    @mcp.resource("knowledge://stats")
    def stats_resource() -> str:
        """即時統計 JSON。"""
        return do_resource_stats()

    @mcp.resource("knowledge://recent")
    def recent_resource() -> str:
        """最近 10 筆文件。"""
        return do_resource_recent()

    @mcp.prompt()
    def index_document_prompt(topic: str = "") -> str:
        """引導使用者提供文件並自動索引到知識庫。"""
        return do_index_prompt(topic)

    mcp.run()


def _auto_install_and_restart() -> None:
    """缺 mcp/fastmcp 時自動 pip 安裝並重啟行程一次（自我修復）。

    「MCP 顯示離線」最常見的原因，就是用戶端啟動本 server 時找不到 MCP
    SDK，腳本隨即結束。這裡偵測到缺套件就自動安裝再重啟，省去手動步驟。

    * 可用環境變數 ``RAG_MCP_AUTO_INSTALL=0`` 關閉此行為。
    * 所有 pip 輸出一律送往 stderr，避免污染 stdout 的 JSON-RPC 通道。
    * 以 ``_RAG_MCP_BOOTSTRAPPED`` 旗標確保最多只自動安裝 / 重啟一次。
    """
    flag = os.environ.get("RAG_MCP_AUTO_INSTALL", "1").lower()
    if flag not in ("1", "true", "yes", "on"):
        return
    if os.environ.get("_RAG_MCP_BOOTSTRAPPED") == "1":
        return  # 已嘗試過，避免無限重啟

    print(
        "[rag_mcp_server] 未偵測到 mcp/fastmcp，嘗試自動安裝…"
        "（可設 RAG_MCP_AUTO_INSTALL=0 關閉）",
        file=sys.stderr,
    )
    installed_any = False
    for package in ("mcp", "fastmcp"):
        try:
            subprocess.check_call(
                [
                    sys.executable, "-m", "pip", "install",
                    "--disable-pip-version-check", package,
                ],
                stdout=sys.stderr,  # 切勿寫入 stdout（JSON-RPC 通道）
                stderr=sys.stderr,
            )
            installed_any = True
        except Exception as exc:
            print(f"[rag_mcp_server] 安裝 {package} 失敗：{exc}", file=sys.stderr)

    if not installed_any:
        print(
            "[rag_mcp_server] 自動安裝失敗，請手動執行："
            f"{sys.executable} -m pip install mcp fastmcp",
            file=sys.stderr,
        )
        return

    os.environ["_RAG_MCP_BOOTSTRAPPED"] = "1"
    print("[rag_mcp_server] 安裝完成，重新啟動伺服器…", file=sys.stderr)
    try:
        os.execv(sys.executable, [sys.executable, *sys.argv])
    except Exception as exc:  # execv 失敗（罕見）：請使用者重啟用戶端
        print(f"[rag_mcp_server] 自動重啟失敗，請重新啟動用戶端：{exc}", file=sys.stderr)


def main() -> int:
    if _BACKEND is None:
        _auto_install_and_restart()  # 成功時會 execv 取代行程，不會返回
        print(
            "錯誤：未安裝 mcp 或 fastmcp。請執行 install_deps.bat、"
            "`python check_setup.py --install`，或 `pip install mcp fastmcp`。",
            file=sys.stderr,
        )
        return 1
    print(f"[rag_mcp_server] 啟動中，MCP 後端 = {_BACKEND}", file=sys.stderr)
    if _BACKEND == "mcp":
        _serve_mcp()
    else:
        _serve_fastmcp()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
