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
copy /Y "integrations\slicer\QarosLive.py" "%QAR_PLUGIN%\QarosLive.py" >nul
if errorlevel 1 goto failed
copy /Y "integrations\slicer\qarvtk_host_view.py" "%QAR_PLUGIN%\QarosVTKLib\qarvtk_host_view.py" >nul
if errorlevel 1 goto failed
copy /Y "integrations\slicer\qarvtk_host_runtime.py" "%QAR_PLUGIN%\QarosVTKLib\qarvtk_host_runtime.py" >nul
if errorlevel 1 goto failed
echo Multi-volume Python plugin installed over the existing r17 host DLL.
echo Open Slicer. QAROS Live Renderer should say Multiple VTK GPU Composite volumes.
echo Use VTK GPU Ray Casting and Composite for both volumes in the FIRST 3D view.
echo To restore the released r17 plugin, close Slicer and run START-PREVIEW.cmd.
pause
exit /b 0
:missing
echo Files are missing. Pull this branch and run START-PREVIEW.cmd once, then close its preview.
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
