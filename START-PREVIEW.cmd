@echo off
setlocal
cd /d "%~dp0"
if not exist "downloads\QAROS_VTK_Windows_session_022c40b6_2026-10-14.zip" (
  echo The Windows starter ZIP is missing. Use Fetch origin and Pull origin in GitHub Desktop.
  pause
  exit /b 1
)
echo Preparing the Windows preview...
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { $zip=Join-Path (Get-Location) 'downloads/QAROS_VTK_Windows_session_022c40b6_2026-10-14.zip'; $expected='4daf48fd135bc9c57424f2273bceeab9d1bd19a736c0d476cb2c9a37e3b8d7c5'; if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ine $expected) { throw 'Windows starter checksum mismatch.' }; Expand-Archive -LiteralPath $zip -DestinationPath 'package/windows-start' -Force } catch { Write-Error $_; exit 1 }"
if errorlevel 1 (
  echo Preparing the preview failed. Copy the error above.
  pause
  exit /b 1
)
call "%~dp0package\windows-start\01-Preview.cmd"

