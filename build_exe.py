"""
build_exe.py - 使用 PyInstaller 打包成 Windows .exe
執行方式：python build_exe.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent


def build() -> None:
    print("=" * 56)
    print("  Multi-Mobile QR Controller — 打包為 EXE")
    print("=" * 56)

    # 確認 PyInstaller 已安裝
    try:
        import PyInstaller  # noqa
    except ImportError:
        print("[!] 安裝 PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # 額外需要打包進去的資料目錄
    datas = [
        ("templates", "templates"),
        ("static",    "static"),
    ]
    add_data_args: list[str] = []
    for src, dst in datas:
        sep = ";" if sys.platform == "win32" else ":"
        add_data_args += ["--add-data", f"{src}{sep}{dst}"]

    # PyInstaller 指令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",                     # 單一 exe
        "--windowed",                    # 無 console 視窗（GUI 模式）
        "--name", "QRController",
        "--icon", str(BASE / "static" / "images" / "icon.ico")
        if (BASE / "static" / "images" / "icon.ico").exists()
        else "NONE",
        # 隱藏的 import（FastAPI/Uvicorn 動態載入模組）
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "fastapi",
        "--hidden-import", "websockets",
        "--hidden-import", "aiofiles",
        "--hidden-import", "PySide6.QtWebEngineWidgets",
        "--hidden-import", "PySide6.QtWebEngineCore",
        "--hidden-import", "engineio.async_drivers.aiohttp",
        *add_data_args,
        "main.py",
    ]

    # 過濾掉 icon=NONE 的情況
    cmd = [c for c in cmd if c != "NONE"]
    # 若 icon 前一個是 --icon 但後面是 NONE，一起移除
    i = 0
    clean_cmd: list[str] = []
    while i < len(cmd):
        if cmd[i] == "--icon" and i + 1 < len(cmd):
            i += 2   # 跳過（icon 路徑不存在就不加）
        else:
            clean_cmd.append(cmd[i])
            i += 1

    print("\n[~] 執行打包指令...")
    print(" ".join(clean_cmd))
    print()

    result = subprocess.run(clean_cmd, cwd=str(BASE))
    if result.returncode == 0:
        exe = BASE / "dist" / "QRController.exe"
        print(f"\n[✓] 打包完成！")
        print(f"    輸出路徑：{exe}")
    else:
        print("\n[✗] 打包失敗，請查看上方錯誤訊息")


if __name__ == "__main__":
    build()
