@echo off
setlocal
cd /d "%~dp0"
if not exist "downloads\QAROS_VTK_Windows_session_022c40b6_2026-10-15_r13.zip" (
  echo The Windows starter ZIP is missing. Use Fetch origin and Pull origin in GitHub Desktop.
  pause
  exit /b 1
)
echo Preparing the Windows preview - live Slicer renderer r13...
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { $zip=Join-Path (Get-Location) 'downloads/QAROS_VTK_Windows_session_022c40b6_2026-10-15_r13.zip'; $expected='679deb687d8edc209a11d92082bfa230bf91146ee01e9c062bf5eb90b478f6b6'; if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ine $expected) { throw 'Windows starter checksum mismatch.' }; Expand-Archive -LiteralPath $zip -DestinationPath 'package/windows-start' -Force } catch { Write-Error $_; exit 1 }"
if errorlevel 1 (
  echo Preparing the preview failed. Copy the error above.
  pause
  exit /b 1
)
call "%~dp0package\windows-start\01-Preview.cmd"

