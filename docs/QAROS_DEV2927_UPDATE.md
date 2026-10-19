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
Slice panels remain read-only previews. Stop destroys senders/panels before the
session and leaves the shared QAROS Hub running.

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
Windows/GPU check: approval in the installed Hub, one volume, two separate
workspaces, slice previews, then stop/start. The CI infrastructure previously
failed before executing steps; check the current run before treating it as passed.
