# Slicer Live with installed QAROS dev.2927

The installation supplied on 2026-10-19 is **0.9.0-dev.2927+f291e404**, normally
`C:\Program Files\Quaternar\QAROS`. Its header differs from the earlier portable
dev.2540 package. Changing the path alone cannot make the old DLL compatible.

## Install and start

1. Close Slicer and the old portable Visualizer. Fetch and pull
   `codex/slicer-qaros-dev2540` (the existing PR branch now also contains this fix).
2. Run `UPDATE-LIVE-PLUGIN.cmd`. It reads the 64-bit machine registry key
   `HKLM\SOFTWARE\Quaternar\QAROS\InstallFolder`, falling back to
   `%ProgramFiles%\Quaternar\QAROS`. A custom installation can be selected with
   `UPDATE-LIVE-PLUGIN.cmd -SdkRoot "E:\Quaternar\QAROS"`.
3. Open the **installed** QAROS. Start one Visualizer receiver, or connect one
   headset through QAROS. Opening the Visualizer control window alone does not
   necessarily start a receiver.
4. Open Slicer → **QAROS Live Renderer**. `QAROS SDK folder` must point to the
   installation root containing `include` and `bin`, not `bin` itself.
   `Host bridge DLL` is `package\windows-start\Release\qarvtk-host.dll` in the
   updated checkout. The plugin migrates a saved old SDK path and prefers the
   verified updated DLL over a stale saved DLL path.
5. Choose `visualizer` or `headset` and **Start live streaming**. On first use,
   allow Slicer in the QAROS Hub approval window. The plugin reports the
   approval/connection progress while the GUI stays responsive.
   Leave **Show slice views as panels (preview only)** off on dev.2927; it is
   now unchecked by default because opening the panels can crash QAROS.

The SDK and bridge must match exactly. The new header SHA256 is
`a32cecd4137dd3b28e0d5e0c1642a066cbea976f81b90f1f31fbac4d0fba8d4a`.
The updater verifies this header, the runtime, launcher and device catalog,
then checks the archive and each payload file before installing. It backs up
replaced files under `package/live-backup-<timestamp>` and rolls back a failed
copy. No admin rights are needed to update the plugin in your writable checkout.
No QAROS runtime binaries, certificates or pairing state are included or changed.

`START-PREVIEW.cmd` now preserves a Live update when its marker is present; it
starts the existing preview instead of extracting r17 over the plugin. The
standalone preview/sender in that old bundle still has its original SDK support.

## Confirmed panel startup problem (2026-10-19)

On the user's Windows/NVIDIA machine, Stop/Start with two independent volumes
and slice panels enabled repeatedly produced the first volume's image, a QAROS
crash, then recovery with both volumes after approximately 30 seconds. With the
same two volumes and slice panels disabled, startup completed without a crash
and both volumes appeared. This isolates the reproducible trigger to enabling
panels in this configuration; it does not identify the internal faulty function.

The supplied crash dump at 17:23:04 local time identifies `qar-stereokit-gui.exe`,
thread `SK_StereoKitGUI`, exception `0xC0000005`, read address `0x4`, at
`WebCore.dll +0x2DA26E0`. Reading the dump confirms `R14=4` at the faulting
`movzx ecx, byte ptr [r14]`. The available debugger could not unwind past that
frame without the corresponding module/unwind data; no named caller or full
call stack has been established. The dump is later than the initial plugin log
ending at 17:17:39, so those are not treated as a single timestamped crash.

Package `installed-hub-update-r3-panels-off` keeps the existing native bridge
and makes panels opt-in with a visible warning. This is a workaround for the
reproduced trigger, not a repair of WebCore or panel initialization. The native
DLL remains `installed-hub-update-r2`, SHA256
`17097e86bf63f7f93bb66d5f4edba5ab22792cae92ad89e8f529712e22052085`.
Re-enable panels only for a deliberate retest after a QAROS fix. Headset behavior
and broader long-running stability are not established by this startup test.

## Behavior and limits

The Live bridge joins the installed Hub using `QarOnboardLocalAppExt`. Local
enrollment is stateless; the Hub manages approval, and there is no pairing code
or onboarding identity file to save. It uses Slicer's GPU and verifies the Hub
session uses the same adapter before creating senders.

The bridge discovers an already running target whose role is **Target** and
category matches the chosen viewer. Control windows, source apps, infrastructure,
initializing and retired peers are excluded. This bridge still serves one target
at a time: if several matching receivers are running it reports the ambiguity;
keep one running and retry. It does not auto-launch a legacy Visualizer or invite
a new headset. Target selection and device management belong to the QAROS Hub.

Each Slicer volume keeps its own workspace and sender. Volume and panel common
names contain the source peer ID and an index, so duplicate or Unicode labels,
separate Slicer processes and preview panels cannot share an identity by mistake.
Slice panels remain optional read-only previews, off by default in this update.
Stop destroys senders/panels before the session and leaves the shared QAROS Hub
running.

For rollback, close Slicer and restore the reported backup over
`package/windows-start`; select the SDK matching the restored DLL. A DLL already
loaded into Slicer cannot be switched by changing the field: restart Slicer.

## Verification

The shipped x64 DLL is cross-compiled with MinGW-w64 GCC 13-posix and static
compiler runtime. It is built for the exact installed header. Local tests cover
target selection, resource identity isolation, registry/path migration, bridge
fingerprint matching, frame control flow and the PowerShell updater (including
paths with spaces). Both previous pinned SDK variants still compile separately.

Windows CI covers all three headers, native DLL loading, context restoration
and the updater under Windows PowerShell 5.1. This does not replace the real
Windows/GPU check. The user has confirmed two separate workspaces and startup
with panels off; the panel failure and limited scope of that check are above.
The CI infrastructure previously
failed before executing steps; check the current run before treating it as passed.
