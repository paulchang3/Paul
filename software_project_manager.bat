@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >/dev/null 2>nul
if %errorlevel%==0 (
  py -3 "software_project_manager.py" %*
) else (
  where python >/dev/null 2>nul
  if %errorlevel%==0 (
    python "software_project_manager.py" %*
  ) else (
    echo 找不到 Python,即將開啟官網下載頁。
    echo 安裝時請務必勾選 "Add python.exe to PATH",裝好後再雙擊本檔。
    start https://www.python.org/downloads/
  )
)
echo.
pause
