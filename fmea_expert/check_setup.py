"""環境檢查腳本:逐項檢查 FMEA 專家所需環境,產生報告供遠端 Claude 查看。

    python check_setup.py          # 檢查並產生 setup_report.json
    python check_setup.py --push   # 檢查 + 自動 commit/push 報告到 GitHub
    python check_setup.py --full   # 額外做一次真實問答測試(較慢)

報告只記錄狀態與數量,不會包含你的文件內容或檔名。
"""

import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from . import ollama_api
except ImportError:
    import ollama_api

HERE = Path(__file__).resolve().parent
REPORT_FILE = HERE / "setup_report.json"
BASE_MODEL = os.environ.get("FMEA_BASE_MODEL", "qwen2.5:3b")
EMBED_MODEL = os.environ.get("FMEA_EMBED_MODEL", "bge-m3")
EXPERT_MODEL = os.environ.get("FMEA_CHAT_MODEL", "fmea-expert")

# Windows 舊主控台(cp950)印不出特殊符號時以 ? 取代,避免直接當機
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

checks: list[dict] = []


def check(item: str, ok: bool, detail: str = "", fix: str = "") -> bool:
    checks.append({"item": item, "ok": bool(ok), "detail": detail, "fix": fix})
    print(f"[{'OK' if ok else 'X '}] {item}" + (f" -- {detail}" if detail else ""))
    if not ok and fix:
        print(f"      下一步: {fix}")
    return bool(ok)


def has_model(installed: list[str], target: str) -> bool:
    base = target.split(":")[0]
    return any(name == target or name.split(":")[0] == base for name in installed)


def main() -> None:
    print("=== FMEA 專家環境檢查 ===\n")

    check("Ollama 已安裝", shutil.which("ollama") is not None,
          fix="到 https://ollama.com 下載安裝")

    server_ok = False
    installed: list[str] = []
    try:
        import urllib.request
        with urllib.request.urlopen(ollama_api.base_url() + "/api/version", timeout=5) as r:
            version = json.load(r)["version"]
        server_ok = True
        with urllib.request.urlopen(ollama_api.base_url() + "/api/tags", timeout=5) as r:
            installed = [m["model"] for m in json.load(r)["models"]]
    except Exception as exc:
        version = str(exc)
    check("Ollama 伺服器運行中", server_ok,
          f"版本 {version}" if server_ok else str(version),
          fix="桌面版啟動 Ollama 程式,或終端機執行 ollama serve")

    if server_ok:
        check(f"基底模型 {BASE_MODEL}", has_model(installed, BASE_MODEL),
              f"已安裝: {', '.join(installed) or '(無)'}",
              fix=f"ollama pull {BASE_MODEL}")
        check(f"嵌入模型 {EMBED_MODEL}", has_model(installed, EMBED_MODEL),
              fix=f"ollama pull {EMBED_MODEL}")
        check(f"專家模型 {EXPERT_MODEL}(ollama create 的成果)",
              has_model(installed, EXPERT_MODEL),
              fix="在本資料夾執行: ollama create fmea-expert -f Modelfile")

    try:
        import pypdf  # noqa: F401
        check("pypdf(讀 PDF 用)", True)
    except ImportError:
        check("pypdf(讀 PDF 用)", False, fix="pip install pypdf(不用 PDF 可忽略)")

    docs_dir = HERE / "my_docs"
    n_docx = len(list(docs_dir.glob("*.docx"))) if docs_dir.exists() else 0
    n_pdf = len(list(docs_dir.glob("*.pdf"))) if docs_dir.exists() else 0
    check("my_docs/ 內有文件", (n_docx + n_pdf) > 0,
          f"{n_docx} 個 docx、{n_pdf} 個 pdf",
          fix="放入你的 .docx/.pdf,或先執行 python make_sample_docx.py")

    kn_file = HERE / "knowledge.json"
    if kn_file.exists():
        kn = json.loads(kn_file.read_text(encoding="utf-8"))
        check("知識庫 knowledge.json", True,
              f"{len(kn['chunks'])} 個段落塊,嵌入模型 {kn['embed_model']}")
    else:
        check("知識庫 knowledge.json", False, fix="python build_knowledge.py")

    if "--full" in sys.argv and server_ok:
        try:
            answer = ollama_api.chat(
                [{"role": "user", "content": "S=8 O=4 D=3,RPN 是多少?只回數字。"}],
                EXPERT_MODEL,
            )
            check("真實問答測試", "96" in answer, f"模型回答: {answer[:60]}")
        except Exception as exc:
            check("真實問答測試", False, str(exc)[:80])

    passed = sum(1 for c in checks if c["ok"])
    print(f"\n結果: {passed}/{len(checks)} 項通過")

    REPORT_FILE.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platform": platform.system() + " " + platform.release(),
        "summary": f"{passed}/{len(checks)}",
        "checks": checks,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"報告已寫入 {REPORT_FILE.name}")

    if "--push" in sys.argv:
        repo_root = HERE.parent
        if not (repo_root / ".git").exists():
            print("這裡不是 git 倉庫(可能是解壓 zip 而來),"
                  "請改用 git clone 取得專案後再用 --push")
            return
        run = lambda *args: subprocess.run(args, cwd=repo_root,
                                           capture_output=True, text=True)
        run("git", "add", "fmea_expert/setup_report.json")
        commit = run("git", "commit", "-m",
                     f"chore: 環境檢查報告 {passed}/{len(checks)} 通過")
        if "nothing to commit" in commit.stdout + commit.stderr:
            print("報告內容沒有變化,不需推送")
            return
        push = run("git", "push")
        if push.returncode == 0:
            print("報告已推上 GitHub,可以請 Claude 遠端檢查了")
        else:
            print("推送失敗:", (push.stderr or push.stdout).strip()[:200])


if __name__ == "__main__":
    main()
