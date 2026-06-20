@echo off
chcp 65001 >nul
set "ROOT=E:\113_製作\710_AI test\001_2606_MCP"
set "PY=%ROOT%\.venv\Scripts\python.exe"
echo [1/2] 安裝必要套件（mcp / fastmcp / ollama / chromadb / sentence-transformers）...
"%PY%" -m pip install --upgrade mcp fastmcp ollama chromadb sentence-transformers
echo.
echo [2/2] 執行環境自我檢查...
"%PY%" "%ROOT%\examples\rag_mcp\check_setup.py"
echo.
echo Done.
pause
