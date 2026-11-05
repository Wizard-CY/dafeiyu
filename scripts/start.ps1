# 大肥鱼一键启动 · packaged by YunShan You
﻿param([switch]$Nested)

$baseDir = Split-Path $PSScriptRoot -Parent
$astrDir = Join-Path $baseDir 'runtime\AstrBot-4.29.3'
$napDir = Join-Path $baseDir 'runtime\napcat-shell'
$env:PATH = (Join-Path $baseDir 'runtime\bin') + ';' + $env:PATH
$env:DASHBOARD_HOST = '127.0.0.1'
$env:PYTHONIOENCODING = 'utf-8'

$statusScript = Join-Path $baseDir 'scripts\status.pyw'
$pythonw = 'C:\Users\Admini\AppData\Local\Programs\Python\Python311\pythonw.exe'
$statusRunning = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'status\.pyw|大肥鱼状态' }
if (-not $statusRunning -and (Test-Path $statusScript) -and (Test-Path $pythonw)) {
    Start-Process -FilePath $pythonw -ArgumentList ('"' + $statusScript + '"') -WindowStyle Hidden
}

function Test-Listening([int]$port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}

function Test-AstrConnected {
    return [bool](Get-NetTCPConnection -State Established -LocalPort 6199 -ErrorAction SilentlyContinue)
}

if (-not (Test-Listening 6185)) {
    Start-Process -FilePath (Join-Path $astrDir '.venv\Scripts\python.exe') -ArgumentList 'main.py' -WorkingDirectory $astrDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $astrDir 'startup.log') -RedirectStandardError (Join-Path $astrDir 'startup-error.log')
}

$qqBackend = Join-Path $baseDir 'backend/qqmusic'
$nodeExe = 'C:\Users\Admini\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe'
if ((Test-Path (Join-Path $qqBackend 'server.mjs')) -and -not (Test-Listening 3311)) {
    Start-Process -FilePath $nodeExe -ArgumentList 'server.mjs' -WorkingDirectory $qqBackend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $qqBackend 'server.log') -RedirectStandardError (Join-Path $qqBackend 'server-error.log')
}

if (-not (Test-Listening 6099)) {
    $isAdmin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    $qqPath = 'E:\QQ\QQ.exe'
    if ($isAdmin) {
        $env:NAPCAT_PATCH_PACKAGE = Join-Path $napDir 'qqnt.json'
        $env:NAPCAT_LOAD_PATH = Join-Path $napDir 'loadNapCat.js'
        $env:NAPCAT_INJECT_PATH = Join-Path $napDir 'NapCatWinBootHook.dll'
        $env:NAPCAT_LAUNCHER_PATH = Join-Path $napDir 'NapCatWinBootMain.exe'
        $env:NAPCAT_MAIN_PATH = Join-Path $napDir 'napcat.mjs'
        Start-Process -FilePath (Join-Path $napDir 'NapCatWinBootMain.exe') -ArgumentList @($qqPath,(Join-Path $napDir 'NapCatWinBootHook.dll'),'-q','1000000000') -WorkingDirectory $napDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $napDir 'startup.log') -RedirectStandardError (Join-Path $napDir 'startup-error.log')
    }
    else {
        $inner = @"
`$n = '$napDir'
`$env:NAPCAT_PATCH_PACKAGE = "`$n\qqnt.json"
`$env:NAPCAT_LOAD_PATH = "`$n\loadNapCat.js"
`$env:NAPCAT_INJECT_PATH = "`$n\NapCatWinBootHook.dll"
`$env:NAPCAT_LAUNCHER_PATH = "`$n\NapCatWinBootMain.exe"
`$env:NAPCAT_MAIN_PATH = "`$n\napcat.mjs"
Start-Process -FilePath "`$n\NapCatWinBootMain.exe" -ArgumentList @('$qqPath', "`$n\NapCatWinBootHook.dll", '-q', '1000000000') -WorkingDirectory `$n -WindowStyle Hidden -RedirectStandardOutput "`$n\startup.log" -RedirectStandardError "`$n\startup-error.log"
"@
        $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($inner))
        try {
            Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile', '-EncodedCommand', $encoded) -ErrorAction Stop
        }
        catch {
            Start-Process -FilePath (Join-Path $napDir 'NapCatWinBootMain.exe') -ArgumentList @($qqPath,(Join-Path $napDir 'NapCatWinBootHook.dll'),'-q','1000000000') -WorkingDirectory $napDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $napDir 'startup.log') -RedirectStandardError (Join-Path $napDir 'startup-error.log')
        }
    }
}

if (-not $Nested) {
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline -and -not (Test-AstrConnected)) {
        Start-Sleep -Seconds 3
    }
    if (-not (Test-AstrConnected)) {
        Add-Type -AssemblyName System.Windows.Forms
        $message = "大肥鱼还没有连上 QQ。`n`n常见原因：`n1. QQ 没有登录（请在弹出的 QQ 窗口登录 1000000000）`n2. 没有点[是]授权管理员权限（NapCat 需要管理员）`n`n登录后再双击一次 [大肥鱼状态中心] 即可。"
        [System.Windows.Forms.MessageBox]::Show($message, '大肥鱼 · 未连接', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
    }
}