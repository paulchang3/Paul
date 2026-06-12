"""從 .pdf 檔抽取文字。

這是整個專案唯一需要外部套件的功能(只在你要用 PDF 時):
    pip install pypdf

限制:只能抽取「文字型」PDF;掃描影像檔(整頁是圖片)抽不出文字,
需要先用 OCR 工具轉換。可直接執行本檔預覽抽取結果來確認:
    python extract_pdf.py my_docs/某文件.pdf
"""

import sys


def extract_lines(pdf_path: str) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit("讀取 PDF 需要 pypdf,請先執行:pip install pypdf")

    reader = PdfReader(pdf_path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise SystemExit(f"{pdf_path} 已加密,無法讀取")

    lines: list[str] = []
    for page in reader.pages:
        for line in (page.extract_text() or "").splitlines():
            line = line.strip()
            if line:
                lines.append(line)
    return lines


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(0)
    for path in sys.argv[1:]:
        print(f"===== {path} =====")
        for line in extract_lines(path):
            print(line)
