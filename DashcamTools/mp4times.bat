@echo off
setlocal
set "TOOL_DIR=%~dp0"

python "%TOOL_DIR%mp4times.py" %*
pause