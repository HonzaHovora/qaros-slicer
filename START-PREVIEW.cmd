@echo off
setlocal
cd /d "%~dp0"
if not exist "downloads\QAROS_VTK_Windows_session_022c40b6_2026-10-15_r11.zip" (
  echo The Windows starter ZIP is missing. Use Fetch origin and Pull origin in GitHub Desktop.
  pause
  exit /b 1
)
echo Preparing the Windows preview - live Slicer renderer r11...
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { $zip=Join-Path (Get-Location) 'downloads/QAROS_VTK_Windows_session_022c40b6_2026-10-15_r11.zip'; $expected='baa8f803914c62c366e3efe4f1d496e314d0ceb518f65323226b1fae131feb76'; if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ine $expected) { throw 'Windows starter checksum mismatch.' }; Expand-Archive -LiteralPath $zip -DestinationPath 'package/windows-start' -Force } catch { Write-Error $_; exit 1 }"
if errorlevel 1 (
  echo Preparing the preview failed. Copy the error above.
  pause
  exit /b 1
)
call "%~dp0package\windows-start\01-Preview.cmd"

