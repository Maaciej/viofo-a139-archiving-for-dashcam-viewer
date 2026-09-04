@echo off
setlocal enabledelayedexpansion

for %%I in ("%CD%") do set "FULL_NAME=%%~nxI"
set "NUMBER_STR=!FULL_NAME:~-3!"

echo !NUMBER_STR!| findstr /r "^[0-9][0-9][0-9]$" >nul
if errorlevel 1 (
    echo ERROR: Folder name does not end with NNN (example: "name 001"^)
    pause
    exit /b
)

set "BASENAME=!FULL_NAME:~0,-3!"
for /f "tokens=* delims=0" %%A in ("!NUMBER_STR!") do set /a "NUMBER_INT=%%A"
if "!NUMBER_INT!"=="" set "NUMBER_INT=0"

:MAIN_LOOP
echo ======================================================================
echo PROCESSING FOLDER: !CD!
echo ======================================================================

call viofo2one.bat

echo.
echo FOLDER !NUMBER_STR! FINISHED.
echo.

set /a "NUMBER_INT+=1"
set "TMP_NUM=000!NUMBER_INT!"
set "NUMBER_STR=!TMP_NUM:~-3!"
set "NEXT_FOLDER=..\!BASENAME!!NUMBER_STR!"

if exist "!NEXT_FOLDER!" (
    cd /d "!NEXT_FOLDER!"
    goto MAIN_LOOP
) 
echo ======================================================================
echo VIOFO CRAWLER: all found folders have been processed
echo ======================================================================