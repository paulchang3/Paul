"""步驟二:把 my_docs/ 裡的文件(.docx 與 .pdf)建成向量知識庫(knowledge.json)。

    python build_knowledge.py

之後文件有增修,重新執行一次即可。PDF 需先安裝 pypdf(pip install pypdf)。
"""

import json
import os
from pathlib import Path

try:
    from . import extract_pdf, ollama_api
    from .extract_docx import chunk_lines, extract_lines
except ImportError:  # 直接以 python build_knowledge.py 執行時
    import extract_pdf
    import ollama_api
    from extract_docx import chunk_lines, extract_lines

HERE = Path(__file__).resolve().parent
DOCS_DIR = HERE / "my_docs"
KNOWLEDGE_FILE = HERE / "knowledge.json"
EMBED_MODEL = os.environ.get("FMEA_EMBED_MODEL", "bge-m3")
BATCH_SIZE = 16


def main() -> None:
    doc_files = sorted(DOCS_DIR.glob("*.docx")) + sorted(DOCS_DIR.glob("*.pdf"))
    if not doc_files:
        print(f"在 {DOCS_DIR} 找不到任何 .docx 或 .pdf。")
        print("請把你的文件放進去,或先執行:python make_sample_docx.py")
        raise SystemExit(1)

    chunks: list[dict] = []
    for path in doc_files:
        if path.suffix.lower() == ".pdf":
            lines = extract_pdf.extract_lines(str(path))
        else:
            lines = extract_lines(str(path))
        texts = chunk_lines(lines)
        print(f"  {path.name}:抽出 {len(texts)} 個段落塊")
        if not texts:
            print("    ⚠️ 沒抽到文字(掃描影像 PDF?),此檔將不會進入知識庫")
        chunks += [{"source": path.name, "text": t} for t in texts]

    print(f"以 {EMBED_MODEL} 計算 {len(chunks)} 個向量...")
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        vectors = ollama_api.embed([c["text"] for c in batch], EMBED_MODEL)
        for chunk, vector in zip(batch, vectors):
            chunk["embedding"] = vector

    KNOWLEDGE_FILE.write_text(
        json.dumps({"embed_model": EMBED_MODEL, "chunks": chunks}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"完成!知識庫已存到 {KNOWLEDGE_FILE.name}(共 {len(chunks)} 塊)")


if __name__ == "__main__":
    main()
