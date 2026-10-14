@echo off
setlocal
cd /d "%~dp0"
if not exist "downloads\QAROS_VTK_Windows_session_022c40b6_2026-10-14_r5.zip" (
  echo The Windows starter ZIP is missing. Use Fetch origin and Pull origin in GitHub Desktop.
  pause
  exit /b 1
)
echo Preparing the Windows preview - initial viewer pose wait r5...
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { $zip=Join-Path (Get-Location) 'downloads/QAROS_VTK_Windows_session_022c40b6_2026-10-14_r5.zip'; $expected='f2136fbaf2a4a677628f569d7c1fe26ccdca8eb8e61dcd67f3e4a51f509757b9'; if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ine $expected) { throw 'Windows starter checksum mismatch.' }; Expand-Archive -LiteralPath $zip -DestinationPath 'package/windows-start' -Force } catch { Write-Error $_; exit 1 }"
if errorlevel 1 (
  echo Preparing the preview failed. Copy the error above.
  pause
  exit /b 1
)
call "%~dp0package\windows-start\01-Preview.cmd"

