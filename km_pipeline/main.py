#!/usr/bin/env python3
"""KM 知識輸入工作流:把 PDF / Word / Excel / HTML 拆解成一份多分頁的知識 Excel。

    python main.py 文件1.docx 文件2.pdf -o 輸出.xlsx
    python main.py 我的文件資料夾/ -o 輸出.xlsx --llm

輸入可以是檔案或資料夾(資料夾會自動掃描裡面的 .docx/.pdf/.html/.xlsx)。
輸出固定六個分頁:00_Index / WBS_Tree / Action_Tree / Cornell_Notes /
SMART_Notes / CODE_Notes,詳見 README.md 或輸出檔案本身的 00_Index 分頁。

--llm 需要本機已安裝並啟動 Ollama(見倉庫根目錄的 scripts/ollama-up.sh);
沒有的話省略 --llm,程式一樣會用規則式拆解產生完整結果。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from . import build_excel, decompose, extract, llm_enhance
except ImportError:  # 直接以 python main.py 執行時
    import build_excel
    import decompose
    import extract
    import llm_enhance

SUPPORTED_SUFFIXES = {".docx", ".pdf", ".html", ".htm", ".xlsx", ".xlsm"}


def _collect_inputs(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in SUPPORTED_SUFFIXES)
        elif p.is_file():
            if p.suffix.lower() not in SUPPORTED_SUFFIXES:
                print(f"略過不支援的檔案:{p}", file=sys.stderr)
                continue
            files.append(p)
        else:
            print(f"找不到:{p}", file=sys.stderr)
    return files


def run(input_paths: list[str], output_path: str, use_llm: bool, llm_model: str) -> Path:
    files = _collect_inputs(input_paths)
    if not files:
        raise SystemExit("沒有找到任何可處理的檔案(支援 .docx/.pdf/.html/.xlsx)")

    merged = {"wbs": [], "actions": [], "cornell": [], "smart": [], "code": []}
    for f in files:
        print(f"處理中:{f}")
        blocks = extract.extract(f)
        result = decompose.decompose(blocks, source=f.name)
        if use_llm:
            result = llm_enhance.enhance(result, model=llm_model)
        for key in merged:
            merged[key].extend(result[key])

    out = build_excel.write_workbook(
        merged, output_path, sources=[f.name for f in files],
        llm_model=llm_model if use_llm else None,
    )
    print(f"完成!已寫入 {out}")
    print(f"  WBS 節點 {len(merged['wbs'])} 筆、"
          f"行動項目 {len(merged['actions'])} 筆、"
          f"康乃爾筆記 {len(merged['cornell'])} 筆、"
          f"SMART 筆記 {len(merged['smart'])} 筆、"
          f"CODE 筆記 {len(merged['code'])} 筆")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("inputs", nargs="+", help="輸入檔案或資料夾(.docx/.pdf/.html/.xlsx)")
    parser.add_argument("-o", "--output", default="km_knowledge.xlsx", help="輸出的 .xlsx 路徑")
    parser.add_argument("--llm", action="store_true", help="用本機 Ollama 強化摘要/標籤/分類")
    parser.add_argument("--llm-model", default=llm_enhance.DEFAULT_MODEL,
                         help="--llm 使用的模型名稱(預設 %(default)s，或設 KM_LLM_MODEL）")
    args = parser.parse_args()

    run(args.inputs, args.output, args.llm, args.llm_model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
