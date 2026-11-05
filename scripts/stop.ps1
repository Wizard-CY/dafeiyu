# 大肥鱼结束下线 · packaged by YunShan You
﻿param([switch]$NoBackup)

$isAdmin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath)
    return
}

$baseDir = Split-Path $PSScriptRoot -Parent
$py = Join-Path $baseDir 'runtime\AstrBot-4.29.3\.venv\Scripts\python.exe'
$backup = Join-Path $PSScriptRoot 'backup.py'
$log = Join-Path $baseDir 'runtime\下线上次记录.txt'

# 下线前先让聊天程序提炼一次记忆，最多等 45 秒
$memoryFlag = Join-Path $baseDir 'runtime\AstrBot-4.29.3\data\dafeiyu_memory.flag'
$memoryState = Join-Path $baseDir 'runtime\AstrBot-4.29.3\data\dafeiyu_memory_state.json'
try {
    if (Get-NetTCPConnection -State Listen -LocalPort 6185 -ErrorAction SilentlyContinue) {
        $before = ''
        $beforeStamp = [datetime]::MinValue
        if (Test-Path $memoryState) {
            try { $before = (Get-Content $memoryState -Raw -Encoding UTF8 | ConvertFrom-Json).last_run } catch { }
            try { $beforeStamp = (Get-Item $memoryState).LastWriteTimeUtc } catch { }
        }
        Set-Content -Path $memoryFlag -Value 'manual' -Encoding UTF8
        $deadline = (Get-Date).AddSeconds(90)
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 2
            $after = ''
            $afterStamp = [datetime]::MinValue
            if (Test-Path $memoryState) {
                try { $after = (Get-Content $memoryState -Raw -Encoding UTF8 | ConvertFrom-Json).last_run } catch { }
                try { $afterStamp = (Get-Item $memoryState).LastWriteTimeUtc } catch { }
            }
            if (-not (Test-Path $memoryFlag) -and ($after -ne $before -or $afterStamp -gt $beforeStamp)) { break }
        }
    }
} catch { }

if (-not $NoBackup) {
    try {
        & $py $backup | Out-Null
        $backupResult = '已备份'
    }
    catch {
        $backupResult = '备份失败'
    }
}
else {
    $backupResult = '跳过备份'
}

for ($round = 0; $round -lt 5; $round++) {
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.CommandLine -and $_.CommandLine -match 'AstrBot-4\.29\.3.*main\.py') {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    Get-Process NapCatWinBootMain, QQ -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 3
    $portOpen = Get-NetTCPConnection -State Listen -LocalPort 6185, 6099 -ErrorAction SilentlyContinue
    $qqLeft = @(Get-Process QQ -ErrorAction SilentlyContinue)
    if (-not $portOpen -and $qqLeft.Count -eq 0) { break }
}

$astr = [bool](Get-NetTCPConnection -State Listen -LocalPort 6185 -ErrorAction SilentlyContinue)
$nap = [bool](Get-NetTCPConnection -State Listen -LocalPort 6099 -ErrorAction SilentlyContinue)
$qq = @(Get-Process QQ -ErrorAction SilentlyContinue).Count
$state = "聊天程序:$([int]$astr) NapCat:$([int]$nap) QQ进程:$qq"
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
"$stamp 下线；$backupResult；$state" | Out-File -FilePath $log -Encoding utf8 -Append
Write-Output "$stamp $backupResult $state"

# 停掉 QQ 音乐后端
$backend = Get-NetTCPConnection -State Listen -LocalPort 3311 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid in $backend) { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue }
