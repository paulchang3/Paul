@echo off
chcp 65001 >nul
setlocal
set "HERE=%~dp0"
for %%I in ("%HERE%..\..") do set "ROOT=%%~fI"
set "TARGET=%HERE%run.bat"
set "ICON=%ROOT%\.venv\Scripts\python.exe"
if not exist "%ICON%" set "ICON=%SystemRoot%\System32\cmd.exe"

echo 正在於桌面建立捷徑...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$desk=[Environment]::GetFolderPath('Desktop'); $lnk=Join-Path $desk 'RAG 知識庫.lnk'; $ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut($lnk); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%HERE%'; $s.IconLocation='%ICON%'; $s.Description='RAG + MCP 知識庫 啟動選單'; $s.Save(); if (Test-Path $lnk) { Write-Host ('[完成] 已建立桌面捷徑: ' + $lnk) } else { Write-Host '[失敗] 捷徑未建立' }"

echo.
pause
