# Isolated updater smoke: never touches an installed Slicer or QAROS package.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('qarvtk-update-test-' + [Guid]::NewGuid().ToString('N'))
$sdk = Join-Path $fixture 'QAROS-0.9.0-dev.2540+1ed038e4'
$destination = Join-Path $fixture 'package\windows-start'
$expected = 'c709c479cc6a1acc0040fb61a071cc7bc16e65bf5acb90d624d9d6b0a6fcd3c1'
try {
    foreach ($dir in @('downloads', 'package\windows-start\plugins\slicer',
                       'QAROS-0.9.0-dev.2540+1ed038e4\include', 'QAROS-0.9.0-dev.2540+1ed038e4\bin')) {
        New-Item -ItemType Directory -Force -Path (Join-Path $fixture $dir) | Out-Null
    }
    Copy-Item -LiteralPath (Join-Path $repo 'ci\sdk-headers\session-c709c479\include\qar_streaming.h') -Destination (Join-Path $sdk 'include')
    foreach ($file in @('qar-streaming-c.dll', 'qar-runtime-launcher.exe')) {
        New-Item -ItemType File -Path (Join-Path $sdk "bin\$file") | Out-Null
    }
    foreach ($file in @('qarvtk-live-dev2540.zip', 'qarvtk-live-dev2540.zip.sha256')) {
        Copy-Item -LiteralPath (Join-Path $repo "downloads\$file") -Destination (Join-Path $fixture 'downloads')
    }
    $oldPlugin = Join-Path $destination 'plugins\slicer\QarosLive.py'
    Set-Content -LiteralPath $oldPlugin -Value 'previous-plugin-sentinel'
    & (Join-Path $repo 'scripts\windows\Update-Live-Plugin.ps1') -RepoRoot $fixture -SdkRoot $sdk
    $info = Get-Content -LiteralPath (Join-Path $destination 'HOST_UPDATE_INFO.json') -Raw | ConvertFrom-Json
    foreach ($file in $info.files.PSObject.Properties) {
        if ((Get-FileHash -LiteralPath (Join-Path $destination $file.Name) -Algorithm SHA256).Hash -ine $file.Value) {
            throw "Installed file mismatch: $($file.Name)"
        }
    }
    $backup = @(Get-ChildItem -LiteralPath (Join-Path $fixture 'package') -Directory -Filter 'live-backup-*')
    if ($backup.Count -ne 1 -or (Get-Content -LiteralPath (Join-Path $backup[0].FullName 'plugins\slicer\QarosLive.py') -Raw).Trim() -ne 'previous-plugin-sentinel') {
        throw 'Previous plugin was not backed up.'
    }
    if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
        python (Join-Path $repo 'tests\test_host_abi.py') (Join-Path $destination 'Release\qarvtk-host.dll') $expected
        if ($LASTEXITCODE -ne 0) { throw 'Shipped DLL ABI test failed.' }
    } else {
        Write-Host 'SKIP: native Windows DLL loading (requires Windows).'
    }
    $installedHash = (Get-FileHash -LiteralPath $oldPlugin -Algorithm SHA256).Hash
    Set-Content -LiteralPath (Join-Path $sdk 'include\qar_streaming.h') -Value 'wrong SDK header'
    $rejected = $false
    try { & (Join-Path $repo 'scripts\windows\Update-Live-Plugin.ps1') -RepoRoot $fixture -SdkRoot $sdk }
    catch { $rejected = $_.Exception.Message -like '*requires the supplied dev.2540*' }
    if (-not $rejected -or (Get-FileHash -LiteralPath $oldPlugin -Algorithm SHA256).Hash -ne $installedHash) {
        throw 'Incompatible SDK was not rejected before modifying the plugin.'
    }
    Write-Host 'PASS: updater payload, backup and rejection of mismatched SDK.'
} finally {
    # ctypes loaded the shipped DLL in a child Python process, which has exited.
    if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture -Recurse -Force }
}
