@echo off
setlocal

set "LOG_FILE=%~1"
if "%LOG_FILE%"=="" set "LOG_FILE=gpx2one.log"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-Content ('%LOG_FILE%') -Raw"

endlocal
pause