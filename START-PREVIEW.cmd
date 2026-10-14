@echo off
setlocal
cd /d "%~dp0"
if not exist "downloads\QAROS_VTK_Windows_session_022c40b6_2026-10-14_r9.zip" (
  echo The Windows starter ZIP is missing. Use Fetch origin and Pull origin in GitHub Desktop.
  pause
  exit /b 1
)
echo Preparing the Windows preview - lighting and CT-MR scenes r9...
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { $zip=Join-Path (Get-Location) 'downloads/QAROS_VTK_Windows_session_022c40b6_2026-10-14_r9.zip'; $expected='12f3001e2209f4876adc3607d5e459aa4b2e9fed796dd52acc1f473253223335'; if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ine $expected) { throw 'Windows starter checksum mismatch.' }; Expand-Archive -LiteralPath $zip -DestinationPath 'package/windows-start' -Force } catch { Write-Error $_; exit 1 }"
if errorlevel 1 (
  echo Preparing the preview failed. Copy the error above.
  pause
  exit /b 1
)
call "%~dp0package\windows-start\01-Preview.cmd"

