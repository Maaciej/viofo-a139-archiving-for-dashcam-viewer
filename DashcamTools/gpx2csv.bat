@echo off
setlocal
set "TOOL_DIR=%~dp0"

python "%TOOL_DIR%gpx2csv.py" %*
pause