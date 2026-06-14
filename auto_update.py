"""
auto_update.py - 自動更新機制（從 GitHub Releases 下載最新版）
使用方式：python auto_update.py
"""

from __future__ import annotations

import json
import os
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

# ── 設定（請依實際 GitHub 倉庫修改）──────────────────────────────────────────
GITHUB_REPO  = "your-username/multi-mobile-qr-controller"
CURRENT_VERSION = "1.0.0"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

BASE_DIR = Path(__file__).parent


def get_latest_release() -> Optional[dict]:
    """查詢 GitHub API 取得最新 Release 資訊"""
    try:
        req = Request(API_URL, headers={"User-Agent": "QRController-Updater/1.0"})
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except (URLError, json.JSONDecodeError) as exc:
        print(f"[!] 無法取得更新資訊：{exc}")
        return None


def _version_tuple(v: str) -> tuple:
    """將版本字串轉為可比較的 tuple，例如 '1.2.3' → (1, 2, 3)"""
    return tuple(int(x) for x in v.lstrip("v").split(".") if x.isdigit())


def check_update() -> Optional[dict]:
    """
    檢查是否有新版本。
    回傳 release dict（若有新版），否則回傳 None。
    """
    release = get_latest_release()
    if not release:
        return None

    latest_tag = release.get("tag_name", "").lstrip("v")
    if not latest_tag:
        return None

    if _version_tuple(latest_tag) > _version_tuple(CURRENT_VERSION):
        print(f"[!] 發現新版本 v{latest_tag}（當前 v{CURRENT_VERSION}）")
        return release

    print(f"[✓] 已是最新版本 v{CURRENT_VERSION}")
    return None


def download_and_apply(release: dict) -> bool:
    """
    下載最新 ZIP 並解壓覆蓋。
    回傳 True 表示更新成功。
    """
    assets = release.get("assets", [])
    zip_asset = next(
        (a for a in assets if a["name"].endswith(".zip")), None
    )
    if not zip_asset:
        print("[!] Release 中沒有 .zip 資產，跳過更新")
        return False

    dl_url  = zip_asset["browser_download_url"]
    zip_path = BASE_DIR / "_update.zip"
    backup   = BASE_DIR / "_backup"

    print(f"[~] 下載 {zip_asset['name']} ...")
    try:
        req = Request(dl_url, headers={"User-Agent": "QRController-Updater/1.0"})
        with urlopen(req, timeout=60) as resp, open(zip_path, "wb") as f:
            shutil.copyfileobj(resp, f)
    except Exception as exc:
        print(f"[✗] 下載失敗：{exc}")
        return False

    # 備份目前版本
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir()
    for item in BASE_DIR.iterdir():
        if item.name not in ("_update.zip", "_backup", ".venv", "logs"):
            dest = backup / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

    # 解壓更新
    print("[~] 套用更新...")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(BASE_DIR)
        zip_path.unlink()
        print("[✓] 更新完成！請重新啟動程式")
        return True
    except Exception as exc:
        print(f"[✗] 解壓失敗，正在還原備份：{exc}")
        # 還原備份
        for item in backup.iterdir():
            dest = BASE_DIR / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        return False


def main() -> None:
    print("=" * 50)
    print("  Multi-Mobile QR Controller — 自動更新")
    print(f"  當前版本：v{CURRENT_VERSION}")
    print("=" * 50)

    release = check_update()
    if release:
        user_input = input("是否立即更新？[y/N] ").strip().lower()
        if user_input == "y":
            success = download_and_apply(release)
            if success:
                print("\n請重新執行 main.py 或 deploy.bat")
        else:
            print("已取消更新")
    print()


if __name__ == "__main__":
    main()
