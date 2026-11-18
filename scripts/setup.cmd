@echo off
rem Maintained by YunShan_You
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
"%~dp0..\runtime\python\python.exe" "%~dp0setup.py"
pause
