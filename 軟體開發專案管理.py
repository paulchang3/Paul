#!/usr/bin/env python3
"""軟體開發專案管理 —— 單檔工具,放在專案總資料夾最上層。

以本檔所在資料夾為「總部」,每個子資料夾是一個軟體開發專案,
統一管制:目標、WBS(工作分解結構)、版次、命名、編號。

零相依:只用 Python 3.10+ 標準函式庫,不需安裝任何套件。
直接「雙擊」本檔(或配套的 .bat)會進入互動選單;
進階使用者可在終端機下指令:

    python 軟體開發專案管理.py selftest                  SRS 全功能自我檢測
    python 軟體開發專案管理.py init 韌體升級工具          建立新專案(自動編號)
    python 軟體開發專案管理.py list                      所有專案總覽
    python 軟體開發專案管理.py goal P001 "2027Q1 交付"   設定/查看目標
    python 軟體開發專案管理.py wbs  P001 add "需求訪談"   新增 WBS(--parent 1 變子項)
    python 軟體開發專案管理.py wbs  P001 done 1.1        標記完成
    python 軟體開發專案管理.py ver  P001 bump minor -m "新增登入"   升版
    python 軟體開發專案管理.py check                     稽核命名/編號/資料完整性
    python 軟體開發專案管理.py report                    產生 專案總覽.md
"""

from __future__ import annotations  # 讓舊版 Python 也能載入,進到版本守門訊息

import argparse
import builtins
import contextlib
import io
import json
import re
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


def python_ok(version: tuple | None = None) -> bool:
    """REQ-15:版本守門。低於 3.10 回傳 False,由呼叫端友善提示。"""
    v = version or sys.version_info
    return tuple(v[:2]) >= (3, 10)


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


def safe_load(folder: Path) -> dict | None:
    """讀取專案資料;檔案缺失或損壞時回傳 None(由呼叫端標示,不可當機)。"""
    try:
        return load(folder)
    except Exception:
        return None


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
    if not name or any(ch in name for ch in r'\/:*?"<>| '):
        raise SystemExit(r'[X ] 專案名稱不可為空,且不可含空格與 \/:*?"<>| 字元')
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
    return code


def cmd_list(base: Path) -> None:
    items = projects(base)
    if not items:
        print("目前沒有專案,選「建立新專案」(或 init 指令)開始")
        return
    print(f"{'編號':<6} {'版次':<9} {'WBS進度':<9} {'名稱':<20} 目標")
    print("-" * 70)
    for code, folder in items.items():
        d = safe_load(folder)
        if d is None:
            print(f"{code:<6} {'--':<9} {'--':<9} {folder.name:<20} "
                  "[!] 資料損壞,請執行稽核(check)")
            continue
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
            print(f"{code} 尚無 WBS")
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


def cmd_check(base: Path, quiet: bool = False) -> list[str]:
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
            problems.append(f"{p.name}/{PROJECT_FILE} 格式損壞:{type(exc).__name__}")
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
    return problems


def cmd_report(base: Path) -> None:
    lines = [f"# 專案總覽(自動產生 {date.today().isoformat()})", "",
             "| 編號 | 名稱 | 版次 | WBS 進度 | 目標 |", "| --- | --- | --- | --- | --- |"]
    for code, folder in projects(base).items():
        d = safe_load(folder)
        if d is None:
            lines.append(f"| {code} | {folder.name} | -- | -- | [!] 資料損壞 |")
            continue
        done = sum(1 for w in d["wbs"] if w["done"])
        lines.append(f"| {code} | [{d['name']}]({folder.name}/) | {d['version']} "
                     f"| {done}/{len(d['wbs'])} | {d['goal']} |")
    out = base / "專案總覽.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] 已產生 {out.name}")


# ---------- 互動選單(雙擊執行時進入,REQ-13/14:不再閃退) ----------

MENU = """
==== 軟體開發專案管理 ====
 1. 專案總覽            2. 建立新專案
 3. 設定/查看目標       4. 查看 WBS
 5. 新增 WBS 工作       6. 完成 WBS 工作
 7. 升版                8. 版次歷史
 9. 稽核(命名/編號)  10. 產生總覽報告
 0. 離開"""


def interactive(base: Path) -> None:
    print(MENU)
    while True:
        try:
            choice = input("\n請選擇(0-10,直接按 Enter 重印選單):").strip()
        except EOFError:
            return
        try:
            if choice == "0":
                return
            elif choice == "":
                print(MENU)
            elif choice == "1":
                cmd_list(base)
            elif choice == "2":
                cmd_init(base, input("專案名稱(不可含空格):").strip())
            elif choice == "3":
                cmd_goal(base, input("專案編號(如 P001):").strip(),
                         input("新目標(留空=只查看):").strip() or None)
            elif choice == "4":
                cmd_wbs(base, input("專案編號:").strip(), None, None, None)
            elif choice == "5":
                cmd_wbs(base, input("專案編號:").strip(), "add",
                        input("工作名稱:").strip(),
                        input("父項編號(留空=頂層):").strip() or None)
            elif choice == "6":
                cmd_wbs(base, input("專案編號:").strip(), "done",
                        input("WBS 編號(如 1.1):").strip(), None)
            elif choice == "7":
                cmd_ver(base, input("專案編號:").strip(), "bump",
                        input("等級 major/minor/patch:").strip(),
                        input("修改說明:").strip() or "(未填說明)")
            elif choice == "8":
                cmd_ver(base, input("專案編號:").strip(), None, None, "")
            elif choice == "9":
                cmd_check(base)
            elif choice == "10":
                cmd_report(base)
            else:
                print("無此選項,請輸入 0-10")
        except SystemExit as exc:      # 操作錯誤只顯示訊息,選單繼續
            print(exc)
        except KeyboardInterrupt:
            return


# ---------- SRS 自我檢測(用範例檔案逐項驗證需求) ----------

def cmd_selftest() -> None:
    results: list[tuple[str, str, bool, str]] = []

    def req(rid: str, desc: str, fn) -> None:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                fn()
            results.append((rid, desc, True, ""))
        except Exception as exc:
            results.append((rid, desc, False, f"{type(exc).__name__}: {exc}"[:70]))

    def feed(seq):  # 模擬使用者在選單中的輸入
        it = iter(seq)
        return lambda prompt="": next(it)

    print("=== SRS 自我檢測(範例檔案實測)===")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        def t01():
            assert cmd_init(base, "範例專案A") == "P001"
            assert cmd_init(base, "範例專案B") == "P002", "編號應自動遞增"
        req("REQ-01", "專案自動編號 P001、P002 遞增", t01)

        def t02():
            for sub in STD_SUBDIRS:
                assert (base / "P001_範例專案A" / sub).is_dir(), f"缺 {sub}"
        req("REQ-02", "init 自動建立 5 個標準子資料夾", t02)

        def t03():
            try:
                cmd_init(base, "壞 名字")
                raise AssertionError("含空格的名稱應被拒絕")
            except SystemExit:
                pass
        req("REQ-03", "命名管制:拒絕含空格/非法字元名稱", t03)

        def t04():
            cmd_goal(base, "P001", "三個月內交付 MVP")
            assert load(base / "P001_範例專案A")["goal"] == "三個月內交付 MVP"
        req("REQ-04", "目標設定與讀回", t04)

        def t05():
            cmd_wbs(base, "P001", "add", "需求分析", None)
            cmd_wbs(base, "P001", "add", "訪談使用者", "1")
            cmd_wbs(base, "P001", "add", "整理規格書", "1")
            assert [w["code"] for w in load(base / "P001_範例專案A")["wbs"]] \
                == ["1", "1.1", "1.2"]
        req("REQ-05", "WBS 階層編號自動產生 1 → 1.1 → 1.2", t05)

        def t06():
            cmd_wbs(base, "P001", "done", "1.1", None)
            d = load(base / "P001_範例專案A")
            assert [w for w in d["wbs"] if w["code"] == "1.1"][0]["done"] is True
            assert sum(1 for w in d["wbs"] if w["done"]) == 1
        req("REQ-06", "WBS 完成標記與進度統計", t06)

        def t07():
            cmd_ver(base, "P001", "bump", "minor", "新增登入")
            cmd_ver(base, "P001", "bump", "patch", "修正錯字")
            assert load(base / "P001_範例專案A")["version"] == "v0.2.1"
        req("REQ-07", "版次 bump major/minor/patch 規則", t07)

        def t08():
            assert len(load(base / "P001_範例專案A")["history"]) == 3
        req("REQ-08", "版次歷史完整記錄(3 筆)", t08)

        # 製造三種違規的範例檔案,逐項驗證稽核
        (base / "亂取名字的資料夾").mkdir()
        bad = load(base / "P002_範例專案B")
        bad["version"] = "1.0"
        save(base / "P002_範例專案B", bad)
        (base / "P003_損壞範例").mkdir()
        (base / "P003_損壞範例" / PROJECT_FILE).write_text("{壞掉的json", encoding="utf-8")
        probs = cmd_check(base, quiet=True)

        req("REQ-09", "稽核:檢出違規命名資料夾",
            lambda: (_ for _ in ()).throw(AssertionError("未檢出"))
            if not any("命名不符" in p for p in probs) else None)
        req("REQ-10", "稽核:檢出錯誤版次格式",
            lambda: (_ for _ in ()).throw(AssertionError("未檢出"))
            if not any("不符 vX.Y.Z" in p for p in probs) else None)
        req("REQ-11", "稽核:檢出損壞的 project.json",
            lambda: (_ for _ in ()).throw(AssertionError("未檢出"))
            if not any("格式損壞" in p for p in probs) else None)

        def t12():
            cmd_report(base)
            content = (base / "專案總覽.md").read_text(encoding="utf-8")
            assert "P001" in content and "v0.2.1" in content
        req("REQ-12", "report 產生專案總覽.md", t12)

        def t13():
            old = builtins.input
            builtins.input = feed(["2", "選單測試專案", "0"])
            try:
                interactive(base)
            finally:
                builtins.input = old
            assert any(d and d["name"] == "選單測試專案"
                       for d in map(safe_load, projects(base).values()))
        req("REQ-13", "互動選單(雙擊模式)可完成建立專案", t13)

        def t14():
            before = len(projects(base))
            old = builtins.input
            builtins.input = feed(["2", "壞 名字", "1", "0"])
            try:
                interactive(base)  # 輸入非法名稱 → 顯示錯誤 → 選單應繼續運作
            finally:
                builtins.input = old
            assert len(projects(base)) == before, "非法名稱不應建立專案"
        req("REQ-14", "互動選單遇錯誤不閃退、可繼續操作", t14)

        req("REQ-15", "Python 版本守門(<3.10 擋下,>=3.10 放行)",
            lambda: (_ for _ in ()).throw(AssertionError("判斷錯誤"))
            if python_ok((3, 8, 0)) or not python_ok((3, 12, 0)) else None)

    print(f"\n{'需求':<8} {'結果':<4} 說明")
    print("-" * 60)
    failed = 0
    for rid, desc, ok, err in results:
        print(f"{rid:<8} {'PASS' if ok else 'FAIL':<4} {desc}"
              + (f" -- {err}" if err else ""))
        failed += 0 if ok else 1
    total = len(results)
    print("-" * 60)
    if failed:
        print(f"結果:{failed}/{total} 項未通過")
        sys.exit(1)
    print(f"結果:全部需求驗證通過({total}/{total})")


# ---------- 進入點 ----------

def main() -> None:
    if not python_ok():
        print(f"[X ] 需要 Python 3.10 以上,目前是 {sys.version.split()[0]}")
        print("     請到 https://www.python.org/downloads/ 下載安裝,"
              '安裝時記得勾選 "Add python.exe to PATH"')
        if len(sys.argv) == 1:
            with contextlib.suppress(EOFError):
                input("按 Enter 鍵結束...")
        sys.exit(1)

    if len(sys.argv) == 1:           # 雙擊或無參數 → 互動選單
        interactive(SCRIPT_DIR)
        return

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
    sub.add_parser("selftest", help="SRS 自我檢測(範例檔案實測所有需求)")
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
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        if len(sys.argv) == 1:       # 雙擊模式:視窗保持開啟,看得到錯誤
            with contextlib.suppress(EOFError):
                input("\n發生錯誤(內容如上),按 Enter 鍵結束...")
        sys.exit(1)
