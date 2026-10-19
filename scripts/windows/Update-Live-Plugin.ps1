param(
    [string]$SdkRoot = 'D:\QAROS-0.9.0-dev.2540+1ed038e4',
    [string]$RepoRoot = (Join-Path $PSScriptRoot '..\..'),
    [string]$ArchivePath = ''
)
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$expectedSdk = 'c709c479cc6a1acc0040fb61a071cc7bc16e65bf5acb90d624d9d6b0a6fcd3c1'
$destination = Join-Path $RepoRoot 'package\windows-start'
$archive = if ($ArchivePath) { $ArchivePath } else { Join-Path $RepoRoot 'downloads\qarvtk-live-dev2540.zip' }

if (Get-Process -Name 'Slicer', 'SlicerApp-real' -ErrorAction SilentlyContinue) {
    throw 'Close Slicer before updating its plugin.'
}
foreach ($name in @('include\qar_streaming.h', 'bin\qar-streaming-c.dll', 'bin\qar-runtime-launcher.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $SdkRoot $name) -PathType Leaf)) {
        throw "Incomplete QAROS package: $SdkRoot\$name is missing. Select the SDK root containing include and bin."
    }
}
if ((Get-FileHash -LiteralPath (Join-Path $SdkRoot 'include\qar_streaming.h') -Algorithm SHA256).Hash -ine $expectedSdk) {
    throw 'This update requires the supplied dev.2540 SDK header c709c479. Do not replace individual SDK files.'
}
if (-not (Test-Path -LiteralPath (Join-Path $destination 'plugins\slicer\QarosLive.py') -PathType Leaf)) {
    throw 'Existing package/windows-start plugin is missing. Run START-PREVIEW.cmd once, close the preview, then rerun this updater.'
}
$expected = (Get-Content -LiteralPath ($archive + '.sha256') -Raw).Trim().Split(' ')[0]
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ine $expected) {
    throw 'Live plugin archive checksum mismatch. Pull the complete update from GitHub.'
}

$stamp = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
$staging = Join-Path $RepoRoot "package\live-update-$stamp"
$backup = Join-Path $RepoRoot "package\live-backup-$stamp"
$files = @(
    'Release/qarvtk-host.dll',
    'plugins/slicer/QarosLive.py',
    'plugins/slicer/QarosVTKLib/__init__.py',
    'plugins/slicer/QarosVTKLib/qarvtk_host_runtime.py',
    'plugins/slicer/QarosVTKLib/qarvtk_host_view.py',
    'plugins/slicer/QarosVTKLib/qarvtk_host_gpu.py',
    'plugins/slicer/QarosVTKLib/qarvtk_host_panels.py',
    'plugins/slicer/QarosVTKLib/qarvtk_host_diagnostics.py',
    'plugins/slicer/QarosVTKLib/qarvtk_runtime.py',
    'HOST_UPDATE_INFO.json'
)
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($archive)
try {
    $names = @($zip.Entries | ForEach-Object { $_.FullName })
    if ($names.Count -ne $files.Count -or @($names | Select-Object -Unique).Count -ne $files.Count) {
        throw 'Unexpected or duplicate files in update archive.'
    }
    foreach ($name in $names) {
        if ($name -cnotin $files) { throw "Unexpected update path: $name" }
    }
} finally { $zip.Dispose() }

Expand-Archive -LiteralPath $archive -DestinationPath $staging
$info = Get-Content -LiteralPath (Join-Path $staging 'HOST_UPDATE_INFO.json') -Raw | ConvertFrom-Json
if ($info.sdk_header_sha256 -ne $expectedSdk -or $info.host_abi -ne 5) {
    throw 'Archive SDK or ABI metadata differs from this updater.'
}
foreach ($relative in $files) {
    if ($relative -eq 'HOST_UPDATE_INFO.json') { continue }
    $hash = (Get-FileHash -LiteralPath (Join-Path $staging $relative) -Algorithm SHA256).Hash
    if ($hash -ine $info.files.$relative) { throw "Payload checksum mismatch: $relative" }
}

# Back up every file before replacing any. Restore the previous set on failure.
$existing = @{}
foreach ($relative in $files) {
    $target = Join-Path $destination $relative
    $existing[$relative] = Test-Path -LiteralPath $target -PathType Leaf
    if ($existing[$relative]) {
        $saved = Join-Path $backup $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $saved) | Out-Null
        Copy-Item -LiteralPath $target -Destination $saved
    }
}
try {
    foreach ($relative in $files) {
        $target = Join-Path $destination $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath (Join-Path $staging $relative) -Destination $target -Force
    }
} catch {
    $failure = $_
    foreach ($relative in $files) {
        $target = Join-Path $destination $relative
        if ($existing[$relative]) {
            Copy-Item -LiteralPath (Join-Path $backup $relative) -Destination $target -Force
        } elseif (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target
        }
    }
    throw $failure
}
Remove-Item -LiteralPath $staging -Recurse
Write-Host 'QAROS Live Renderer updated for 0.9.0-dev.2540+1ed038e4 (ABI 5).'
Write-Host "Previous plugin saved to: $backup"
Write-Host "Open Slicer, QAROS Live Renderer. SDK folder: $SdkRoot"
Write-Host 'Separate workspaces and read-only slice panels are included. Start live streaming.'
Write-Host 'START-PREVIEW.cmd restores the old r17 package; use this updater again afterwards.'
