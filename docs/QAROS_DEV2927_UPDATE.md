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
   Panels are enabled by default. For the reproduced panel crash, select
   **Test panel startup step by step** before Start and follow the test below.

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

## Confirmed panel creation problem (2026-10-19)

On the user's Windows/NVIDIA machine, Stop/Start with two independent volumes
and slice panels enabled repeatedly produced the first volume's image, a QAROS
crash, then recovery with both volumes after approximately 30 seconds. With the
same two volumes and slice panels disabled, startup completed without a crash
and both volumes appeared. This isolates the reproducible trigger to enabling
panels in this configuration; it does not identify the internal faulty function.

**18:17 follow-up:** r4 still triggers the same WebCore access violation, now
confirmed by the launcher's process-exit/restart records. It occurs with only
the first new panel created, before any panel frame call. The Hub and SDK
snapshots confirm stream content and matching IDs. See the
[correlated timeline and manual reproduction](PANEL_STARTUP_CRASH_20261019.md).

**18:34 manual test:** the user waited approximately 30 seconds while both
volumes produced 664 frames, then opened only Red with video disabled. The same
WebCore exception occurred at 18:34:47. No panel begin/show-frame calls were made;
steps 2/3 were not run. This reproduces creation-time failure after startup and
rules out a simple startup delay as a repair for this case. The next required
input is the QAROS GUI implementation or a matching symbolized crashing-thread
stack. The installed r4 build is sufficient to reproduce; no update is needed.

The developer-requested comparison with the official Vulkan source is recorded
in the [crash investigation](PANEL_STARTUP_CRASH_20261019.md#comparison-with-the-official-vulkan-source-after-developer-feedback).
The tested build already uses local-app onboarding and common names for both
volumes and panels; Hub logs confirm both. The Vulkan example does not create
GUI panels. Runtime selection, GPU ownership and cross-launch identity policy
are documented differences, not established repairs for the exception.

**October 20 QAROS report:** five attached October 19 dumps now confirm the
same WebCore fault site, including the 18:34 manual test. The report's current
alert is a different mixer startup failure: 57 starts in about one minute,
with status-1 exits before session initialization is logged. The specific
startup error is missing. See the [report review](CRASH_REPORT_20261020.md)
for the successful/failed startup comparison and separate historical launcher
errors. This documentation update requires no plugin reinstall.

The supplied crash dump at 17:23:04 local time identifies `qar-stereokit-gui.exe`,
thread `SK_StereoKitGUI`, exception `0xC0000005`, read address `0x4`, at
`WebCore.dll +0x2DA26E0`. Reading the dump confirms `R14=4` at the faulting
`movzx ecx, byte ptr [r14]`. The available debugger could not unwind past that
frame without the corresponding module/unwind data; no named caller or full
call stack has been established. The dump is later than the initial plugin log
ending at 17:17:39, so those are not treated as a single timestamped crash.

The briefly published `installed-hub-update-r3-panels-off` only disabled panels
by default. The user requested investigation rather than that workaround.
Package **`installed-hub-update-r4-panel-probe`** restores enabled panels and
adds a manual experiment plus native logging. It is **diagnostic, not a confirmed
crash fix**. The existing dump establishes the failing process/module, but
neither it nor the source review establishes the internal root cause.

### Run the panel experiment

The user's run has now failed at step 1 as described above. These steps remain
as the reproduction procedure for the QAROS developer; the user does not need
to repeat the completed experiment or advance to steps 2/3.

1. Close Slicer, pull the PR branch and run `UPDATE-LIVE-PLUGIN.cmd`. Restart
   Slicer so the new native DLL is loaded. Use the normal Red/Yellow/Green layout.
2. Keep **Show slice views as panels (preview only)** enabled, also select
   **Test panel startup step by step**, then Start. Wait until both 3D volumes
   are visible and responsive. This phase creates no panels.
3. Click **1. Open Red panel without video**. The plugin creates the normal
   stream-backed panel with its normal OpenGL video sender and stages the slice
   locally, but does not call video begin-frame/show-frame. Observe the result.
4. If QAROS remains running, click **2. Start Red panel video** and wait for the
   slice image. It uses the same panel and sender; no panel recreation occurs.
5. If that works, click **3. Add the other slice panels**. Observe the result.
6. At the first crash, do not advance further. Run `COLLECT-LOGS.cmd` promptly
   and provide its ZIP plus the step that failed. The collector now includes
   recent QAROS process text logs from `%TEMP%\quaternar\logs`, prioritizing
   `qar-stereokit-gui` and crash reports. It lists dump locations without copying
   dumps, credentials or session state. If all three steps work, report that too.

Interpretation is deliberately limited:

| First failure | What it narrows down |
| --- | --- |
| Before step 1 | Failure independent of creation of new slice panels in this run. |
| Step 1 | Panel/sender creation or receiver initialization; no video frame has been sent. |
| Step 2 | First-frame acquisition/copy/submission or receiver processing; compare the native stage logs. |
| Step 3 | Adding further panels/streams; not enough by itself to prove a race or resource limit. |
| All steps work, normal startup still crashes | Timing, order or concurrent initialization remains implicated, not proven. |

The native log records `PANEL_CONTENT_REQUEST`, `PANEL_CREATE_BEGIN`,
`PANEL_CREATED`, a `PANEL_REGISTERED` snapshot (actual content type, stream ID,
visibility and size), then `PANEL_BEGIN_POLL`, `PANEL_FRAME_ACQUIRED`,
`PANEL_FRAME_COPIED` and `PANEL_FIRST_FRAME`. A delayed/missing registry snapshot
is logged separately and is not treated as proof of wrong content. A successful
first-frame submission is not proof that the receiver displayed it. Diagnostic
queries themselves may alter timing; compare the ordinary startup with the same
instrumented build. In the 18:17 run each synchronous registration check took
about two seconds on the panel worker, delaying the first frame and the next
panel creation. There is no explicit startup sleep, but this instrumentation
does change timing and must not be mistaken for a crash fix.

Source review finds the required `QarGuiPanelStreamIdExt` and OpenGL extension
chained correctly, one RGBA8 mono view, and a sender owned by the same session.
The 18:17 follow-up confirms the Hub mutation and SDK snapshots carry matching
stream content; the original GUI's transient internal state is still unknown.
Matching module binaries/PDBs or QAROS internal source would still
be needed to identify the named WebCore caller from this dump. Headset behavior
and broader long-running stability are not established by the startup test.

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
Slice panels remain optional read-only previews, enabled by default.
Stop destroys senders/panels before the session and leaves the shared QAROS Hub
running.

For rollback, close Slicer and restore the reported backup over
`package/windows-start`; select the SDK matching the restored DLL. A DLL already
loaded into Slicer cannot be switched by changing the field: restart Slicer.

## Verification

The shipped x64 DLL is cross-compiled with MinGW-w64 GCC 13-posix and static
compiler runtime. It is built for the exact installed header. Local tests cover
target selection, resource identity isolation, registry/path migration, bridge
fingerprint matching, frame control flow, manual panel-test sequencing and the
PowerShell updater (including paths with spaces). Both previous pinned SDK
variants still compile separately.

Windows CI covers all three headers, native DLL loading, context restoration
and the updater under Windows PowerShell 5.1. This does not replace the real
Windows/GPU check. The user has confirmed two separate workspaces and startup
with panels off; the panel failure and limited scope of that check are above.
The CI infrastructure previously
failed before executing steps; check the current run before treating it as passed.
