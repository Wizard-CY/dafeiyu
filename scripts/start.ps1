# 大肥鱼 2.0 · 一键启动
# 整理：YunShan_You（悠云山）
# 需要先按 README 第 2 节替换机器人 QQ 和主人 QQ。
param([switch]$Nested, [switch]$CheckOnly)

$ErrorActionPreference = 'Continue'

$baseDir = Split-Path $PSScriptRoot -Parent
$astrDir = Join-Path $baseDir 'runtime\AstrBot-4.29.3'
$napDir = Join-Path $baseDir 'runtime\napcat-shell'
$pyDir = Join-Path $baseDir 'runtime\python'
$python = Join-Path $pyDir 'python.exe'
$pythonw = Join-Path $pyDir 'pythonw.exe'
$nodeExe = Join-Path $baseDir 'runtime\bin\node.exe'
$statusScript = Join-Path $baseDir 'scripts\status.pyw'
$qqInstaller = Join-Path $baseDir 'runtime\installer\QQ_9.9.36_260924_x64_01.exe'
$logDir = Join-Path $baseDir 'runtime\logs'
$logPath = Join-Path $logDir '启动.log'
$botQQ = '1000000000'

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$env:PATH = (Join-Path $baseDir 'runtime\bin') + ';' + $pyDir + ';' + $env:PATH
$env:PYTHONIOENCODING = 'utf-8'
$env:DASHBOARD_HOST = '127.0.0.1'

$isAdmin = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

$problems = New-Object System.Collections.Generic.List[string]
$qqPath = $null
$qqVersion = $null

function Write-StartupLog {
    param([string]$Text)
    try {
        if ((Test-Path $logPath) -and ((Get-Item $logPath).Length -gt 512KB)) {
            Move-Item -LiteralPath $logPath -Destination ($logPath + '.old') -Force -ErrorAction SilentlyContinue
        }
        $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),
            $(if ($Nested) { 'autostart' } else { 'manual' }), $Text
        Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
    }
    catch {
        # Logging must never stop the launcher.
    }
}

function Add-Problem {
    param([string]$Text)
    $problems.Add($Text)
    Write-StartupLog ('PROBLEM: ' + $Text)
}

function Show-Alert {
    param([string]$Message)
    Write-StartupLog ('ALERT: ' + $Message)
    if ($Nested) { return }
    try {
        $shell = New-Object -ComObject WScript.Shell -ErrorAction Stop
        $shell.Popup($Message, 0, '大肥鱼 · 启动提示', 48) | Out-Null
        return
    }
    catch {
    }
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        [System.Windows.Forms.MessageBox]::Show($Message, '大肥鱼 · 启动提示',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
    }
    catch {
    }
}

function Test-Listening {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Test-AstrConnected {
    return [bool](Get-NetTCPConnection -State Established -LocalPort 6199 -ErrorAction SilentlyContinue)
}

function Start-HiddenProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory = '',
        [string]$RedirectStandardOutput = '',
        [string]$RedirectStandardError = ''
    )
    $params = @{
        FilePath = $FilePath
        WindowStyle = 'Hidden'
        PassThru = $true
    }
    if ($ArgumentList.Count -gt 0) { $params['ArgumentList'] = $ArgumentList }
    if ($WorkingDirectory) { $params['WorkingDirectory'] = $WorkingDirectory }
    if ($RedirectStandardOutput) { $params['RedirectStandardOutput'] = $RedirectStandardOutput }
    if ($RedirectStandardError) { $params['RedirectStandardError'] = $RedirectStandardError }
    return Start-Process @params
}

function Quote-PathArg {
    param([Parameter(Mandatory = $true)][string]$Value)
    # Start-Process 的 ArgumentList 不会自动加引号，路径里有空格就必须自己包上。
    return '"' + $Value + '"'
}

# ── 目录写权限 ────────────────────────────────────────────────
$writeOK = $false
try {
    $probe = Join-Path $logDir ('.write_test_' + [guid]::NewGuid().ToString('N'))
    Set-Content -LiteralPath $probe -Value 'ok' -ErrorAction Stop
    Remove-Item -LiteralPath $probe -Force -ErrorAction Stop
    $writeOK = $true
}
catch {
    Add-Problem '当前目录不能写（可能在 Program Files、只读盘或被安全软件锁住），请把整个文件夹放到用户目录后再试。'
}

# ── 本机路径（可选覆盖） ───────────────────────────────────────
# 在 scripts\paths.local.ps1 里写 $qqPath = 'D:\QQ\QQ.exe' 可以跳过自动探测。
$localPaths = Join-Path $PSScriptRoot 'paths.local.ps1'
if (Test-Path $localPaths) {
    . $localPaths
}

if (-not ($qqPath -and (Test-Path $qqPath))) {
    $qqPath = $null
    foreach ($key in @(
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\QQ',
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\QQ'
    )) {
        try {
            $uninstall = (Get-ItemProperty -Path $key -Name UninstallString -ErrorAction Stop).UninstallString
            $uninstallDir = Split-Path ($uninstall -replace '"', '') -Parent
            $candidate = Join-Path $uninstallDir 'QQ.exe'
            if (Test-Path $candidate) { $qqPath = $candidate; break }
        }
        catch {
        }
    }
}

if (-not $qqPath) {
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:ProgramFiles) {
        $candidates.Add((Join-Path $env:ProgramFiles 'Tencent\QQNT\QQ.exe'))
    }
    if (${env:ProgramFiles(x86)}) {
        $candidates.Add((Join-Path ${env:ProgramFiles(x86)} 'Tencent\QQNT\QQ.exe'))
    }
    $candidates.Add('C:\Program Files\Tencent\QQNT\QQ.exe')
    $candidates.Add('D:\Program Files\Tencent\QQNT\QQ.exe')
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { $qqPath = $candidate; break }
    }
}

if (-not $qqPath) {
    $runningQQ = Get-Process QQ -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($runningQQ -and $runningQQ.Path -and (Test-Path $runningQQ.Path)) {
        $qqPath = $runningQQ.Path
    }
}

try {
    $qqVersion = (Get-ItemProperty -Path 'HKCU:\Software\Tencent\QQNT' -Name version -ErrorAction Stop).version
}
catch {
    $qqVersion = $null
}

Write-StartupLog ('========== 启动请求 ==========')
Write-StartupLog ('模式：{0}；管理员：{1}；QQ：{2}；版本：{3}' -f
    $(if ($Nested) { '后台' } else { '手动' }), $isAdmin, $qqPath, $qqVersion)

if ($CheckOnly) {
    Write-Output '大肥鱼 2.0 · 启动环境检查'
    Write-Output ('包目录：' + $baseDir)
    Write-Output ('目录里有空格：' + [bool]($baseDir -match ' '))
    Write-Output ('Python：' + $(if (Test-Path $python) { 'OK' } else { '缺失' }))
    Write-Output ('pythonw：' + $(if (Test-Path $pythonw) { 'OK' } else { '缺失' }))
    Write-Output ('AstrBot main.py：' + $(if (Test-Path (Join-Path $astrDir 'main.py')) { 'OK' } else { '缺失' }))
    Write-Output ('控制中心 status.pyw：' + $(if (Test-Path $statusScript) { 'OK' } else { '缺失' }))
    Write-Output ('NapCat：' + $(if (Test-Path (Join-Path $napDir 'NapCatWinBootMain.exe')) { 'OK' } else { '缺失' }))
    Write-Output ('NapCat chunk：' + $(if (Test-Path (Join-Path $napDir 'conout-wiJ7YKRd.js')) { 'OK' } else { '缺失（会卡在注入阶段）' }))
    Write-Output ('Node：' + $(if (Test-Path $nodeExe) { 'OK' } else { '缺失（不影响聊天）' }))
    Write-Output ('QQ 路径：' + $(if ($qqPath) { $qqPath } else { '没找到' }))
    Write-Output ('QQ 版本：' + $(if ($qqVersion) { $qqVersion } else { '未知' }))
    Write-Output ('管理员：' + $isAdmin)
    Write-Output ('目录可写：' + $writeOK)
    $cfgPath = Join-Path $astrDir 'data\cmd_config.json'
    $keyCount = 0
    if (Test-Path -LiteralPath $cfgPath) {
        try {
            $cfg = Get-Content -LiteralPath $cfgPath -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json
            if ($cfg -and $cfg.provider_sources) {
                $keyCount = @($cfg.provider_sources[0].key).Count
            }
        }
        catch {
        }
    }
    Write-Output ('API Key 已填：' + ($keyCount -gt 0))
    try {
        $selfText = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'start.ps1') -Raw -Encoding UTF8
        Write-Output ('机器人 QQ 还是占位符：' + [bool]($selfText -match "'1000000000'"))
    }
    catch {
    }
    exit 0
}

# ── 控制中心（托盘） ──────────────────────────────────────────
$statusRows = @(
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match 'status\.pyw' }
)
if ($statusRows.Count -eq 0) {
    if ((Test-Path $statusScript) -and (Test-Path $pythonw)) {
        try {
            $proc = Start-HiddenProcess -FilePath $pythonw -ArgumentList @((Quote-PathArg $statusScript))
            Write-StartupLog ('已启动控制中心（PID {0}，托盘）。' -f $proc.Id)
        }
        catch {
            Add-Problem ('控制中心启动失败：' + $_.Exception.Message)
        }
    }
    else {
        Add-Problem '找不到控制中心或 pythonw，请确认包是完整解压的。'
    }
}
else {
    Write-StartupLog ('控制中心已在运行（PID {0}）。' -f (($statusRows | Select-Object -First 1).ProcessId))
}

# ── 聊天程序 ─────────────────────────────────────────────────
function Start-AstrBot {
    if (Test-Listening 6185) {
        Write-StartupLog '聊天程序已经在监听 6185，跳过启动。'
        return
    }
    $astrMain = Join-Path $astrDir 'main.py'
    if (-not (Test-Path $python) -or -not (Test-Path $astrMain)) {
        Add-Problem ('找不到聊天程序：' + $astrMain)
        return
    }
    try {
        $proc = Start-HiddenProcess -FilePath $python -ArgumentList @((Quote-PathArg $astrMain)) `
            -WorkingDirectory $astrDir `
            -RedirectStandardOutput (Join-Path $astrDir 'startup.log') `
            -RedirectStandardError (Join-Path $astrDir 'startup-error.log')
        Write-StartupLog ('已启动聊天程序（PID {0}）。' -f $proc.Id)
    }
    catch {
        Add-Problem ('聊天程序启动失败：' + $_.Exception.Message)
    }
}

# ── QQ 音乐后端 ──────────────────────────────────────────────
function Start-QQMusicBackend {
    $backend = Join-Path $baseDir 'backend\qqmusic'
    $server = Join-Path $backend 'server.mjs'
    if (-not (Test-Path $server)) {
        Write-StartupLog '未找到 QQ 音乐后端，跳过（不影响聊天）。'
        return
    }
    if (Test-Listening 3311) {
        Write-StartupLog 'QQ 音乐后端已经在监听 3311，跳过启动。'
        return
    }
    $node = $null
    if (Test-Path $nodeExe) { $node = $nodeExe }
    else {
        $found = Get-Command node.exe -ErrorAction SilentlyContinue
        if ($found) { $node = $found.Source }
    }
    if (-not $node) {
        Write-StartupLog '未找到 node.exe，点歌后端没有启动（不影响聊天）。'
        return
    }
    try {
        $proc = Start-HiddenProcess -FilePath $node -ArgumentList @('server.mjs') `
            -WorkingDirectory $backend `
            -RedirectStandardOutput (Join-Path $backend 'server.log') `
            -RedirectStandardError (Join-Path $backend 'server-error.log')
        Write-StartupLog ('已启动 QQ 音乐后端（PID {0}）。' -f $proc.Id)
    }
    catch {
        Write-StartupLog ('QQ 音乐后端启动失败（不影响聊天）：' + $_.Exception.Message)
    }
}

# ── NapCat / QQ ──────────────────────────────────────────────
function Start-NapCat {
    if (Test-Listening 6099) {
        Write-StartupLog 'QQ 接入已经在监听 6099，跳过启动。'
        return
    }
    if (-not $qqPath) {
        Add-Problem ('找不到 QQ。请先安装 runtime\installer\QQ_9.9.36_260924_x64_01.exe，或参考 docs\CONFIGURATION.md 写 scripts\paths.local.ps1')
        return
    }
    if ($qqVersion -and ($qqVersion -notmatch '^9\.9\.36')) {
        Add-Problem ("QQ 版本是 $qqVersion，NapCat 只支持 9.9.36。请卸载新版 QQ，再安装 runtime\installer\QQ_9.9.36_260924_x64_01.exe")
        return
    }

    $chunkFile = Join-Path $napDir 'conout-wiJ7YKRd.js'
    if (-not (Test-Path -LiteralPath $chunkFile)) {
        Add-Problem '缺少 NapCat chunk：runtime\napcat-shell\conout-wiJ7YKRd.js，QQ 会卡在注入阶段。请用最新修复补丁补上。'
        return
    }

    $napExe = Join-Path $napDir 'NapCatWinBootMain.exe'
    $hookDll = Join-Path $napDir 'NapCatWinBootHook.dll'
    if (-not (Test-Path $napExe) -or -not (Test-Path $hookDll)) {
        Add-Problem ('找不到 QQ 接入组件：' + $napDir)
        return
    }

    # NapCat 要由它自己拉起一个新的 QQ；已有普通 QQ 在跑时先收掉。
    $staleNapCat = @(Get-Process NapCatWinBootMain -ErrorAction SilentlyContinue)
    if ($staleNapCat.Count -gt 0) {
        Write-StartupLog ('发现 {0} 个残留 QQ 接入进程，先清理。' -f $staleNapCat.Count)
        $staleNapCat | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 800
    }

    $qqProcesses = @(Get-Process QQ -ErrorAction SilentlyContinue)
    if ($qqProcesses.Count -gt 0) {
        Write-StartupLog ('发现 QQ 已在运行（{0} 个进程），先关闭，交给 NapCat 重新拉起。' -f $qqProcesses.Count)
        $qqProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
        $qqDeadline = (Get-Date).AddSeconds(10)
        while ((Get-Date) -lt $qqDeadline -and @(Get-Process QQ -ErrorAction SilentlyContinue).Count -gt 0) {
            Start-Sleep -Milliseconds 500
        }
        if (@(Get-Process QQ -ErrorAction SilentlyContinue).Count -gt 0) {
            Add-Problem 'QQ 正在运行且无法关闭，QQ 接入没有启动。请手动退出 QQ 后重新启动。'
            return
        }
    }

    $env:NAPCAT_PATCH_PACKAGE = Join-Path $napDir 'qqnt.json'
    $env:NAPCAT_LOAD_PATH = Join-Path $napDir 'loadNapCat.js'
    $env:NAPCAT_INJECT_PATH = $hookDll
    $env:NAPCAT_LAUNCHER_PATH = $napExe
    $env:NAPCAT_MAIN_PATH = Join-Path $napDir 'napcat.mjs'
    $napArgs = @((Quote-PathArg $qqPath), (Quote-PathArg $hookDll), '-q', $botQQ)

    if ($isAdmin) {
        try {
            $proc = Start-HiddenProcess -FilePath $napExe -ArgumentList $napArgs `
                -WorkingDirectory $napDir `
                -RedirectStandardOutput (Join-Path $napDir 'startup.log') `
                -RedirectStandardError (Join-Path $napDir 'startup-error.log')
            Write-StartupLog ('已启动 QQ 接入（PID {0}，管理员）。' -f $proc.Id)
        }
        catch {
            Add-Problem ('QQ 接入启动失败：' + $_.Exception.Message)
        }
        return
    }

    $inner = @"
`$n = '$napDir'
`$env:NAPCAT_PATCH_PACKAGE = "`$n\qqnt.json"
`$env:NAPCAT_LOAD_PATH = "`$n\loadNapCat.js"
`$env:NAPCAT_INJECT_PATH = "`$n\NapCatWinBootHook.dll"
`$env:NAPCAT_LAUNCHER_PATH = "`$n\NapCatWinBootMain.exe"
`$env:NAPCAT_MAIN_PATH = "`$n\napcat.mjs"
`$qq = '$qqPath'
`$hook = "`$n\NapCatWinBootHook.dll"
Start-Process -FilePath "`$n\NapCatWinBootMain.exe" -ArgumentList @('"' + `$qq + '"', '"' + `$hook + '"', '-q', '$botQQ') -WorkingDirectory `$n -WindowStyle Hidden -RedirectStandardOutput "`$n\startup.log" -RedirectStandardError "`$n\startup-error.log"
"@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($inner))
    try {
        Start-Process powershell.exe -Verb RunAs `
            -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded) `
            -ErrorAction Stop | Out-Null
        Write-StartupLog '已请求管理员权限启动 QQ 接入（会弹一次 UAC）。'
    }
    catch {
        Add-Problem '没有获得管理员权限，QQ 接不起来（NapCat 需要管理员）。请右键以管理员身份运行 scripts\start.ps1。'
    }
}

try {
    Start-AstrBot
    Start-QQMusicBackend
    Start-NapCat
}
catch {
    Add-Problem ('启动过程出现异常：' + $_.Exception.Message)
}

if (-not $Nested) {
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline -and -not (Test-AstrConnected)) {
        Start-Sleep -Seconds 3
    }
}

$connected = Test-AstrConnected
Write-StartupLog ('连接状态：{0}；问题数：{1}' -f $connected, $problems.Count)

if ($problems.Count -gt 0) {
    $detail = ($problems | ForEach-Object { '· ' + $_ }) -join "`n"
    if (-not $connected) {
        $message = "大肥鱼没有连上 QQ。`n`n$detail`n`n常见原因：`n1. 还没替换机器人 QQ（现在是 $botQQ）`n2. QQ 没登录（登录窗口里扫 $botQQ 的码）`n3. 没点 UAC 的[是]（NapCat 需要管理员）`n`n处理后可以点托盘里的「启动上线」，或重新运行 scripts\start.ps1。"
    }
    else {
        $message = "大肥鱼已经上线，但以下组件没有正常启动：`n`n$detail`n`n聊天本身不受影响；需要时可以重新运行 scripts\start.ps1。"
    }
    Show-Alert $message
}

if (-not $connected -and -not $Nested) {
    Write-StartupLog '启动结束：未连接。'
    exit 1
}

Write-StartupLog '启动结束：成功。'
exit 0
