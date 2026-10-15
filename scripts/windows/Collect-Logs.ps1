param(
    [string]$SdkRoot = 'D:\install',
    [string]$OutputRoot = '',
    [switch]$NoOpen
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $OutputRoot) { $OutputRoot = Join-Path $repoRoot 'diagnostics' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$folder = Join-Path $OutputRoot ("QAROS-VTK-diagnostics-" + $stamp)
$archive = $folder + '.zip'
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$notes = New-Object 'System.Collections.Generic.List[string]'
$notes.Add('Collected at: ' + (Get-Date -Format o))
$notes.Add('PowerShell: ' + $PSVersionTable.PSVersion.ToString())
$notes.Add('This collector does not launch, stop or modify the sender or viewer.')
$notes.Add('Only sender/live-host logs, installed build metadata and related crash events are collected.')

# Each Slicer/ParaView plugin instance has a separate qarvtk-* directory.
# Copy only sender.log, never scene.vtp, invites or onboarding identities.
$logs = @(Get-ChildItem -LiteralPath ([IO.Path]::GetTempPath()) -Directory -Filter 'qarvtk-*' |
    ForEach-Object {
        $path = Join-Path $_.FullName 'sender.log'
        if (Test-Path -LiteralPath $path -PathType Leaf) { Get-Item -LiteralPath $path }
    } | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 3)
$index = 0
foreach ($log in $logs) {
    $index++
    $target = Join-Path $folder ("sender-" + $index + '.log')
    $notes.Add(('sender-{0}.log: {1}; modified {2:o}; {3} bytes' -f $index, $log.FullName, $log.LastWriteTime, $log.Length))
    try {
        if ($log.Length -le 25MB) {
            Copy-Item -LiteralPath $log.FullName -Destination $target
        } else {
            $notes.Add("sender-$index.log was over 25 MiB: included first 100 and last 10000 lines.")
            Get-Content -LiteralPath $log.FullName -Encoding UTF8 -TotalCount 100 | Set-Content -LiteralPath $target -Encoding UTF8
            '--- LARGE LOG: middle omitted by collector ---' | Add-Content -LiteralPath $target -Encoding UTF8
            Get-Content -LiteralPath $log.FullName -Encoding UTF8 -Tail 10000 | Add-Content -LiteralPath $target -Encoding UTF8
        }
    } catch { $notes.Add("Cannot read sender log: $_") }
}
if ($logs.Count -eq 0) { $notes.Add('No sender.log found in qarvtk-* temporary folders.') }

$liveRoot = Join-Path $env:LOCALAPPDATA 'QAROS_VTK\live-logs'
if (Test-Path -LiteralPath $liveRoot -PathType Container) {
    $liveLogs = @(Get-ChildItem -LiteralPath $liveRoot -Directory |
        ForEach-Object {
            $path = Join-Path $_.FullName 'host-bridge.log'
            if (Test-Path -LiteralPath $path -PathType Leaf) { Get-Item -LiteralPath $path }
        } | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 3)
    $liveIndex = 0
    foreach ($log in $liveLogs) {
        $liveIndex++
        $target = Join-Path $folder ("host-bridge-" + $liveIndex + '.log')
        $notes.Add(('host-bridge-{0}.log: {1}; modified {2:o}; {3} bytes' -f $liveIndex, $log.FullName, $log.LastWriteTime, $log.Length))
        try {
            Get-Content -LiteralPath $log.FullName -Encoding UTF8 -Tail 10000 |
                Set-Content -LiteralPath $target -Encoding UTF8
        } catch { $notes.Add("Cannot read host bridge log: $_") }
        $pythonLog = Join-Path $log.DirectoryName 'host-python.log'
        if (Test-Path -LiteralPath $pythonLog -PathType Leaf) {
            try {
                Get-Content -LiteralPath $pythonLog -Encoding UTF8 -Tail 10000 |
                    Set-Content -LiteralPath (Join-Path $folder ("host-python-" + $liveIndex + '.log')) -Encoding UTF8
            } catch { $notes.Add("Cannot read live Python log: $_") }
        }
    }
}

$install = Join-Path $repoRoot 'package\windows-start'
foreach ($name in @('BUILD_INFO.json', 'qarvtk-sdk.json')) {
    $path = Join-Path $install $name
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        Copy-Item -LiteralPath $path -Destination (Join-Path $folder $name)
    }
}
foreach ($path in @((Join-Path $install 'Release\qarvtk-sender.exe'), (Join-Path $install 'Release\qarvtk-host.dll'), (Join-Path $SdkRoot 'include\qar_streaming.h'))) {
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        try {
            $hash = Get-FileHash -LiteralPath $path -Algorithm SHA256
            $notes.Add('SHA256 ' + $hash.Hash + '  ' + $path)
        } catch { $notes.Add("Cannot hash file: $_") }
    } else { $notes.Add('Missing file: ' + $path) }
}

# Windows Application Error / WER / .NET crash records can identify the failing
# executable and faulting module even if its own log ends without an error.
$processPattern = '(?i)(qar[^\s<>]*\.exe|visuali[sz]er[^\s<>]*\.exe|slicer(?:app-real)?\.exe)'
try {
    $events = @(Get-WinEvent -FilterHashtable @{
        LogName = 'Application'; Id = @(1000, 1001, 1026); StartTime = (Get-Date).AddHours(-2)
    } -MaxEvents 500 -ErrorAction Stop | Where-Object {
        $_.ToXml() -match $processPattern
    } | Select-Object -First 20)
    if ($events.Count -gt 0) {
        $events | Select-Object TimeCreated, Id, ProviderName, Message |
            Format-List | Out-String -Width 4096 |
            Set-Content -LiteralPath (Join-Path $folder 'windows-crashes.txt') -Encoding UTF8
        $events | ForEach-Object { $_.ToXml() } |
            Set-Content -LiteralPath (Join-Path $folder 'windows-crashes-raw.txt') -Encoding UTF8
        $notes.Add('Related Windows crash records: ' + $events.Count)
    } else { $notes.Add('No related Windows crash records found in the last two hours.') }
} catch { $notes.Add("Windows crash records unavailable or no events found: $_") }

try {
    $processes = @(Get-Process | Where-Object {
        $_.ProcessName -match '(?i)(^qar|visuali[sz]er|^slicer)'
    } | Select-Object ProcessName, Id, Path)
    $processes | Format-Table -AutoSize | Out-String -Width 4096 |
        Set-Content -LiteralPath (Join-Path $folder 'running-processes.txt') -Encoding UTF8
} catch { $notes.Add("Cannot list related running processes: $_") }

$notes | Set-Content -LiteralPath (Join-Path $folder 'collection-info.txt') -Encoding UTF8
Compress-Archive -Path (Join-Path $folder '*') -DestinationPath $archive
Write-Host ''
Write-Host ('Created: ' + $archive)
Write-Host ('Sender logs found: ' + $logs.Count)
if (-not $NoOpen) {
    Start-Process explorer.exe -ArgumentList ('/select,"' + $archive + '"')
}
