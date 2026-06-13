#!/usr/bin/env python3
"""軟體開發專案管理 —— 單檔工具,放在專案總資料夾最上層。

以本檔所在資料夾為「總部」,每個子資料夾是一個軟體開發專案,
統一管制:目標、WBS(工作分解結構)、版次、命名、編號。

零相依:只用 Python 3.10+ 標準函式庫,不需安裝任何套件。

常用指令(在本檔所在資料夾執行):
    python 軟體開發專案管理.py selftest                  先自我檢查
    python 軟體開發專案管理.py init 韌體升級工具          建立新專案(自動編號)
    python 軟體開發專案管理.py list                      所有專案總覽
    python 軟體開發專案管理.py goal P001 "2027Q1 交付"   設定/查看目標
    python 軟體開發專案管理.py wbs  P001 add "需求訪談"   新增 WBS(--parent 1 變子項)
    python 軟體開發專案管理.py wbs  P001 done 1.1        標記完成
    python 軟體開發專案管理.py ver  P001 bump minor -m "新增登入"   升版
    python 軟體開發專案管理.py check                     稽核命名/編號/資料完整性
    python 軟體開發專案管理.py report                    產生 專案總覽.md
"""

import argparse
import json
import re
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_RE = re.compile(r"^P(\d{3})_(.+)$")          # 專案資料夾命名規則
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")          # 版次規則 v主.次.修
WBS_CODE_RE = re.compile(r"^\d+(\.\d+)*$")            # WBS 編號規則 1.2.3
STD_SUBDIRS = ["01_需求", "02_設計", "03_開發", "04_測試", "05_釋出"]
IGNORED_DIRS = {"__pycache__", ".git", ".claude", "cowork_memory_pack"}
PROJECT_FILE = "project.json"

# Windows 舊主控台(cp950)印不出的字元以 ? 取代,避免當機
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")


# ---------- 基礎 ----------

def projects(base: Path) -> dict[str, Path]:
    """回傳 {專案編號: 資料夾路徑},僅含符合命名規則的子資料夾。"""
    found = {}
    for p in sorted(base.iterdir()):
        m = PROJECT_RE.match(p.name)
        if p.is_dir() and m:
            found[f"P{m.group(1)}"] = p
    return found


def load(folder: Path) -> dict:
    return json.loads((folder / PROJECT_FILE).read_text(encoding="utf-8"))


def save(folder: Path, data: dict) -> None:
    (folder / PROJECT_FILE).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def find(base: Path, code: str) -> tuple[Path, dict]:
    folder = projects(base).get(code.upper())
    if not folder:
        raise SystemExit(f"[X ] 找不到專案 {code},用 list 查看現有專案")
    return folder, load(folder)


def wbs_sort_key(item: dict):
    return tuple(int(x) for x in item["code"].split("."))


# ---------- 指令 ----------

def cmd_init(base: Path, name: str) -> str:
    if any(ch in name for ch in r'\/:*?"<>| '):
        raise SystemExit(r'[X ] 專案名稱不可含空格與 \/:*?"<>| 字元')
    next_no = max([int(c[1:]) for c in projects(base)], default=0) + 1
    code = f"P{next_no:03d}"
    folder = base / f"{code}_{name}"
    folder.mkdir()
    for sub in STD_SUBDIRS:
        (folder / sub).mkdir()
    save(folder, {
        "code": code, "name": name, "goal": "(未設定,用 goal 指令設定)",
        "version": "v0.1.0", "created": date.today().isoformat(),
        "wbs": [],
        "history": [{"version": "v0.1.0",
                     "date": date.today().isoformat(), "note": "建立專案"}],
    })
    print(f"[OK] 已建立 {folder.name}(含 {len(STD_SUBDIRS)} 個標準子資料夾)")
    print(f"     下一步: goal {code} \"你的目標\" → wbs {code} add \"第一項工作\"")
    return code


def cmd_list(base: Path) -> None:
    items = projects(base)
    if not items:
        print("目前沒有專案,用 init <名稱> 建立第一個")
        return
    print(f"{'編號':<6} {'版次':<9} {'WBS進度':<9} {'名稱':<20} 目標")
    print("-" * 70)
    for code, folder in items.items():
        d = load(folder)
        done = sum(1 for w in d["wbs"] if w["done"])
        print(f"{code:<6} {d['version']:<9} {done}/{len(d['wbs']):<7} "
              f"{d['name']:<20} {d['goal'][:30]}")


def cmd_goal(base: Path, code: str, text: str | None) -> None:
    folder, d = find(base, code)
    if text:
        d["goal"] = text
        save(folder, d)
        print(f"[OK] {code} 目標已更新")
    print(f"{code} {d['name']} 的目標:{d['goal']}")


def cmd_wbs(base: Path, code: str, action: str | None,
            name: str | None, parent: str | None) -> None:
    folder, d = find(base, code)
    if action == "add":
        if not name:
            raise SystemExit("[X ] 請提供工作名稱:wbs P001 add \"工作名稱\"")
        codes = [w["code"] for w in d["wbs"]]
        if parent:
            if parent not in codes:
                raise SystemExit(f"[X ] 父項 {parent} 不存在")
            children = [c for c in codes
                        if c.startswith(parent + ".") and "." not in c[len(parent) + 1:]]
            new_code = f"{parent}.{max([int(c.rsplit('.', 1)[1]) for c in children], default=0) + 1}"
        else:
            tops = [int(c) for c in codes if "." not in c]
            new_code = str(max(tops, default=0) + 1)
        d["wbs"].append({"code": new_code, "name": name, "done": False})
        d["wbs"].sort(key=wbs_sort_key)
        save(folder, d)
        print(f"[OK] 已新增 WBS {new_code} {name}")
    elif action == "done":
        if not name:
            raise SystemExit("[X ] 請提供要完成的編號:wbs P001 done 1.1")
        for w in d["wbs"]:
            if w["code"] == name:
                w["done"] = True
                save(folder, d)
                print(f"[OK] {name} {w['name']} 已完成")
                return
        raise SystemExit(f"[X ] 找不到 WBS 編號 {name}")
    else:  # 顯示
        if not d["wbs"]:
            print(f"{code} 尚無 WBS,用 wbs {code} add \"工作名稱\" 新增")
            return
        done = sum(1 for w in d["wbs"] if w["done"])
        print(f"{code} {d['name']}  WBS 進度 {done}/{len(d['wbs'])}")
        for w in sorted(d["wbs"], key=wbs_sort_key):
            indent = "    " * w["code"].count(".")
            mark = "V" if w["done"] else " "
            print(f"  [{mark}] {indent}{w['code']} {w['name']}")


def cmd_ver(base: Path, code: str, action: str | None,
            part: str | None, note: str) -> None:
    folder, d = find(base, code)
    if action == "bump":
        if part not in ("major", "minor", "patch"):
            raise SystemExit("[X ] 用法:ver P001 bump major|minor|patch -m \"說明\"")
        major, minor, patch = (int(x) for x in d["version"][1:].split("."))
        major, minor, patch = {
            "major": (major + 1, 0, 0),
            "minor": (major, minor + 1, 0),
            "patch": (major, minor, patch + 1),
        }[part]
        d["version"] = f"v{major}.{minor}.{patch}"
        d["history"].append({"version": d["version"],
                             "date": date.today().isoformat(), "note": note})
        save(folder, d)
        print(f"[OK] {code} 升版至 {d['version']}")
    else:
        print(f"{code} {d['name']} 目前版次:{d['version']}")
        for h in d["history"]:
            print(f"  {h['version']:<10} {h['date']}  {h['note']}")


def cmd_check(base: Path, quiet: bool = False) -> int:
    problems: list[str] = []
    say = (lambda *_: None) if quiet else print
    say(f"=== 稽核 {base} ===")
    seen_codes: set[str] = set()
    for p in sorted(base.iterdir()):
        if not p.is_dir() or p.name in IGNORED_DIRS or p.name.startswith("."):
            continue
        m = PROJECT_RE.match(p.name)
        if not m:
            problems.append(f"命名不符:{p.name}(規則:P###_名稱,如 P001_韌體升級)")
            continue
        code = f"P{m.group(1)}"
        if code in seen_codes:
            problems.append(f"編號重複:{code}({p.name})")
        seen_codes.add(code)
        if not (p / PROJECT_FILE).exists():
            problems.append(f"{p.name} 缺少 {PROJECT_FILE}(非本工具建立?)")
            continue
        try:
            d = load(p)
        except Exception as exc:
            problems.append(f"{p.name}/{PROJECT_FILE} 格式損壞:{exc}")
            continue
        if d.get("code") != code:
            problems.append(f"{p.name} 內部編號 {d.get('code')} 與資料夾不一致")
        if not VERSION_RE.match(d.get("version", "")):
            problems.append(f"{p.name} 版次 {d.get('version')} 不符 vX.Y.Z 規則")
        for w in d.get("wbs", []):
            if not WBS_CODE_RE.match(w["code"]):
                problems.append(f"{p.name} WBS 編號 {w['code']} 格式錯誤")
    for prob in problems:
        say(f"[X ] {prob}")
    say(f"結果:{'全部合規' if not problems else f'{len(problems)} 個問題待處理'}")
    return len(problems)


def cmd_report(base: Path) -> None:
    lines = [f"# 專案總覽(自動產生 {date.today().isoformat()})", "",
             "| 編號 | 名稱 | 版次 | WBS 進度 | 目標 |", "| --- | --- | --- | --- | --- |"]
    for code, folder in projects(base).items():
        d = load(folder)
        done = sum(1 for w in d["wbs"] if w["done"])
        lines.append(f"| {code} | [{d['name']}]({folder.name}/) | {d['version']} "
                     f"| {done}/{len(d['wbs'])} | {d['goal']} |")
    out = base / "專案總覽.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] 已產生 {out.name}")


# ---------- 自我檢查 ----------

def cmd_selftest() -> None:
    print("=== 自我檢查開始 ===")
    assert sys.version_info >= (3, 10), "需要 Python 3.10 以上"
    print(f"[OK] Python {sys.version.split()[0]}(>= 3.10)")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        code = cmd_init(base, "測試專案A")
        assert code == "P001" and (base / "P001_測試專案A" / "01_需求").is_dir()
        assert cmd_init(base, "測試專案B") == "P002", "編號應自動遞增"
        print("[OK] init:自動編號、標準子資料夾")

        cmd_goal(base, "P001", "三個月內交付 MVP")
        assert load(base / "P001_測試專案A")["goal"] == "三個月內交付 MVP"
        print("[OK] goal:目標設定與讀回")

        cmd_wbs(base, "P001", "add", "需求分析", None)
        cmd_wbs(base, "P001", "add", "訪談使用者", "1")
        cmd_wbs(base, "P001", "add", "整理規格書", "1")
        cmd_wbs(base, "P001", "done", "1.1", None)
        d = load(base / "P001_測試專案A")
        assert [w["code"] for w in d["wbs"]] == ["1", "1.1", "1.2"]
        assert d["wbs"][1]["done"] is True
        print("[OK] wbs:階層編號 1 → 1.1 → 1.2、完成標記")

        cmd_ver(base, "P001", "bump", "minor", "新增登入功能")
        cmd_ver(base, "P001", "bump", "patch", "修正錯字")
        d = load(base / "P001_測試專案A")
        assert d["version"] == "v0.2.1" and len(d["history"]) == 3
        print("[OK] ver:v0.1.0 → v0.2.1、歷史紀錄 3 筆")

        assert cmd_check(base, quiet=True) == 0
        (base / "亂取名字的資料夾").mkdir()
        bad = load(base / "P002_測試專案B")
        bad["version"] = "1.0"
        save(base / "P002_測試專案B", bad)
        assert cmd_check(base, quiet=True) == 2, "應抓到命名與版次 2 個問題"
        print("[OK] check:正確抓出違規命名與錯誤版次")

        cmd_report(base)
        assert "P001" in (base / "專案總覽.md").read_text(encoding="utf-8")
        print("[OK] report:總覽檔產生")
    print("=== 自我檢查全部通過(7 項)===")


# ---------- 進入點 ----------

def main() -> None:
    ap = argparse.ArgumentParser(
        prog="軟體開發專案管理.py",
        description="管制子資料夾專案的目標 / WBS / 版次 / 命名 / 編號")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="所有專案總覽")
    p = sub.add_parser("init", help="建立新專案(自動編號 P###)")
    p.add_argument("name", help="專案名稱(不可含空格)")
    p = sub.add_parser("goal", help="查看或設定專案目標")
    p.add_argument("code"), p.add_argument("text", nargs="?")
    p = sub.add_parser("wbs", help="WBS:顯示 / add / done")
    p.add_argument("code"), p.add_argument("action", nargs="?", choices=["add", "done"])
    p.add_argument("name", nargs="?", help="add=工作名稱;done=WBS編號")
    p.add_argument("--parent", help="add 時指定父項編號,例 --parent 1")
    p = sub.add_parser("ver", help="版次:顯示 / bump major|minor|patch")
    p.add_argument("code"), p.add_argument("action", nargs="?", choices=["bump"])
    p.add_argument("part", nargs="?"), p.add_argument("-m", default="(未填說明)")
    sub.add_parser("check", help="稽核命名 / 編號 / 資料完整性")
    sub.add_parser("report", help="產生 專案總覽.md")
    sub.add_parser("selftest", help="自我檢查(在暫存資料夾測試所有功能)")
    a = ap.parse_args()

    base = SCRIPT_DIR
    if a.cmd == "init":
        cmd_init(base, a.name)
    elif a.cmd == "list":
        cmd_list(base)
    elif a.cmd == "goal":
        cmd_goal(base, a.code, a.text)
    elif a.cmd == "wbs":
        cmd_wbs(base, a.code, a.action, a.name, a.parent)
    elif a.cmd == "ver":
        cmd_ver(base, a.code, a.action, a.part, a.m)
    elif a.cmd == "check":
        sys.exit(1 if cmd_check(base) else 0)
    elif a.cmd == "report":
        cmd_report(base)
    elif a.cmd == "selftest":
        cmd_selftest()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
