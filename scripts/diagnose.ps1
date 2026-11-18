# 大肥鱼 2.0 · 一键诊断
# 整理：YunShan_You（悠云山）
# 生成 诊断报告.txt，不改动任何配置。
param([switch]$NoOpen)

$ErrorActionPreference = 'Continue'
$baseDir = Split-Path $PSScriptRoot -Parent
$report = Join-Path $baseDir '诊断报告.txt'
$lines = New-Object System.Collections.Generic.List[string]

function Add-Line {
    param([string]$Text)
    $script:lines.Add([string]$Text)
}

function Add-Section {
    param([string]$Title)
    Add-Line ''
    Add-Line ('===== ' + $Title + ' =====')
}

function Add-Tail {
    param([string]$Path, [int]$Count = 30)
    Add-Section ('日志：' + $Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        Add-Line '（文件不存在）'
        return
    }
    try {
        Get-Content -LiteralPath $Path -Encoding UTF8 -Tail $Count | ForEach-Object { Add-Line $_ }
    }
    catch {
        Add-Line ('读取失败：' + $_.Exception.Message)
    }
}

function Add-FileState {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        try {
            $item = Get-Item -LiteralPath $Path
            Add-Line ('OK   ' + $Path + '  (' + $item.Length + ' bytes)')
        }
        catch {
            Add-Line ('OK   ' + $Path)
        }
    }
    else {
        Add-Line ('MISS ' + $Path)
    }
}

try {
    Add-Line '大肥鱼 2.0 · 诊断报告'
    Add-Line ('生成时间：' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
    Add-Line ('整理：YunShan_You（悠云山）')
    Add-Line ('包目录：' + $baseDir)

    Add-Section '系统'
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        Add-Line ('操作系统：' + $os.Caption + ' ' + $os.Version + ' (' + $os.OSArchitecture + ')')
    }
    catch {
        Add-Line ('操作系统：' + [System.Environment]::OSVersion.VersionString)
    }
    Add-Line ('64 位系统：' + [System.Environment]::Is64BitOperatingSystem)
    Add-Line ('PowerShell：' + $PSVersionTable.PSVersion.ToString() + ' / ' + $PSVersionTable.PSEdition)
    try {
        Add-Line ('执行策略：' + (Get-ExecutionPolicy))
    }
    catch {
        Add-Line '执行策略：读取失败'
    }
    $isAdmin = [Security.Principal.WindowsPrincipal]::new(
        [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    Add-Line ('管理员：' + $isAdmin)

    Add-Section '路径'
    Add-Line ('路径长度：' + $baseDir.Length)
    Add-Line ('路径含空格：' + [bool]($baseDir -match ' '))
    Add-Line ('路径含中文：' + [bool]($baseDir -match '[\u4e00-\u9fff]'))
    Add-Line ('当前目录：' + (Get-Location))

    Add-Section '目录写权限'
    foreach ($rel in @('scripts', 'runtime\logs', 'data')) {
        $folder = Join-Path $baseDir $rel
        try {
            if (-not (Test-Path -LiteralPath $folder)) { New-Item -ItemType Directory -Path $folder -Force -ErrorAction Stop | Out-Null }
            $probe = Join-Path $folder ('.write_test_' + [guid]::NewGuid().ToString('N'))
            Set-Content -LiteralPath $probe -Value 'ok' -ErrorAction Stop
            Remove-Item -LiteralPath $probe -Force -ErrorAction Stop
            Add-Line ('可写  ' + $rel)
        }
        catch {
            Add-Line ('只读/不可写  ' + $rel + '  ' + $_.Exception.Message)
        }
    }

    Add-Section '关键文件'
    foreach ($rel in @(
        'runtime\python\python.exe',
        'runtime\python\pythonw.exe',
        'runtime\AstrBot-4.29.3\main.py',
        'runtime\AstrBot-4.29.3\data\cmd_config.json',
        'scripts\start.ps1',
        'scripts\status.pyw',
        'scripts\stop.ps1',
        'scripts\backup.py',
        'runtime\napcat-shell\NapCatWinBootMain.exe',
        'runtime\napcat-shell\NapCatWinBootHook.dll',
        'runtime\napcat-shell\conout-wiJ7YKRd.js',
        'runtime\napcat-shell\napcat.mjs',
        'runtime\bin\node.exe',
        'runtime\bin\ffmpeg.exe',
        'runtime\installer\QQ_9.9.36_260924_x64_01.exe'
    )) {
        Add-FileState (Join-Path $baseDir $rel)
    }

    Add-Section '下载锁定（Zone.Identifier）'
    foreach ($rel in @('scripts\start.ps1', 'runtime\python\python.exe',
                       'runtime\napcat-shell\NapCatWinBootHook.dll',
                       'runtime\installer\QQ_9.9.36_260924_x64_01.exe')) {
        $path = Join-Path $baseDir $rel
        if (-not (Test-Path -LiteralPath $path)) { continue }
        try {
            Get-Item -LiteralPath $path -Stream Zone.Identifier -ErrorAction Stop | Out-Null
            Add-Line ('BLOCKED ' + $rel)
        }
        catch {
            Add-Line ('ok      ' + $rel)
        }
    }

    Add-Section '运行时版本'
    $python = Join-Path $baseDir 'runtime\python\python.exe'
    if (Test-Path -LiteralPath $python) {
        try { Add-Line ('Python：' + ((& $python --version 2>&1) | Out-String).Trim()) }
        catch { Add-Line ('Python 运行失败：' + $_.Exception.Message) }
    }
    $node = Join-Path $baseDir 'runtime\bin\node.exe'
    if (Test-Path -LiteralPath $node) {
        try { Add-Line ('Node：' + ((& $node -v 2>&1) | Out-String).Trim()) }
        catch { Add-Line ('Node 运行失败：' + $_.Exception.Message) }
    }
    $ffmpeg = Join-Path $baseDir 'runtime\bin\ffmpeg.exe'
    if (Test-Path -LiteralPath $ffmpeg) {
        try {
            $first = (& $ffmpeg -version 2>&1 | Select-Object -First 1)
            Add-Line ('ffmpeg：' + $first)
        }
        catch { Add-Line ('ffmpeg 运行失败：' + $_.Exception.Message) }
    }

    Add-Section 'QQ'
    $qqPath = $null
    foreach ($key in @(
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\QQ',
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\QQ'
    )) {
        try {
            $uninstall = (Get-ItemProperty -Path $key -Name UninstallString -ErrorAction Stop).UninstallString
            $dir = Split-Path ($uninstall -replace '"', '') -Parent
            $candidate = Join-Path $dir 'QQ.exe'
            if (Test-Path $candidate) { $qqPath = $candidate; break }
        }
        catch {
        }
    }
    if (-not $qqPath) {
        foreach ($candidate in @(
            'C:\Program Files\Tencent\QQNT\QQ.exe',
            'D:\Program Files\Tencent\QQNT\QQ.exe',
            'C:\QQ\QQ.exe',
            'D:\QQ\QQ.exe'
        )) {
            if (Test-Path $candidate) { $qqPath = $candidate; break }
        }
    }
    if (-not $qqPath) {
        $running = Get-Process QQ -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($running -and $running.Path) { $qqPath = $running.Path }
    }
    Add-Line ('QQ 路径：' + $(if ($qqPath) { $qqPath } else { '没找到' }))
    try {
        $version = (Get-ItemProperty -Path 'HKCU:\Software\Tencent\QQNT' -Name version -ErrorAction Stop).version
        Add-Line ('QQ 版本：' + $version)
        Add-Line ('版本符合 9.9.36：' + [bool]($version -match '^9\.9\.36'))
    }
    catch {
        Add-Line ('QQ 版本：读不到（可能还没登录过 QQ）')
    }

    Add-Section '端口'
    try {
        $ports = Get-NetTCPConnection -ErrorAction Stop | Where-Object {
            $_.LocalPort -in 6185, 6099, 6199, 3311
        } | Sort-Object LocalPort, State
        if ($ports) {
            $ports | ForEach-Object { Add-Line ('{0}  {1}  PID {2}' -f $_.LocalPort, $_.State, $_.OwningProcess) }
        }
        else {
            Add-Line '6185 / 6099 / 6199 / 3311 都没有连接'
        }
    }
    catch {
        Add-Line ('端口检查失败：' + $_.Exception.Message)
    }

    Add-Section '相关进程'
    try {
        $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe' OR Name='NapCatWinBootMain.exe' OR Name='QQ.exe'" -ErrorAction Stop
        if ($procs) {
            foreach ($p in $procs) {
                $cmd = [string]$p.CommandLine
                if ($cmd.Length -gt 220) { $cmd = $cmd.Substring(0, 220) + '...' }
                Add-Line ('PID ' + $p.ProcessId + '  ' + $p.Name + '  ' + $cmd)
            }
        }
        else {
            Add-Line '没有相关进程'
        }
    }
    catch {
        Add-Line ('进程检查失败：' + $_.Exception.Message)
    }

    Add-Section '启动脚本自检（-CheckOnly）'
    try {
        $check = & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'start.ps1') -CheckOnly 2>&1 | Out-String
        $check.Trim().Split("`n") | ForEach-Object { Add-Line $_.TrimEnd() }
    }
    catch {
        Add-Line ('自检失败：' + $_.Exception.Message)
    }

    Add-Tail (Join-Path $baseDir 'runtime\logs\launcher.log') 40
    Add-Tail (Join-Path $baseDir 'runtime\logs\启动.log') 40
    Add-Tail (Join-Path $baseDir 'runtime\logs\control_center_error.log') 30
    Add-Tail (Join-Path $baseDir 'runtime\AstrBot-4.29.3\startup.log') 60
    Add-Tail (Join-Path $baseDir 'runtime\AstrBot-4.29.3\startup-error.log') 30
    Add-Tail (Join-Path $baseDir 'runtime\napcat-shell\startup.log') 60
    Add-Tail (Join-Path $baseDir 'runtime\napcat-shell\startup-error.log') 30

    Add-Section '说明'
    Add-Line '报告只包含本机路径、版本和日志，不读取 cmd_config.json 里的 API Key。'
    Add-Line '如果日志里出现你自己的 Key、QQ 号，发之前可以手动删掉。'
}
catch {
    Add-Line ''
    Add-Line ('诊断脚本异常：' + $_.Exception.Message)
    Add-Line $_.ScriptStackTrace
}

try {
    [System.IO.File]::WriteAllLines($report, $lines, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host ''
    Write-Host ('诊断报告已生成：' + $report)
    if (-not $NoOpen) {
        Start-Process -FilePath 'notepad.exe' -ArgumentList @(('"' + $report + '"'))
    }
}
catch {
    Write-Host ('报告写入失败：' + $_.Exception.Message)
    exit 1
}
exit 0
