@echo off
setlocal
rem Maintained by YunShan_You
chcp 65001 >nul
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "LOGDIR=%ROOT%\runtime\logs"
set "LOG=%LOGDIR%\launcher.log"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1
echo.>>"%LOG%"
echo [%date% %time%] start.cmd begin>>"%LOG%"

if /i "%~1"=="check" (
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -CheckOnly
  echo.
  pause
  exit /b 0
)

if not exist "%~dp0start.ps1" (
  echo start.ps1 not found. Please extract the whole package first.
  echo [%date% %time%] start.ps1 missing>>"%LOG%"
  pause
  exit /b 1
)

echo Starting DaFeiYu 2.0 ... first start may take 1-2 minutes.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" >>"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
>>"%LOG%" echo [%date% %time%] start.cmd exit=%RC%
if "%RC%"=="0" exit /b 0

echo.
echo DaFeiYu failed to start. Error code: %RC%
echo Log file: "%LOG%"
echo Also check the logs under:
echo   "%ROOT%\runtime\logs"
echo   "%ROOT%\runtime\AstrBot-4.29.3\startup.log"
echo   "%ROOT%\runtime\napcat-shell\startup.log"
echo.
echo Run scripts\diagnose.cmd to collect a report for support.
echo.
pause
exit /b %RC%
