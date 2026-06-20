#!/usr/bin/env python3
"""RAG + MCP 範例：環境自我檢查 / 自動安裝 / 產生設定。

用法：
    python check_setup.py            # 診斷並列出缺少的套件（不安裝）
    python check_setup.py --install  # 自動 pip 安裝缺少的套件後再診斷
    python check_setup.py --config   # 只印出「套用本機路徑」的 mcp_config.json

這支腳本本身只用標準函式庫，任何 Python 3.10+ 都能直接執行。它會：
* 檢查 Python 版本與每個相依套件（標示必需 / 可選）；
* `--install` 時自動安裝缺少的套件；
* 對 RAGBackend 做一次 add/search 煙霧測試；
* 產生符合「目前 Python 路徑」的 MCP 設定，避免手動填錯路徑導致 MCP 離線。
"""

from __future__ import annotations

import importlib.util
import json
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# (import 名稱, pip 名稱, 是否為 server 必需, 說明)
PACKAGES: list[tuple[str, str, bool, str]] = [
    ("mcp", "mcp", True, "官方 MCP SDK（server 主要後端）"),
    ("fastmcp", "fastmcp", False, "MCP 備援後端（mcp 不可用時）"),
    ("chromadb", "chromadb", False, "持久化向量資料庫（缺少時改用記憶體）"),
    ("sentence_transformers", "sentence-transformers", False, "向量嵌入（缺少時改用關鍵字搜尋）"),
    ("ollama", "ollama", False, "query_with_llm 的 LLM 生成（可選）"),
]

checks: list[tuple[str, bool]] = []


def check(item: str, ok: bool, detail: str = "", fix: str = "") -> bool:
    checks.append((item, ok))
    print(f"[{'OK' if ok else 'X '}] {item}" + (f" — {detail}" if detail else ""))
    if not ok and fix:
        print(f"      → {fix}")
    return ok


def have(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def suggested_config() -> dict:
    """產生套用「本機」實際路徑的 mcp_config.json 內容。"""
    return {
        "mcpServers": {
            "rag-knowledge-base": {
                "command": sys.executable,
                "args": [str(HERE / "rag_mcp_server.py")],
                "env": {"PYTHONPATH": str(ROOT)},
            }
        }
    }


def pip_install(packages: list[str]) -> bool:
    print(f"\n>>> pip install {' '.join(packages)}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install",
             "--disable-pip-version-check", *packages]
        )
        return True
    except Exception as exc:
        print(f"安裝失敗：{exc}")
        return False


def main() -> int:
    args = sys.argv[1:]

    if "--config" in args:
        print(json.dumps(suggested_config(), ensure_ascii=False, indent=2))
        return 0

    print("=== RAG + MCP 範例環境檢查 ===\n")
    print(f"Python : {sys.version.split()[0]}  ({sys.executable})")
    print(f"平台   : {platform.system()} {platform.release()}\n")

    check(
        "Python >= 3.10",
        sys.version_info >= (3, 10),
        f"目前 {sys.version_info.major}.{sys.version_info.minor}",
        fix="請改用 Python 3.10 以上版本",
    )

    if "--install" in args:
        missing = [pip for mod, pip, *_ in PACKAGES if not have(mod)]
        if missing:
            pip_install(missing)
        else:
            print(">>> 所有套件皆已安裝，無需安裝")
        print()

    for module, pip_name, required, desc in PACKAGES:
        tag = "必需" if required else "可選"
        check(
            f"[{tag}] {pip_name}",
            have(module),
            desc,
            fix=f"pip install {pip_name}（或執行 check_setup.py --install）",
        )

    server_ready = have("mcp") or have("fastmcp")
    check(
        "MCP server 可啟動（mcp 或 fastmcp 至少一個）",
        server_ready,
        fix="pip install mcp fastmcp",
    )

    # RAGBackend 索引 / 搜尋煙霧測試
    sys.path.insert(0, str(HERE))
    try:
        from rag_backend import DEFAULT_COLLECTION, RAGBackend, default_db_path

        rag = RAGBackend(default_db_path(), DEFAULT_COLLECTION)
        doc_id = rag.add_document("風險分析測試文件", "smoke_test")
        hits = rag.search("風險", n_results=1)
        ok = bool(hits) and hits[0]["id"] == doc_id
        check(
            "RAGBackend 索引 / 搜尋煙霧測試",
            ok,
            f"backend={rag.backend_name}, 向量={rag.has_embeddings}",
        )
    except Exception as exc:
        check("RAGBackend 索引 / 搜尋煙霧測試", False, str(exc)[:80])

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n結果：{passed}/{len(checks)} 項通過")

    print("\n--- 建議的 mcp_config.json（已套用本機路徑）---")
    print(json.dumps(suggested_config(), ensure_ascii=False, indent=2))
    print("\n將以上內容合併到 Claude Desktop 的 claude_desktop_config.json 後重啟即可。")

    if not server_ready:
        print(
            "\n⚠ 目前缺少 mcp/fastmcp，MCP server 會顯示離線。"
            "請執行：python check_setup.py --install"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
