@echo off
rem Maintained by YunShan_You
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
