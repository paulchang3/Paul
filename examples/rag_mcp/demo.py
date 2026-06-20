#!/usr/bin/env python3
"""RAG 範例 Demo（不依賴 MCP，直接呼叫 RAGBackend）。

執行：
    python examples/rag_mcp/demo.py

流程：初始化後端 → 批次索引 5 筆醫療器材法規文件 → 執行 3 個搜尋查詢
→（若 Ollama 可用）以 RAG + LLM 生成回答 → 顯示統計報告。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rag_backend import DEFAULT_COLLECTION, RAGBackend, default_db_path  # noqa: E402


# 5 筆醫療器材法規文件片段（source 標籤, 內容）
DOCUMENTS: list[tuple[str, str]] = [
    (
        "ISO13485_7.3",
        "ISO 13485 第 7.3 節 設計與開發：醫療器材製造商須建立設計與開發程序，"
        "涵蓋設計規劃、設計輸入、設計輸出、設計審查、設計驗證、設計確效、"
        "設計移轉與設計變更管制。設計輸入應包含功能、性能、安全與法規要求，"
        "並保留設計歷史檔案（DHF）作為符合性證據。",
    ),
    (
        "IEC62304_5.1",
        "IEC 62304 第 5.1 節 軟體開發計畫：須為醫療器材軟體建立軟體開發計畫，"
        "定義開發生命週期模型、活動與任務、可交付文件、需求追溯、組態管理與"
        "問題解決流程。計畫須依軟體安全分類（A/B/C）決定所需執行的活動，並隨"
        "專案進展持續更新。",
    ),
    (
        "ISO14971_4.1",
        "ISO 14971 第 4 章 風險分析：製造商須針對醫療器材識別預期用途與安全"
        "有關特性，系統化辨識已知與可預見的危害（hazard），並估計每個危害情境"
        "的風險（風險評估）。輸入包含臨床使用情境、使用者誤用與單一故障狀況，"
        "輸出記錄於風險管理檔案。",
    ),
    (
        "IEC82304_5.4",
        "IEC 82304-1 第 5.4 節 軟體安全分類：針對健康軟體產品，須依其可能造成"
        "傷害的嚴重度進行安全考量與風險控制，並驗證軟體系統需求涵蓋安全、"
        "保全（security）與資料保護。製造商應確保產品說明與使用環境假設清楚"
        "記載。",
    ),
    (
        "ISO13485_8.3",
        "ISO 13485 第 8.3 節 不合格品控制：須建立不合格品管制程序，確保不符合"
        "要求的產品被識別、記錄、評估、隔離並決定處置方式（重工、讓步接收、"
        "報廢或回收）。對已交付的不合格品須評估影響並採取矯正措施，必要時依"
        "法規通報主管機關。",
    ),
]

QUERIES = [
    "如何進行風險評估？",
    "軟體生命週期文件要求",
    "設計驗證與確效",
]

LLM_QUERY = "醫療器材軟體開發需要建立哪些文件與計畫？"


def _ollama_host() -> str:
    host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
    if "://" not in host:
        host = "http://" + host
    return host.rstrip("/")


def ollama_available() -> bool:
    """模仿 prompt 規格：``ollama.list()`` 不報錯即視為可用。"""
    try:
        import ollama  # type: ignore

        ollama.list()
        return True
    except Exception:
        pass
    try:  # 退回 HTTP 探測（與 repo 的 ollama_client.py 一致）
        req = urllib.request.Request(_ollama_host() + "/api/tags")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def _ollama_chat(model: str, system: str, user: str) -> str:
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


def main() -> int:
    print("=" * 62)
    print("  RAG + MCP 範例 Demo — 醫療器材法規知識庫")
    print("=" * 62)

    db_path = default_db_path()
    rag = RAGBackend(db_path, DEFAULT_COLLECTION)
    print(
        "[INFO] RAG 後端初始化完成"
        f"（backend={rag.backend_name}, 向量搜尋="
        f"{'啟用' if rag.has_embeddings else '停用'}）"
    )
    print(f"[INFO] 資料庫路徑：{db_path}")
    print(f"[INFO] 開始索引 {len(DOCUMENTS)} 筆醫療器材法規文件…")

    for source, content in DOCUMENTS:
        doc_id = rag.add_document(content, source, {"tags": "醫療器材,法規"})
        print(f"[ADD]  {source:<14} → id: {doc_id[:8]}")

    for query in QUERIES:
        print()
        print(f"[SEARCH] {query}")
        hits = rag.search(query, n_results=3)
        if not hits:
            print("  （無結果）")
            continue
        for i, hit in enumerate(hits, 1):
            snippet = hit["content"].replace("\n", " ")[:30]
            print(f"  {i}. ({hit['score']:.3f}) {hit['source']}: {snippet}…")

    print()
    if ollama_available():
        print(f"[LLM]  {LLM_QUERY}")
        context = rag.query_with_context(LLM_QUERY, top_k=3)
        system = "你是醫療器材法規助理，只依據提供的參考資料回答，並標註依據條款。"
        try:
            answer = _ollama_chat(
                "gemma4:latest", system, f"參考資料:\n{context}\n\n問題: {LLM_QUERY}"
            )
        except Exception as exc:  # 模型不存在等
            answer = f"（Ollama 呼叫失敗：{exc}）\n以下為檢索內容：\n{context}"
        for line in answer.splitlines():
            print(f"       {line}")
    else:
        print("[LLM]  Ollama 未連線，略過 query_with_llm（需安裝並啟動 Ollama）")
        print("       提示：context 仍可由 rag.query_with_context() 取得供任意 LLM 使用。")

    stats = rag.get_stats()
    print()
    print(
        f"[STATS] 總文件: {stats['total_docs']} | 模型: {stats['model']} "
        f"| 集合: {stats['collection']}"
    )
    print(
        f"[STATS] 後端: {stats['backend']} | "
        f"向量搜尋: {'啟用' if stats['embeddings'] else '停用（關鍵字後備）'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
