@echo off
chcp 65001 >nul
setlocal
set "HERE=%~dp0"
for %%I in ("%HERE%..\..") do set "ROOT=%%~fI"
set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
title RAG + MCP 知識庫

:menu
cls
echo ============================================================
echo   RAG + MCP 知識庫  啟動選單
echo   直譯器: %PY%
echo ============================================================
echo    [1] 執行 Demo（索引 5 筆法規 + 語意搜尋）
echo    [2] 環境自我檢查 check_setup
echo    [3] 安裝 / 更新套件 install_deps
echo    [4] 產生本機 MCP 設定 (--config)
echo    [0] 離開
echo ============================================================
set "c="
set /p "c=請輸入選項並按 Enter: "
if "%c%"=="1" goto demo
if "%c%"=="2" goto check
if "%c%"=="3" goto install
if "%c%"=="4" goto config
if "%c%"=="0" exit /b 0
goto menu

:demo
echo.
"%PY%" "%HERE%demo.py"
echo.
pause
goto menu

:check
echo.
"%PY%" "%HERE%check_setup.py"
echo.
pause
goto menu

:install
echo.
call "%HERE%install_deps.bat"
goto menu

:config
echo.
"%PY%" "%HERE%check_setup.py" --config
echo.
pause
goto menu
