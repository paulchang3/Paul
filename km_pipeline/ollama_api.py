"""與本機 Ollama 伺服器溝通的最小 API 層(只用 Python 標準函式庫)。

預設連到 http://127.0.0.1:11434,可用環境變數 OLLAMA_HOST 覆寫
(與 ollama CLI 使用同一個變數)。與 fmea_expert/ollama_api.py 是同一份寫法。
"""

import json
import os
import urllib.request


def base_url() -> str:
    host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
    if "://" not in host:
        host = "http://" + host
    return host.rstrip("/")


def chat(prompt: str, model: str) -> str:
    """單輪對話,回傳模型的回答文字。"""
    req = urllib.request.Request(
        base_url() + "/api/chat",
        data=json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)["message"]["content"]
