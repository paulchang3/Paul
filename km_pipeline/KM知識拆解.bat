@echo off
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set "PY=python"
  ) else (
    echo 找不到 Python,即將開啟官網下載頁。
    echo 安裝時請務必勾選 "Add python.exe to PATH",裝好後再雙擊本檔。
    start https://www.python.org/downloads/
    pause
    exit /b 1
  )
)

echo === 步驟 1:環境檢查(自動安裝必要套件 + 自我測試)===
%PY% check_setup.py
if not %errorlevel%==0 (
  echo.
  echo 環境檢查沒通過,請看上面的訊息排除問題後再試一次。
  pause
  exit /b 1
)

if "%~1"=="" (
  echo.
  echo === 用法 ===
  echo 把 .docx / .pdf / .html / .xlsx 檔案拖曳到這個 .bat 上,
  echo 會自動產生同一個資料夾的「檔名_KM知識.xlsx」。
  echo 也可以一次拖曳多個檔案。
  pause
  exit /b 0
)

echo.
echo === 步驟 2:拆解你拖曳的檔案 ===
%PY% main.py %* -o "%~dp1%~n1_KM知識.xlsx"

echo.
echo 完成!輸出檔案:%~dp1%~n1_KM知識.xlsx
pause
