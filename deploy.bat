@echo off
chcp 65001 >nul
title Multi-Mobile QR Controller — 啟動器

echo ============================================
echo   Multi-Mobile QR Controller
echo   自動部署 ^& 啟動腳本
echo ============================================
echo.

:: 檢查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [錯誤] 找不到 Python，請先安裝 Python 3.11+
    echo        下載網址：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [✓] Python 已安裝
echo.

:: 切換到腳本所在目錄
cd /d "%~dp0"

:: 建立虛擬環境（若尚未建立）
if not exist ".venv" (
    echo [~] 建立虛擬環境 .venv ...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [錯誤] 無法建立虛擬環境
        pause
        exit /b 1
    )
    echo [✓] 虛擬環境建立完成
) else (
    echo [✓] 虛擬環境已存在
)

:: 啟動虛擬環境
call .venv\Scripts\activate.bat

:: 升級 pip
python -m pip install --upgrade pip --quiet

:: 安裝/更新相依套件
echo.
echo [~] 安裝相依套件...
pip install -r requirements.txt --quiet
echo [✓] 套件安裝完成
echo.

:: 防火牆規則（需要管理員權限才能執行，失敗時跳過）
echo [~] 嘗試開放防火牆 Port 8000 ...
netsh advfirewall firewall add rule name="QR Controller" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
if %errorlevel% equ 0 (
    echo [✓] 防火牆規則已設定
) else (
    echo [!] 防火牆設定需要管理員權限，請手動開放 TCP Port 8000
)

echo.
echo [✓] 所有準備完成，啟動程式...
echo ============================================
echo.

:: 啟動主程式
python main.py

echo.
echo [程式已結束]
pause
