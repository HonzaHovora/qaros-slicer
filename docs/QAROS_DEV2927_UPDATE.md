# Slicer Live with installed QAROS dev.2927

The supported installation is **0.9.0-dev.2927+f291e404**, normally
`C:\Program Files\Quaternar\QAROS`. The Live update is
**installed-hub-update-r5**, with host ABI 5.

## Install and start

1. Close Slicer. Switch the repository checkout to `main` and Fetch/Pull.
2. Run `UPDATE-LIVE-PLUGIN.cmd`. It reads the 64-bit machine registry key
   `HKLM\SOFTWARE\Quaternar\QAROS\InstallFolder`, falling back to
   `%ProgramFiles%\Quaternar\QAROS`. For a custom installation use
   `UPDATE-LIVE-PLUGIN.cmd -SdkRoot "E:\Quaternar\QAROS"`.
3. Open the installed QAROS. In **Stream Graph → This PC watches**, create
   and start a receiver, then open its **Texture Grid** tab. Alternatively,
   connect a headset. The Visualizer control window alone is not a running
   receiver. This bridge serves one running target at a time.
4. Open Slicer → **QAROS Live Renderer**. `QAROS SDK folder` is the installation
   root containing `include` and `bin`. `Host bridge DLL` is
   `package\windows-start\Release\qarvtk-host.dll` in the updated checkout.
5. Leave **Test panel startup step by step** unchecked for normal use.
   Slice panels are enabled by default. Choose `visualizer` or `headset`,
   click **Start live streaming**, and approve Slicer in QAROS if prompted.

## Normal panel startup in r5

Ordinary panel creation no longer performs the synchronous registration
inspection that delayed each panel in r4. The inspection is retained only
when opening a panel with video disabled in the explicit manual diagnostic
mode. Sender creation, panel registration, first-frame logs, normal frame
pacing and independent volume workspaces remain available.

The package manifest records `panel_registration_snapshot=manual_probe_only`.
The update does not claim to repair the receiver lifecycle issue below.

## Known dev.2927 receiver issue and observed recovery

The user can stream the volumes and GUI panels successfully with a newly
created receiver. After stopping Slicer streaming, the existing receiver can
fail to display again. Removing that receiver in Visualizer and creating a
new one restores the working configuration and avoids the observed panel
startup problem. This is the current operational workaround.

For QAROS investigation, compare startup with a restored receiver against
startup with a newly created receiver, and then repeat Slicer Stop/Start
while retaining the new receiver. Retained state from a previous session is
a hypothesis; the exact fault and any SDK interaction remain unconfirmed.
A successful fresh receiver does not establish that reconnecting is fixed.
Do not reset all Hub data to perform this comparison.

The optional **Test panel startup step by step** remains available for the
QAROS developer: start the volumes, open only Red without panel video,
then enable its video and finally add the other panels. The registration
inspection in this mode may take a few seconds. It is not part of normal
startup and need not be enabled for everyday use.

## Package checks and rollback

The SDK header SHA256 is
`a32cecd4137dd3b28e0d5e0c1642a066cbea976f81b90f1f31fbac4d0fba8d4a`.
The updater verifies the complete installed SDK, archive checksum and every
payload hash. It backs up replaced plugin files under
`package/live-backup-<timestamp>` and rolls back a failed copy. To restore a
previous update, close Slicer and copy the backed-up files to their matching
paths under `package/windows-start`.

`START-PREVIEW.cmd` preserves an installed Live update instead of overwriting
it with the older preview bundle. That archived standalone preview has its
own SDK support; it is separate from the Live bridge updated here.

The ZIP contains the Windows x64 bridge and Python plugin, not QAROS runtime
binaries. It preserves ABI 5 and the manual probe capability. Cross-build and
installer verification do not replace a live Windows/NVIDIA test of r5;
headset and long-running stability remain unverified.
