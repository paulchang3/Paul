@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >/dev/null 2>nul
if %errorlevel%==0 (
  py -3 "軟體開發專案管理.py" %*
) else (
  where python >/dev/null 2>nul
  if %errorlevel%==0 (
    python "軟體開發專案管理.py" %*
  ) else (
    echo 找不到 Python,即將開啟官網下載頁。
    echo 安裝時請務必勾選 "Add python.exe to PATH",裝好後再雙擊本檔。
    start https://www.python.org/downloads/
  )
)
echo.
pause
