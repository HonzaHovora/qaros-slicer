@echo off
setlocal
cd /d "%~dp0"
set "QAR_PLUGIN=package\windows-start\plugins\slicer"
if not exist "%QAR_PLUGIN%\QarosVTKLib\qarvtk_host_panels.py" goto missing
if not exist "package\windows-start\Release\qarvtk-host.dll" goto missing
tasklist /NH /FI "IMAGENAME eq SlicerApp-real.exe" | find /I "SlicerApp-real.exe" >nul
if not errorlevel 1 goto running
tasklist /NH /FI "IMAGENAME eq Slicer.exe" | find /I "Slicer.exe" >nul
if not errorlevel 1 goto running
if not exist "integrations\slicer\QarosLive.py" goto missing
if not exist "integrations\slicer\qarvtk_host_view.py" goto missing
if not exist "integrations\slicer\qarvtk_host_runtime.py" goto missing
if not exist "downloads\qarvtk-host-independent-abi5.zip" goto missing
if not exist "downloads\qarvtk-host-independent-abi5.zip.sha256" goto missing
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $archive='downloads\qarvtk-host-independent-abi5.zip'; $expected=(Get-Content -LiteralPath ($archive+'.sha256')).Split(' ')[0]; if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) { throw 'Host update archive checksum mismatch' }; Expand-Archive -LiteralPath $archive -DestinationPath 'package\host-independent-update' -Force"
if errorlevel 1 goto failed
if not exist "package\host-independent-update\qarvtk-host.dll" goto failed
copy /Y "package\host-independent-update\qarvtk-host.dll" "package\windows-start\Release\qarvtk-host.dll" >nul
if errorlevel 1 goto failed
copy /Y "integrations\slicer\QarosLive.py" "%QAR_PLUGIN%\QarosLive.py" >nul
if errorlevel 1 goto failed
copy /Y "integrations\slicer\qarvtk_host_view.py" "%QAR_PLUGIN%\QarosVTKLib\qarvtk_host_view.py" >nul
if errorlevel 1 goto failed
copy /Y "integrations\slicer\qarvtk_host_runtime.py" "%QAR_PLUGIN%\QarosVTKLib\qarvtk_host_runtime.py" >nul
if errorlevel 1 goto failed
echo Independent-volume plugin and ABI 5 host DLL installed. The QAROS SDK is unchanged.
echo Open Slicer and enable Separate QAROS workspace for each volume.
echo Use VTK GPU Ray Casting and Composite for both volumes in the FIRST 3D view.
echo To restore the released r17 plugin, close Slicer and run START-PREVIEW.cmd.
pause
exit /b 0
:missing
echo Files are missing. Pull codex/slicer-multiple-volumes including its downloads folder.
echo If package\windows-start is missing, run START-PREVIEW.cmd once and close its preview.
echo After that, run UPDATE-LIVE-PLUGIN.cmd again with Slicer closed.
pause
exit /b 1
:running
echo Close Slicer before updating the plugin, then run this command again.
pause
exit /b 1
:failed
echo Copy failed. Close Slicer and rerun UPDATE-LIVE-PLUGIN.cmd.
echo START-PREVIEW.cmd restores the released r17 plugin if needed.
pause
exit /b 1
