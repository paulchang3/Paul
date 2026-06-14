"""
installer.py - 自動環境檢查與套件安裝模組
執行 main.py 前先呼叫 ensure_environment()
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import os
from pathlib import Path
from typing import NamedTuple

# 需要的套件 (import名稱, pip安裝名稱)
REQUIRED_PACKAGES: list[tuple[str, str]] = [
    ("fastapi",       "fastapi==0.111.0"),
    ("uvicorn",       "uvicorn[standard]==0.29.0"),
    ("websockets",    "websockets==12.0"),
    ("qrcode",        "qrcode[pil]==7.4.2"),
    ("PIL",           "Pillow==10.3.0"),
    ("psutil",        "psutil==5.9.8"),
    ("socketio",      "python-socketio==5.11.2"),
    ("multipart",     "python-multipart==0.0.9"),
    ("aiofiles",      "aiofiles==23.2.1"),
    ("PySide6",       "PySide6==6.7.0"),
    ("jinja2",        "jinja2==3.1.4"),
]

# netifaces 在某些環境需要編譯，單獨處理
OPTIONAL_PACKAGES: list[tuple[str, str]] = [
    ("netifaces",     "netifaces==0.11.0"),
]


class CheckResult(NamedTuple):
    ok: bool
    message: str


def _pip_install(package_spec: str) -> bool:
    """使用 pip 安裝指定套件，回傳是否成功。"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_spec,
             "--quiet", "--no-warn-script-location"],
            capture_output=True, text=True, timeout=120,
        )
        return result.returncode == 0
    except Exception as exc:
        print(f"  [installer] pip 安裝失敗: {exc}")
        return False


def check_python_version() -> CheckResult:
    """確認 Python >= 3.11"""
    major, minor = sys.version_info.major, sys.version_info.minor
    if major >= 3 and minor >= 11:
        return CheckResult(True, f"Python {major}.{minor} ✓")
    return CheckResult(False, f"Python {major}.{minor} — 需要 3.11+")


def check_pip() -> CheckResult:
    """確認 pip 可用"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            ver = result.stdout.split()[1]
            return CheckResult(True, f"pip {ver} ✓")
    except Exception:
        pass
    return CheckResult(False, "pip 不可用")


def check_network() -> CheckResult:
    """嘗試 DNS 解析確認網路連線"""
    import socket
    try:
        socket.setdefaulttimeout(3)
        socket.getaddrinfo("pypi.org", 443)
        return CheckResult(True, "網路連線正常 ✓")
    except Exception:
        return CheckResult(False, "無法連線至 PyPI（離線模式）")


def install_missing_packages(verbose: bool = True) -> bool:
    """
    檢查所有必要套件，若缺少則自動安裝。
    回傳 True 表示全部就緒。
    """
    all_ok = True

    for import_name, pip_spec in REQUIRED_PACKAGES:
        try:
            importlib.import_module(import_name)
            if verbose:
                print(f"  [✓] {import_name}")
        except ImportError:
            if verbose:
                print(f"  [!] 缺少 {import_name}，正在安裝 {pip_spec} ...")
            ok = _pip_install(pip_spec)
            if ok:
                # 重新嘗試 import 驗證
                try:
                    importlib.import_module(import_name)
                    if verbose:
                        print(f"  [✓] {import_name} 安裝完成")
                except ImportError:
                    if verbose:
                        print(f"  [✗] {import_name} 安裝後仍無法 import")
                    all_ok = False
            else:
                if verbose:
                    print(f"  [✗] {import_name} 安裝失敗")
                all_ok = False

    # 選用套件（失敗不中斷）
    for import_name, pip_spec in OPTIONAL_PACKAGES:
        try:
            importlib.import_module(import_name)
            if verbose:
                print(f"  [✓] {import_name} (選用)")
        except ImportError:
            if verbose:
                print(f"  [~] 嘗試安裝選用套件 {pip_spec} ...")
            _pip_install(pip_spec)

    return all_ok


def ensure_directories() -> None:
    """確保 logs、static 等目錄存在"""
    base = Path(__file__).parent
    for d in ["logs", "static/css", "static/js", "static/images", "templates"]:
        (base / d).mkdir(parents=True, exist_ok=True)


def ensure_environment(verbose: bool = True) -> bool:
    """
    完整環境自我檢查入口，由 main.py 呼叫。
    回傳 True 代表環境就緒，可繼續啟動。
    """
    print("=" * 56)
    print("  Multi-Mobile QR Controller — 環境自動檢查")
    print("=" * 56)

    # 1. Python 版本
    result = check_python_version()
    print(f"  Python 版本  : {result.message}")
    if not result.ok:
        print("  ✗ 請升級至 Python 3.11 以上再執行")
        return False

    # 2. pip
    result = check_pip()
    print(f"  pip 狀態     : {result.message}")

    # 3. 網路
    result = check_network()
    print(f"  網路狀態     : {result.message}")

    # 4. 套件
    print("\n  檢查並安裝相依套件：")
    ok = install_missing_packages(verbose=verbose)

    # 5. 目錄
    ensure_directories()

    print("=" * 56)
    if ok:
        print("  環境就緒，開始啟動伺服器 ✓")
    else:
        print("  部分套件安裝失敗，程式可能無法正常運作")
    print("=" * 56)
    return ok
