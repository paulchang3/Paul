#!/usr/bin/env python3
"""RAG 後端引擎：封裝 ChromaDB + sentence-transformers。

設計目標
--------
* 預設使用 ChromaDB（持久化向量資料庫）+ sentence-transformers
  （``all-MiniLM-L6-v2``, 384 維）做語意檢索。
* 若 ``chromadb`` 未安裝，自動 fallback 到記憶體 dict 儲存，仍可執行；
  此時若 ``sentence-transformers`` 可用則以餘弦相似度搜尋，否則退化為
  對中文友善的字元 bigram 關鍵字比對（完全不需第三方套件）。

所有公開方法都附型別註記與 docstring。匯入第三方套件失敗時只印出
警告（送往 stderr）而非直接崩潰，方便在尚未安裝完整環境的機器上先體驗。
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"
DEFAULT_COLLECTION = "rag_mcp_knowledge"


# --- 選用相依套件（缺少時僅警告，不崩潰）----------------------------------
try:
    import chromadb

    _HAS_CHROMA = True
except Exception as exc:  # pragma: no cover - 視環境而定
    chromadb = None
    _HAS_CHROMA = False
    print(f"[rag_backend] chromadb 未安裝，改用記憶體儲存：{exc}", file=sys.stderr)

try:
    from sentence_transformers import SentenceTransformer

    _HAS_ST = True
except Exception as exc:  # pragma: no cover - 視環境而定
    SentenceTransformer = None
    _HAS_ST = False
    print(
        f"[rag_backend] sentence-transformers 未安裝，改用關鍵字後備搜尋：{exc}",
        file=sys.stderr,
    )


def project_root() -> Path:
    """回傳專案根目錄（即 ``examples/rag_mcp/`` 的上兩層）。"""
    return Path(__file__).resolve().parents[2]


def default_db_path() -> str:
    """預設 ChromaDB 路徑：``{ROOT}/database/chroma/rag_example``。

    可用環境變數 ``RAG_DB_PATH`` 覆寫，方便在不同機器共用同一份程式碼。
    """
    env = os.environ.get("RAG_DB_PATH")
    if env:
        return env
    return str(project_root() / "database" / "chroma" / "rag_example")


# --- 關鍵字後備搜尋（無向量模型時使用）------------------------------------
_WORD_RE = re.compile(r"[^\w一-鿿]+", re.UNICODE)


def _normalize(text: str) -> str:
    return _WORD_RE.sub("", text.lower())


def _bigrams(text: str) -> set[str]:
    """字元 bigram；中文無空白分詞，bigram 比單字更適合做關鍵字比對。"""
    text = _normalize(text)
    if len(text) < 2:
        return {text} if text else set()
    return {text[i : i + 2] for i in range(len(text) - 1)}


def _keyword_score(query: str, content: str) -> float:
    """以查詢為基準的 bigram 重疊係數，範圍約 0~1（越高越相關）。"""
    q = _bigrams(query)
    if not q:
        return 0.0
    c = _bigrams(content)
    return len(q & c) / len(q)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class RAGBackend:
    """檢索增強生成（RAG）後端：新增 / 搜尋 / 管理知識庫文件。"""

    def __init__(
        self,
        db_path: str,
        collection_name: str = DEFAULT_COLLECTION,
        embed_model: str = DEFAULT_EMBED_MODEL,
    ) -> None:
        self.db_path = db_path
        self.collection_name = collection_name
        self.embed_model = embed_model

        # 1) 載入向量模型（若 sentence-transformers 可用）
        self.model = None
        if _HAS_ST:
            try:
                self.model = SentenceTransformer(embed_model)
            except Exception as exc:  # 下載失敗 / 離線
                print(
                    f"[rag_backend] 載入模型 {embed_model} 失敗，改用關鍵字搜尋：{exc}",
                    file=sys.stderr,
                )
                self.model = None
        self.has_embeddings = self.model is not None

        # 2) 建立儲存後端。
        #    僅在「有本地向量模型」時才啟用 ChromaDB——這樣我們永遠以明確的
        #    embeddings 寫入 / 查詢，不必依賴 ChromaDB 內建（需連網下載）的向量
        #    函式。缺模型時退回記憶體 dict + 關鍵字搜尋，確保離線也不會崩潰。
        self._collection = None
        self._store: dict[str, dict[str, Any]] = {}
        if _HAS_CHROMA and self.has_embeddings:
            try:
                Path(db_path).mkdir(parents=True, exist_ok=True)
                client = chromadb.PersistentClient(path=db_path)
                self._collection = client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as exc:
                print(
                    f"[rag_backend] 初始化 ChromaDB 失敗，改用記憶體儲存：{exc}",
                    file=sys.stderr,
                )
                self._collection = None
        elif _HAS_CHROMA and not self.has_embeddings:
            print(
                "[rag_backend] 已安裝 chromadb 但無可用向量模型，"
                "改用記憶體 + 關鍵字搜尋",
                file=sys.stderr,
            )
        self.backend_name = "chromadb" if self._collection is not None else "memory"

    # --- 內部工具 ----------------------------------------------------------
    def _encode(self, text: str) -> list[float] | None:
        if self.model is None:
            return None
        return self.model.encode(text, show_progress_bar=False).tolist()

    @staticmethod
    def _sanitize_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
        """ChromaDB metadata 僅接受 str/int/float/bool，其餘轉成 JSON 字串。"""
        out: dict[str, Any] = {}
        for key, value in (meta or {}).items():
            if isinstance(value, (str, int, float, bool)):
                out[key] = value
            elif value is None:
                out[key] = ""
            else:
                out[key] = json.dumps(value, ensure_ascii=False)
        return out

    # --- 公開 API ----------------------------------------------------------
    def add_document(
        self,
        content: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """新增一筆文件，回傳自動產生的 ``doc_id``（UUID hex）。

        會用 SentenceTransformer 將 ``content`` 編碼為向量後存入 ChromaDB；
        在記憶體後備模式下則保存內容與（若有的）向量。
        """
        doc_id = uuid.uuid4().hex
        meta = self._sanitize_meta(metadata)
        meta["source"] = source
        meta.setdefault("added_at", datetime.now(timezone.utc).isoformat())
        embedding = self._encode(content)

        if self._collection is not None:
            # 啟用 ChromaDB 時必有本地向量模型，故一律以明確 embeddings 寫入
            self._collection.add(
                ids=[doc_id],
                documents=[content],
                embeddings=[embedding],
                metadatas=[meta],
            )
        else:
            self._store[doc_id] = {
                "content": content,
                "metadata": meta,
                "embedding": embedding,
            }
        return doc_id

    def search(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        """語意搜尋，回傳 ``[{id, content, source, score, metadata}]``。

        ``score`` 越高越相關：向量模式為餘弦相似度，關鍵字後備則為 bigram
        重疊係數。
        """
        if self._collection is not None:
            return self._search_chroma(query, n_results)
        return self._search_memory(query, n_results)

    def _search_chroma(self, query: str, n_results: int) -> list[dict[str, Any]]:
        try:
            count = self._collection.count()
        except Exception:
            count = n_results
        if count == 0:
            return []
        n = max(1, min(n_results, count))
        # 啟用 ChromaDB 時必有本地向量模型，直接以查詢向量檢索
        res = self._collection.query(query_embeddings=[self._encode(query)], n_results=n)

        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        out: list[dict[str, Any]] = []
        for i, doc_id in enumerate(ids):
            meta = metas[i] or {}
            distance = float(dists[i]) if i < len(dists) else 0.0
            out.append(
                {
                    "id": doc_id,
                    "content": docs[i],
                    "source": meta.get("source", ""),
                    "score": round(max(0.0, 1.0 - distance), 4),
                    "metadata": meta,
                }
            )
        return out

    def _search_memory(self, query: str, n_results: int) -> list[dict[str, Any]]:
        q_emb = self._encode(query)
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for doc_id, rec in self._store.items():
            if q_emb is not None and rec.get("embedding") is not None:
                score = _cosine(q_emb, rec["embedding"])
            else:
                score = _keyword_score(query, rec["content"])
            scored.append((score, doc_id, rec))
        scored.sort(key=lambda item: item[0], reverse=True)
        out: list[dict[str, Any]] = []
        for score, doc_id, rec in scored[:n_results]:
            meta = rec["metadata"]
            out.append(
                {
                    "id": doc_id,
                    "content": rec["content"],
                    "source": meta.get("source", ""),
                    "score": round(float(score), 4),
                    "metadata": meta,
                }
            )
        return out

    def list_documents(self, limit: int = 20) -> list[dict[str, Any]]:
        """列出知識庫文件（依加入時間排序，最新在前）。"""
        records: list[dict[str, Any]] = []
        if self._collection is not None:
            got = self._collection.get(include=["documents", "metadatas"])
            ids = got.get("ids") or []
            docs = got.get("documents") or []
            metas = got.get("metadatas") or []
            for i, doc_id in enumerate(ids):
                meta = metas[i] or {}
                records.append(
                    {
                        "id": doc_id,
                        "content": docs[i],
                        "source": meta.get("source", ""),
                        "metadata": meta,
                    }
                )
        else:
            for doc_id, rec in self._store.items():
                meta = rec["metadata"]
                records.append(
                    {
                        "id": doc_id,
                        "content": rec["content"],
                        "source": meta.get("source", ""),
                        "metadata": meta,
                    }
                )
        records.sort(key=lambda r: r["metadata"].get("added_at", ""), reverse=True)
        return records[:limit]

    def delete_document(self, doc_id: str) -> bool:
        """刪除指定 ``doc_id``，成功回傳 True、不存在回傳 False。"""
        if self._collection is not None:
            try:
                existing = self._collection.get(ids=[doc_id]).get("ids") or []
                if not existing:
                    return False
                self._collection.delete(ids=[doc_id])
                return True
            except Exception as exc:
                print(f"[rag_backend] 刪除失敗：{exc}", file=sys.stderr)
                return False
        if doc_id in self._store:
            del self._store[doc_id]
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """回傳知識庫統計：總數 / 集合 / 模型 / 路徑 / 後端 / 是否啟用向量。"""
        if self._collection is not None:
            try:
                total = self._collection.count()
            except Exception:
                total = 0
        else:
            total = len(self._store)
        return {
            "total_docs": total,
            "collection": self.collection_name,
            "model": self.embed_model,
            "db_path": self.db_path,
            "backend": self.backend_name,
            "embeddings": self.has_embeddings,
        }

    def query_with_context(self, query: str, top_k: int = 3) -> str:
        """取 top_k 文件組合成 context 字串，供 LLM 使用。"""
        hits = self.search(query, n_results=top_k)
        if not hits:
            return "（知識庫中找不到相關文件）"
        blocks = []
        for i, hit in enumerate(hits, 1):
            blocks.append(
                f"[參考 {i} | 來源: {hit['source']} | 相關度: {hit['score']:.3f}]\n"
                f"{hit['content']}"
            )
        return "\n\n".join(blocks)


if __name__ == "__main__":
    # 簡易自我檢查：python rag_backend.py
    rag = RAGBackend(default_db_path())
    print(json.dumps(rag.get_stats(), ensure_ascii=False, indent=2))
