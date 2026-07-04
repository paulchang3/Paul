"""從 .docx / .pdf / .html / .xlsx 抽取內容,統一轉成一份「區塊清單」(blocks)。

每個區塊是一個 dict:
    {"kind": "heading" | "para" | "list_item" | "table_row" | "structured_row",
     "level": int,        # heading/list 的層級(1 起算);para/table_row 固定 0
     "text": str,         # 這個區塊的文字(structured_row 沒有此欄)
     "record": dict}      # 只有 structured_row 才有:欄位名稱 -> 內容

structured_row 是給「本來就是表格」的來源(主要是 Excel)用的:如果第一列
看起來像表頭(負責人/期限/狀態…),之後每一列就直接轉成結構化欄位,
之後 decompose.py 可以直接拿來當行動項目用,不用再用規則猜。

只有讀 PDF 需要外部套件(pypdf);.docx 用標準函式庫的 zipfile + xml
解析(.docx 本質是一個 zip),.xlsx 用 openpyxl(輸出 Excel 本來就需要它),
.html 用標準函式庫的 html.parser。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

TASK_ALIASES = {"task", "項目", "任務", "事項", "行動", "title", "name", "主題", "標題", "工作"}
OWNER_ALIASES = {"owner", "負責人", "承辦人", "assignee", "responsible"}
DEADLINE_ALIASES = {"deadline", "due", "due date", "期限", "截止日", "完成日", "截止"}
PRIORITY_ALIASES = {"priority", "優先級", "優先順序", "優先"}
STATUS_ALIASES = {"status", "狀態", "進度"}


def extract(path: str | Path) -> list[dict]:
    """依副檔名分派到對應的抽取函式,回傳統一格式的區塊清單。"""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx(path)
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix in (".html", ".htm"):
        return extract_html(path)
    if suffix in (".xlsx", ".xlsm"):
        return extract_xlsx(path)
    raise ValueError(f"不支援的檔案類型:{suffix}(支援 .docx/.pdf/.html/.xlsx)")


# ── .docx ─────────────────────────────────────────────────────────
def _heading_level(style: str | None) -> int | None:
    if not style:
        return None
    m = re.match(r"^Heading ?([1-6])$", style, re.I)
    if m:
        return int(m.group(1))
    if style.lower() == "title":
        return 1
    return None


def _paragraph_text(p) -> str:
    return "".join(t.text or "" for t in p.iter(W + "t")).strip()


def extract_docx(path: str | Path) -> list[dict]:
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))

    blocks: list[dict] = []
    body = root.find(W + "body")
    for element in body:
        if element.tag == W + "p":
            text = _paragraph_text(element)
            if not text:
                continue
            style_el = element.find(f"{W}pPr/{W}pStyle")
            style = style_el.get(W + "val") if style_el is not None else None
            level = _heading_level(style)
            if level:
                blocks.append({"kind": "heading", "level": level, "text": text})
                continue
            num_el = element.find(f"{W}pPr/{W}numPr/{W}ilvl")
            if num_el is not None:
                ilvl = int(num_el.get(W + "val") or 0)
                blocks.append({"kind": "list_item", "level": ilvl + 1, "text": text})
            else:
                blocks.append({"kind": "para", "level": 0, "text": text})
        elif element.tag == W + "tbl":
            for row in element.iter(W + "tr"):
                cells = []
                for cell in row.iter(W + "tc"):
                    cell_text = " ".join(
                        _paragraph_text(p) for p in cell.iter(W + "p")
                    ).strip()
                    cells.append(cell_text)
                if any(cells):
                    blocks.append({"kind": "table_row", "level": 0, "text": " | ".join(cells)})
    return blocks


# ── .pdf ──────────────────────────────────────────────────────────
# 啟發式判斷「看起來像標題」的行:短、沒有句尾標點、常見的編號/章節前綴。
_HEADING_PREFIX_RE = re.compile(
    r"^(第[一二三四五六七八九十百0-9]+[章節條]|[壹貳參肆伍陸柒捌玖拾]+、|"
    r"[一二三四五六七八九十]+、|\d+(\.\d+){0,3}[\.\s、]|Chapter\s+\d+)",
    re.I,
)


def _guess_pdf_level(line: str) -> int | None:
    if len(line) > 40:
        return None
    if line[-1:] in "。.!?,;:，；:":
        return None
    m = _HEADING_PREFIX_RE.match(line)
    if m:
        depth = m.group(0).count(".")
        return min(4, depth + 1) if "." in m.group(0) else 1
    if len(line) <= 20 and not re.search(r"[a-z]", line):
        # 全形/短行且沒有小寫字母,常見於中文標題
        return 2
    return None


def extract_pdf(path: str | Path) -> list[dict]:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit("讀取 PDF 需要 pypdf,請先執行:pip install pypdf")

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise SystemExit(f"{path} 已加密,無法讀取")

    blocks: list[dict] = []
    for page in reader.pages:
        for raw_line in (page.extract_text() or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            level = _guess_pdf_level(line)
            if level:
                blocks.append({"kind": "heading", "level": level, "text": line})
            else:
                blocks.append({"kind": "para", "level": 0, "text": line})
    return blocks


# ── .html ─────────────────────────────────────────────────────────
def extract_html(path: str | Path) -> list[dict]:
    from html.parser import HTMLParser

    html_text = Path(path).read_text(encoding="utf-8", errors="replace")

    class _Parser(HTMLParser):
        LEAF_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th"}
        SKIP_TAGS = {"script", "style"}

        def __init__(self):
            super().__init__()
            self.blocks: list[dict] = []
            self._list_depth = 0
            self._capture_tag: str | None = None
            self._buf: list[str] = []
            self._row_cells: list[str] | None = None
            self._skip_depth = 0

        def handle_starttag(self, tag, attrs):
            if tag in self.SKIP_TAGS:
                self._skip_depth += 1
            elif tag in ("ul", "ol"):
                self._list_depth += 1
            elif tag == "tr":
                self._row_cells = []
            elif tag in self.LEAF_TAGS:
                self._capture_tag = tag
                self._buf = []

        def handle_endtag(self, tag):
            if tag in self.SKIP_TAGS:
                self._skip_depth = max(0, self._skip_depth - 1)
            elif tag in ("ul", "ol"):
                self._list_depth = max(0, self._list_depth - 1)
            elif tag == "tr":
                if self._row_cells:
                    text = " | ".join(c for c in self._row_cells if c)
                    if text:
                        self.blocks.append({"kind": "table_row", "level": 0, "text": text})
                self._row_cells = None
            elif tag == self._capture_tag:
                text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
                if tag in ("td", "th"):
                    if self._row_cells is not None:
                        self._row_cells.append(text)
                elif text:
                    if tag[0] == "h" and tag[1:].isdigit():
                        self.blocks.append({"kind": "heading", "level": int(tag[1]), "text": text})
                    elif tag == "li":
                        self.blocks.append(
                            {"kind": "list_item", "level": max(1, self._list_depth), "text": text}
                        )
                    else:
                        self.blocks.append({"kind": "para", "level": 0, "text": text})
                self._capture_tag = None

        def handle_data(self, data):
            if self._skip_depth == 0 and self._capture_tag:
                self._buf.append(data)

    parser = _Parser()
    parser.feed(html_text)
    return parser.blocks


# ── .xlsx ─────────────────────────────────────────────────────────
def _classify_header(cells: list[str]) -> dict[str, int] | None:
    """如果表頭列看起來像任務清單(有負責人/期限/狀態等欄位),回傳欄位->索引的對應。"""
    lowered = [c.strip().lower() for c in cells]
    mapping: dict[str, int] = {}
    for i, cell in enumerate(lowered):
        if cell in TASK_ALIASES and "task" not in mapping:
            mapping["task"] = i
        elif cell in OWNER_ALIASES:
            mapping["owner"] = i
        elif cell in DEADLINE_ALIASES:
            mapping["deadline"] = i
        elif cell in PRIORITY_ALIASES:
            mapping["priority"] = i
        elif cell in STATUS_ALIASES:
            mapping["status"] = i
    # 至少要有任務欄 + 一個其他欄位,才當作結構化任務表
    if "task" in mapping and len(mapping) >= 2:
        return mapping
    return None


def extract_xlsx(path: str | Path) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    blocks: list[dict] = []
    for ws in wb.worksheets:
        rows = [
            [("" if c is None else str(c).strip()) for c in row]
            for row in ws.iter_rows(values_only=True)
        ]
        rows = [r for r in rows if any(r)]
        if not rows:
            continue
        blocks.append({"kind": "heading", "level": 1, "text": ws.title})

        header_map = _classify_header(rows[0]) if rows else None
        data_rows = rows[1:] if header_map else rows
        if header_map:
            for row in data_rows:
                if not any(row):
                    continue
                record = {}
                for field, idx in header_map.items():
                    record[field] = row[idx] if idx < len(row) else ""
                extra = [
                    v for i, v in enumerate(row)
                    if i not in header_map.values() and v
                ]
                if extra:
                    record["notes"] = " | ".join(extra)
                blocks.append({"kind": "structured_row", "level": 0, "record": record})
        else:
            for row in rows:
                text = " | ".join(v for v in row if v)
                if text:
                    blocks.append({"kind": "table_row", "level": 0, "text": text})
    return blocks
