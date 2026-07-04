"""選用:呼叫本機 Ollama,強化 decompose.py 的規則式結果(摘要/標籤/分類更準)。

規則式拆解(decompose.py)不需要任何服務,永遠能跑;--llm 是加分項,
失敗(沒裝 Ollama、沒開機、沒有模型)時會印警告並「保留規則式結果」繼續跑,
不會讓整個流程失敗。

沿用倉庫既有的 ollama_client.py 連線慣例(OLLAMA_HOST 環境變數)。
模型可用 KM_LLM_MODEL 環境變數指定,預設 qwen2.5:3b。
"""

from __future__ import annotations

import json
import os
import re
import sys

DEFAULT_MODEL = os.environ.get("KM_LLM_MODEL", "qwen2.5:3b")
MAX_SECTIONS = 20  # 避免文件過大時打太多次 API
MAX_CHARS = 1500   # 每個章節送給模型的內容上限

_PROMPT = """你是知識管理助理。以下是一份文件裡的一個章節,請用繁體中文分析,
只回傳一個 JSON 物件(不要任何說明文字、不要 markdown code fence),格式為:
{{"summary": "3句以內摘要", "tags": ["標籤1","標籤2","標籤3"],
  "cues": ["這段內容適合的提問1", "提問2"],
  "distill": "最關鍵的一句洞見",
  "para": "Projects 專案|Areas 責任範疇|Resources 資源庫|Archives 封存 其中一個",
  "express_type": "SOP 標準作業|培訓素材|稽核文件|提案報告|決策備忘|會議摘要 其中一個"}}

章節標題:{title}
章節內容:
{content}
"""


def _extract_json(raw: str) -> dict | None:
    raw = raw.strip()
    raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.M).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _chat(prompt: str, model: str) -> str:
    try:
        from . import ollama_api
    except ImportError:
        import ollama_api
    return ollama_api.chat(prompt, model)


def enhance(result: dict, model: str = DEFAULT_MODEL) -> dict:
    """就地強化 cornell/code/smart 清單;回傳同一份 result(方便串接)。

    只針對 cornell 清單裡的每個章節呼叫一次模型,把回傳結果套用到
    對應的 cornell 與 code 列。decompose.py 對每個章節是同時各 append 一列
    到 cornell 與 code,順序、數量必然一致,所以直接用索引配對即可。
    """
    cornell = result.get("cornell", [])
    code = result.get("code", [])

    enhanced_any = False
    for i, row in enumerate(cornell[:MAX_SECTIONS]):
        content = row["notes"][:MAX_CHARS]
        if not content.strip():
            continue
        prompt = _PROMPT.format(title=row["section"], content=content)
        try:
            raw = _chat(prompt, model)
        except Exception as exc:  # 連不上 / 沒有模型 / 逾時
            print(f"[km_pipeline] --llm 強化失敗,改用規則式結果:{exc}", file=sys.stderr)
            break

        data = _extract_json(raw)
        if not data:
            print(f"[km_pipeline] 模型回傳的內容不是有效 JSON,略過此章節:{row['section']}",
                  file=sys.stderr)
            continue

        enhanced_any = True
        if data.get("summary"):
            row["summary"] = str(data["summary"])[:400]
        if data.get("tags"):
            row["tags"] = " ".join(str(t) for t in data["tags"])
        if data.get("cues"):
            row["cues"] = "\n".join(str(c) for c in data["cues"])

        code_row = code[i] if i < len(code) else None
        if code_row:
            if data.get("distill"):
                code_row["distill"] = str(data["distill"])[:300]
            if data.get("para"):
                code_row["para"] = str(data["para"])
            if data.get("express_type"):
                code_row["express_type"] = str(data["express_type"])
            if data.get("tags"):
                code_row["tags"] = " ".join(str(t) for t in data["tags"])

    if not enhanced_any:
        print("[km_pipeline] 提示:--llm 沒有成功強化任何章節,輸出仍是規則式結果。"
              "確認 Ollama 是否已啟動、模型是否已安裝(ollama pull " + model + ")。",
              file=sys.stderr)
    return result
