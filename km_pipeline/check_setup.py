"""環境檢查腳本:確認必要套件是否安裝,沒裝會自動 pip install,
然後跑一次 selftest.py 驗證整條流程沒問題(自動安裝 + 自我檢查 + 自動修正)。

    python check_setup.py

給 KM知識拆解.bat 雙擊執行時呼叫,也可以自己單獨執行來排除問題。
"""

from __future__ import annotations

import importlib
import subprocess
import sys

# (匯入名稱, pip 套件名稱, 是否為必要套件)
# pypdf 只有要處理 .pdf 才需要,裝不起來不擋整條流程。
REQUIRED = [
    ("openpyxl", "openpyxl", True),
    ("pypdf", "pypdf", False),
]


def _pip_install(pip_name: str) -> None:
    print(f"    正在自動安裝 {pip_name} ...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", pip_name],
        check=False,
    )


def ensure_packages() -> bool:
    """檢查每個套件;沒裝就自動安裝一次,裝完再檢查一次。回傳必要套件是否都就緒。"""
    all_required_ok = True
    for import_name, pip_name, required in REQUIRED:
        try:
            importlib.import_module(import_name)
            print(f"[OK] {pip_name} 已安裝")
            continue
        except ImportError:
            pass

        _pip_install(pip_name)
        try:
            importlib.invalidate_caches()
            importlib.import_module(import_name)
            print(f"[OK] {pip_name} 自動安裝成功")
        except ImportError:
            note = "" if required else "(選用,不影響 .docx/.html/.xlsx 的處理)"
            print(f"[X ] {pip_name} 自動安裝失敗{note},請手動執行:"
                  f"pip install {pip_name}")
            if required:
                all_required_ok = False
    return all_required_ok


def main() -> int:
    print("=== KM 知識拆解 環境檢查(自動安裝 + 自我測試)===\n")

    if not ensure_packages():
        print("\n必要套件安裝失敗,無法繼續。請檢查網路連線或手動安裝後再試一次。")
        return 1

    print("\n=== 執行自我測試(合成範例跑一次全流程)===\n")
    try:
        from . import selftest
    except ImportError:
        import selftest
    result = selftest.main()

    if result == 0:
        print("\n環境檢查全部通過,可以開始使用了。")
    else:
        print("\n自我測試有項目沒通過,請把上面的訊息回報給 Claude 或檢查程式碼是否被改壞。")
    return result


if __name__ == "__main__":
    sys.exit(main())
