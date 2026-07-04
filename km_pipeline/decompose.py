"""把 extract.py 產生的區塊清單,用規則(啟發式)拆解成:

  - WBS 樹狀結構(wbs)      -- 依標題層級 + 條列項目組成的知識樹
  - 行動樹(actions)        -- 待辦/任務類的句子,含負責人/期限/優先級/狀態
  - 康乃爾筆記(cornell)    -- 每個大章節一列:提示/筆記/摘要/標籤
  - SMART 筆記(smart)      -- 從行動項目或目標句子挑出可量化的目標
  - CODE 筆記(code)        -- 每個大章節一列:Capture/Organize/Distill/Express

全部都是規則式的猜測,不是真正理解語意;品質有限但不需要任何外部服務。
想要更好的摘要/分類,可以加 --llm 讓 llm_enhance.py 用本機 Ollama 補強。
"""

from __future__ import annotations

import re
from collections import Counter

MAX_WBS_LEVELS = 4

STOPWORDS = {
    "的", "了", "與", "及", "和", "或", "在", "是", "為", "於", "而", "也", "就",
    "都", "並", "以", "其", "此", "這", "那", "the", "and", "or", "of", "to",
    "a", "an", "is", "are", "for", "in", "on", "with", "by",
}

_SENT_SPLIT_RE = re.compile(r"(?<=[。！？!?.])\s*")
_ACTION_CUE_RE = re.compile(
    r"待辦|行動項目|TODO|To-?do|Action\s*Item|需(?:要|辦理)|應於|應辦|截止|deadline|due",
    re.I,
)
_BULLET_RE = re.compile(r"^[\-•‣▪◦□☐]\s*(\[[ xX]?\]\s*)?")
_OWNER_RE = re.compile(r"(?:負責人|承辦人|owner|assignee)[:：]?\s*([^\s,，。;；]{1,20})", re.I)
_DEADLINE_RE = re.compile(
    r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?|\d{1,2}[-/]\d{1,2}|"
    r"(?:本週|下週|本月|月底|季末|年底)(?:前|截止)?)"
)
_PRIORITY_WORDS = [("high", ("緊急", "高優先", "優先級高", "urgent", "high priority")),
                    ("low", ("低", "不急", "low priority"))]
_STATUS_WORDS = [
    ("done", ("已完成", "done", "closed", "已結案")),
    ("in_progress", ("進行中", "in progress", "doing")),
    ("delayed", ("延期", "delayed", "blocked")),
]
_METRIC_RE = re.compile(r"\d+\s*(%|percent|分鐘|小時|天|次|件|元|人)|[≤≥<>]=?\s*\d+|kpi", re.I)
_MEETING_WORDS = ("會議", "出席", "決議", "會議記錄", "與會")
_SOP_WORDS = ("步驟", "流程", "作業程序", "sop")
_AREA_WORDS = ("維護", "例行", "職責", "稽核", "responsibility")
_RESOURCE_WORDS = ("定義", "參考", "名詞", "規範", "標準", "reference")
_ARCHIVE_WORDS = ("已結案", "歷史", "封存", "舊版", "archive")
_STRONG_WORDS = ("關鍵", "重要", "結論", "核心", "必須", "key", "important", "conclusion")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]


def extract_tags(text: str, k: int = 5) -> str:
    words = re.findall(r"[A-Za-z]{3,}|[一-鿿]{2,4}", text)
    words = [w for w in words if w.lower() not in STOPWORDS]
    common = [w for w, _ in Counter(words).most_common(k)]
    return " ".join(common)


def _priority_of(text: str) -> str:
    low = text.lower()
    for label, words in _PRIORITY_WORDS:
        if any(w in low or w in text for w in words):
            return label
    return "medium"


def _status_of(text: str) -> str:
    low = text.lower()
    for label, words in _STATUS_WORDS:
        if any(w in low or w in text for w in words):
            return label
    return "todo"


def _looks_like_action(text: str) -> bool:
    return bool(_BULLET_RE.match(text) or _ACTION_CUE_RE.search(text))


def _make_action(text: str, source: str) -> dict:
    owner_m = _OWNER_RE.search(text)
    deadline_m = _DEADLINE_RE.search(text)
    task = _BULLET_RE.sub("", text).strip()
    return {
        "task": task,
        "owner": owner_m.group(1) if owner_m else "",
        "deadline": deadline_m.group(1) if deadline_m else "",
        "priority": _priority_of(text),
        "status": _status_of(text),
        "source_excerpt": text[:120],
        "source": source,
    }


def _guess_para(section_text: str, has_action: bool) -> str:
    if any(w in section_text for w in _AREA_WORDS):
        return "Areas 責任範疇"
    if has_action:
        return "Projects 專案"
    if any(w in section_text for w in _RESOURCE_WORDS):
        return "Resources 資源庫"
    if any(w in section_text for w in _ARCHIVE_WORDS):
        return "Archives 封存"
    return "Resources 資源庫"


def _guess_express_type(section_text: str, has_action: bool) -> str:
    if any(w in section_text for w in _MEETING_WORDS):
        return "會議摘要"
    if any(w in section_text for w in _SOP_WORDS):
        return "SOP 標準作業"
    if has_action:
        return "決策備忘"
    return "提案報告"


def _distill(sentences: list[str]) -> str:
    strong = [s for s in sentences if any(w in s for w in _STRONG_WORDS)]
    if strong:
        return max(strong, key=len)[:300]
    return sentences[0][:300] if sentences else ""


class _Section:
    """一個 Level-1(或找到的最上層)標題底下累積的內容,拆解各筆記法時的中介資料。"""

    def __init__(self, title: str):
        self.title = title
        self.lines: list[str] = []

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def decompose(blocks: list[dict], source: str) -> dict:
    wbs: list[dict] = []
    actions: list[dict] = []
    sections: list[_Section] = []

    path = [""] * MAX_WBS_LEVELS
    current_row: dict | None = None

    def flush_heading(level: int, text: str):
        nonlocal current_row
        idx = min(level, MAX_WBS_LEVELS) - 1
        path[idx] = text
        for i in range(idx + 1, MAX_WBS_LEVELS):
            path[i] = ""
        current_row = {
            "level1": path[0], "level2": path[1], "level3": path[2], "level4": path[3],
            "path": " > ".join(p for p in path if p),
            "content": "", "source": source,
        }
        wbs.append(current_row)
        if idx == 0:
            sections.append(_Section(text))

    def append_content(text: str):
        nonlocal current_row
        if current_row is None:
            flush_heading(1, source)
        current_row["content"] = (current_row["content"] + "\n" + text).strip()
        if sections:
            sections[-1].lines.append(text)

    for block in blocks:
        kind = block["kind"]
        if kind == "heading":
            flush_heading(block["level"], block["text"])
        elif kind == "list_item":
            base_level = sum(1 for p in path if p) or 1
            leaf_level = min(MAX_WBS_LEVELS, base_level + block["level"])
            leaf_path = path[: leaf_level - 1] + [block["text"]]
            leaf_path = (leaf_path + [""] * MAX_WBS_LEVELS)[:MAX_WBS_LEVELS]
            wbs.append({
                "level1": leaf_path[0], "level2": leaf_path[1],
                "level3": leaf_path[2], "level4": leaf_path[3],
                "path": " > ".join(p for p in leaf_path if p),
                "content": "", "source": source,
            })
            append_content(block["text"])
            if _looks_like_action(block["text"]):
                actions.append(_make_action(block["text"], source))
        elif kind in ("para", "table_row"):
            append_content(block["text"])
            if _looks_like_action(block["text"]):
                actions.append(_make_action(block["text"], source))
        elif kind == "structured_row":
            rec = block["record"]
            task = str(rec.get("task", "")).strip()
            if not task:
                continue
            actions.append({
                "task": task,
                "owner": str(rec.get("owner", "")).strip(),
                "deadline": str(rec.get("deadline", "")).strip(),
                "priority": str(rec.get("priority", "")).strip() or "medium",
                "status": str(rec.get("status", "")).strip() or "todo",
                "source_excerpt": str(rec.get("notes", ""))[:120],
                "source": source,
            })
            append_content(task)

    if not wbs:
        wbs.append({"level1": source, "level2": "", "level3": "", "level4": "",
                     "path": source, "content": "(未偵測到任何內容)", "source": source})

    cornell: list[dict] = []
    smart: list[dict] = []
    code: list[dict] = []

    for section in sections or [_Section(source)]:
        text = section.text
        sentences = split_sentences(text)
        explicit_cues = [s for s in sentences if "?" in s or "？" in s]
        cues = explicit_cues or [f"{section.title} 的重點是什麼?"]
        summary = " ".join(sentences[:1] + sentences[-1:]) if sentences else ""
        tags = extract_tags(text)
        section_actions = [a for a in actions if a["source"] == source and a["task"] in text]
        has_action = bool(section_actions)

        cornell.append({
            "section": section.title,
            "cues": "\n".join(cues),
            "notes": text[:2000],
            "summary": summary[:400],
            "tags": tags,
            "review_date": "",
            "source": source,
        })

        code.append({
            "capture": text[:300],
            "para": _guess_para(text, has_action),
            "tags": tags,
            "distill": _distill(sentences),
            "express_type": _guess_express_type(text, has_action),
            "express": summary[:300],
            "source": source,
        })

        for a in section_actions:
            metric_m = _METRIC_RE.search(a["task"])
            if metric_m or "目標" in text or "kpi" in text.lower():
                smart.append({
                    "specific": a["task"],
                    "measurable": metric_m.group(0) if metric_m else "",
                    "achievable": "",
                    "relevant": "",
                    "deadline": a["deadline"],
                    "priority": a["priority"],
                    "status": a["status"],
                    "source": source,
                })

    return {"wbs": wbs, "actions": actions, "cornell": cornell, "smart": smart, "code": code}
