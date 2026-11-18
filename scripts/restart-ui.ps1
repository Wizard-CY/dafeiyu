# 大肥鱼 2.0 · 重启控制中心（托盘卡死时用）
# 整理：YunShan_You（悠云山）
param([switch]$Nested)

$ErrorActionPreference = 'Continue'
$baseDir = Split-Path $PSScriptRoot -Parent
$statusScript = Join-Path $baseDir 'scripts\status.pyw'
$pythonw = Join-Path $baseDir 'runtime\python\pythonw.exe'
$logDir = Join-Path $baseDir 'runtime\logs'
$logPath = Join-Path $logDir '重启控制中心.log'
$env:PYTHONIOENCODING = 'utf-8'

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Write-RestartLog {
    param([string]$Text)
    try {
        if ((Test-Path $logPath) -and ((Get-Item $logPath).Length -gt 256KB)) {
            Move-Item -LiteralPath $logPath -Destination ($logPath + '.old') -Force -ErrorAction SilentlyContinue
        }
        Add-Content -LiteralPath $logPath -Value ('{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Text) -Encoding UTF8
    }
    catch {
    }
}

function Show-Alert {
    param([string]$Text)
    if ($Nested) { return }
    try {
        $shell = New-Object -ComObject WScript.Shell -ErrorAction Stop
        $shell.Popup($Text, 0, '大肥鱼 · 重启控制中心', 48) | Out-Null
        return
    }
    catch {
    }
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        [System.Windows.Forms.MessageBox]::Show($Text, '大肥鱼 · 重启控制中心',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
    }
    catch {
    }
}

if (-not (Test-Path $statusScript) -or -not (Test-Path $pythonw)) {
    Write-RestartLog '找不到控制中心或 pythonw。'
    Show-Alert ('找不到控制中心或 pythonw：' + $statusScript)
    exit 1
}

Write-RestartLog '========== 重启控制中心 =========='
$isAdmin = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$rows = @(
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match 'status\.pyw' }
)
Write-RestartLog ('发现 {0} 个控制中心进程。' -f $rows.Count)
$failed = 0
foreach ($row in $rows) {
    try {
        Stop-Process -Id $row.ProcessId -Force -ErrorAction Stop
        Write-RestartLog ('已结束 PID {0}。' -f $row.ProcessId)
    }
    catch {
        $failed++
        Write-RestartLog ('结束 PID {0} 失败：{1}' -f $row.ProcessId, $_.Exception.Message)
    }
}
if ($failed -gt 0 -and -not $isAdmin) {
    Write-RestartLog '权限不足，请求管理员权限后重试。'
    Start-Process powershell.exe -Verb RunAs -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'), '-Nested'
    )
    exit 0
}
Start-Sleep -Milliseconds 900

try {
    $proc = Start-Process -FilePath $pythonw -ArgumentList @(('"' + $statusScript + '"')) -WindowStyle Hidden -PassThru
    Write-RestartLog ('已启动控制中心（PID {0}）。' -f $proc.Id)
}
catch {
    Write-RestartLog ('启动失败：' + $_.Exception.Message)
    Show-Alert ('控制中心启动失败：' + $_.Exception.Message)
    exit 1
}

Start-Sleep -Seconds 3
$ok = $false
try {
    $probe = Start-Process -FilePath $pythonw -ArgumentList @(('"' + $statusScript + '"'), '--probe') -WindowStyle Hidden -PassThru -Wait
    $ok = ($probe.ExitCode -eq 0)
}
catch {
    $ok = $false
}

if (-not $ok) {
    Write-RestartLog '重启后没有响应。'
    Show-Alert "控制中心重启后没有响应。`n`n请看 runtime\logs\control_center_error.log，或运行 scripts\start.ps1。"
    exit 1
}

try {
    Start-Process -FilePath $pythonw -ArgumentList @(('"' + $statusScript + '"'), '--show') -WindowStyle Hidden | Out-Null
}
catch {
}

Write-RestartLog '重启结束：控制中心正常响应。'
exit 0
