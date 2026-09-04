@echo off
:: viofo_settime 20260310_095533 2.mp4
:: script sets videofile datetime to "provided datetime + duration of video"
::this way Dashcam Viewer shows specified time on the beginning of video

setlocal enabledelayedexpansion


if "%~1"=="" goto :usage
if "%~2"=="" goto :usage

set "START_DT=%~1"
set "VIDEO_FILE=%~2"


powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$durationRaw = ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 \"%VIDEO_FILE%\";" ^
    "if ([string]::IsNullOrWhiteSpace($durationRaw)) { Write-Error 'Cannot retrieve video duration'; exit 1 };" ^
    "$secs = [int][Math]::Ceiling([double]$durationRaw.Trim());" ^
    "$culture = [System.Globalization.CultureInfo]::InvariantCulture;" ^
    "$startTime = [DateTime]::ParseExact('%START_DT%', 'yyyyMMdd_HHmmss', $culture);" ^
    "$endTime = $startTime.AddSeconds($secs);" ^
    "(Get-Item \"%VIDEO_FILE%\").LastWriteTime = $endTime;" ^
    "Write-Host 'Success: Updated file modified time to:' $endTime.ToString('yyyy-MM-dd HH:mm:ss') -ForegroundColor Green"

goto :eof

:usage
echo Usage:
echo %~nx0 [RRRRMMDD_GGMMSS] [video_filename.mp4]
echo Przyklad:
echo %~nx0 20260310_095533 2.mp4
exit /b 1

