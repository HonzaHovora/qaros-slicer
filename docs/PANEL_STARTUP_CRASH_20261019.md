# Panel creation crash: ordinary startup and delayed manual reproduction

## Latest result: manual step 1 also crashes (18:34)

The requested delayed experiment is now complete. **A single new stream panel
crashes the already running QAROS GUI with panel video disabled.** Both volume
streams had produced frames for approximately 30 seconds before the user opened
Red. The existing GUI process had itself been running since 18:17:05, about
17 minutes before this failure. Delaying panel creation until after volume/GUI
startup therefore does not eliminate this reproduction.

Source archive: `QAROS-VTK-diagnostics-20261019-183522-479.zip`, SHA256
`169efc6d4cad9762893be8f2a0d6cb2a535f69ab4b89f0aa3e40280a4504e11d`.
It confirms the same installed r4 DLL/header hashes listed below. It contains
the new crash text report, but not the new minidump.

### Manual-run evidence

All wall times in this section are 2026-10-19, Europe/Prague (UTC+02:00).
Python logs use UTC; the table converts them to local time.

| Time | Recorded event | Evidence |
| --- | --- | --- |
| 18:34:14.423 | `PANEL_PROBE waiting_for_manual_step volumes_only`; native gate is `enabled=no`. | `host-python-1.log:6`; `host-bridge-1.log:4` |
| 18:34:16.582 / .880 | Both volume senders connect; first frames follow at native elapsed 2571.67 / 2778.60 ms. | `host-sdk-1-1.log:43,56`; `host-bridge-1.log:20,24` |
| 18:34:47.535 | 664 total volume frames have been produced; both volume counters advance in every preceding one-second report. | `host-python-1.log:36` |
| 18:34:47.615 | User advances only `step=1 red_panel_no_video`. | `host-python-1.log:37` |
| 18:34:47.735 | SDK creates the one-view video conversion resources. | `host-sdk-1-1.log:62,63` |
| 18:34:47.741 | Hub validates the Red panel creation with stream content `Type:1`, the expected stream ID, one intended target, positive size and identity orientation. | `qaros-10-launcher_stdout.log:9597` |
| 18:34:47 | GUI PID 25588, thread 18624, crashes: `0xC0000005`, read `0x4`, `WebCore.dll +0x2DA26E0`. Crash time has only whole-second precision. | `qaros-1-20261019-183447_qar-stereokit-gui_25588.crash.txt` |
| Native elapsed 35506.6 ms | Registration snapshot confirms video content, matching stream ID and intended target; only one panel was created. | `host-bridge-1.log:40` |
| 18:34:49.714 / .732 | Launcher records the crashed GUI and starts replacement PID 6040. | `qaros-10-launcher_stdout.log:9619,9623` |
| 18:34:52.259 / .298 | Replacement `BrowserControl` connects Red at 756×292; SDK confirms its transfer connection. | `qaros-6-mixer_…_stdout.log:8508`; `host-sdk-1-1.log:68` |

There is no `PANEL_VIDEO_GATE enabled=yes`, `PANEL_BEGIN_POLL`, panel frame
acquisition/copy/submission, or manual step 2/3 anywhere in this run. Source
review confirms the gate returns before all panel begin/access/show-frame calls.
Local slice capture/staging, video-sender creation and panel registration still
occur in step 1; this is not a sender-free or Slicer-free test.

The earlier first-video and all-three-panels hypotheses are not necessary for
this failure, and a delay of approximately 30 seconds does not solve it. A
race inside the creation of one panel, invalid transient model state or a
WebCore control lifetime/content-dispatch error remain hypotheses, not proven
causes. The same failure signature does not by itself identify the same caller.

### Reproduction for the QAROS developer

Use the existing r4 plugin and the installed dev.2927 runtime. Keep the normal
Red slice visible, enable **Test panel startup step by step**, start the two
volumes, wait until they are responsive, and click only **1. Open Red panel
without video**. This exact sequence has now reproduced the crash; steps 2/3
are unnecessary. No new plugin installation is needed.

The relevant SDK sequence is in `PanelStream::open()` in
[`src/host_panels.cpp`](../src/host_panels.cpp):

1. `qar_video_sender_create(session, &init, &sender)`: OpenGL callbacks, one
   756×292 RGBA8 texture/view, color data, `QAR_VIDEO_FRAME_VIEW_EYE_NONE`.
2. `qar_video_sender_stream_id(sender, &content.stream_id)` and a single
   `QarGuiPanelStreamIdExt` chained through `QarGuiPanelInit::header.next`.
3. `qar_gui_panels_get_or_create(session, &gui, &id)`: a new ASCII common name,
   display name `Slicer Red`, identity orientation, position (-0.5, -0.385,
   -1.45), size approximately 0.45×0.17381 m, content scale 1, one target.
4. `qar_query_gui_panels` plus read-only inspection of the returned registration.
   The sender remains alive; no panel video frame API is called.

These calls match the supplied header's stream-content and same-session-sender
contract. Hub and SDK evidence agree on the content and identity. This review
has not found a concrete violated precondition to repair in the plugin.

Investigate the dynamic new-panel path in `qar-stereokit-gui`, especially
`BrowserControl` construction/content dispatch and any WebCore/Ultralight view
access before the first stream-connection log. Compare it with rebuilding the
same stored stream panel after the GUI restart, which reaches that log without
any video submission. Do not assume a stream panel cannot touch WebCore: its
surrounding controls or an intermediate content state may do so.

The next required input is the matching QAROS GUI source (panel creation,
`BrowserControl`, content dispatch) or a crashing-thread stack from a matching
symbolized build. A developer with the source should reproduce under the
`windows-x64-relWithDebInfo` preset and break on the access violation before
the crash handler restarts the process. PDBs from a different build do not
symbolize this release. The available GitHub connection exposes the plugin
repository, not the internal GUI implementation; no GUI fix can be validated
in this workspace yet. Raw logs/dumps are not committed.

### Separate recovery symptom

At 18:34:53 both volume senders report reconnection, but after the pause only
volume 1 continues producing frames through the end of the collected log at
18:35:22. Native volume 0 stays at 336 submitted frames. The launcher also logs
a stale media-stream proposal for volume 0 at 18:34:53.165. The log does not
establish that this warning causes the stall. Track recovery separately from
the panel-created WebCore exception; a restarted process alone is not evidence
that both volumes resumed.

## Earlier baseline: ordinary startup at 18:17

QAROS still crashes. The newer run recovers automatically, but the exception is
the same: `qar-stereokit-gui.exe`, `0xC0000005`, read at `0x4`,
`WebCore.dll +0x2DA26E0`. The failing process serves the Visualizer's mixer; the
Visualizer control process survives. Launcher records confirm a new GUI process,
not recovery of the faulting instruction in the original process.

The crash occurs in the second when **the first new stream panel is created**.
It precedes the plugin's first panel begin-frame call, the first slice-image
submission, and creation of the other two new panels. Therefore neither a slice
image nor simultaneous creation of all three panels is necessary to reproduce
this run's failure. Panel/sender creation and receiving-side initialization are
still candidates. The exact faulty function and its underlying cause remain
unproven.

## Evidence and build

Source archive: `QAROS-VTK-diagnostics-20261019-181736-906.zip`, collected
2026-10-19 at 18:17:36 Europe/Prague (UTC+02:00). SHA256:
`8011470b2541ee2c16d2bb6e8776e756e1a1480098d5c807f3774ac437c4ce4d`.
Raw logs and dumps are not committed to this repository.

- Runtime: `0.9.0-dev.2927+f291e404.demo`, installed under Program Files.
- Plugin/native build: `installed-hub-update-r4-panel-probe`, ABI 5.
- Native DLL SHA256:
  `8598ab7d389e8844d9969e7659cec321dd3b2fbdae42ab5fe4493f9a1db95d56`.
- SDK header SHA256:
  `a32cecd4137dd3b28e0d5e0c1642a066cbea976f81b90f1f31fbac4d0fba8d4a`.
- GPU: NVIDIA GeForce RTX 2070 with Max-Q Design.
- Crash report: `qaros-1-20261019-181703_qar-stereokit-gui_20104.crash.txt`.
  Faulting PID 20104, thread 11080. This archive contains the text report, not
  its new dump. The earlier 17:23 dump has the same signature, but is a different
  execution and must not be substituted for this run's stack.

## Timeline

Times below are local UTC+02:00. Host-native events use elapsed milliseconds;
their approximate wall-clock mapping is corroborated by the SDK/launcher logs.
The crash report itself has only whole-second precision.

| Time | Recorded event | Evidence |
| --- | --- | --- |
| 18:17:02.764 / .969 | Both independent volume senders connected. | `host-sdk-1-1.log` |
| About 18:17:03.05 / .14 | First stereo frame submitted for each volume. | `host-bridge-1.log`, elapsed 5247.20 / 5339.96 ms |
| About 18:17:03.11 | Red panel created, elapsed 5306.49 ms. | `host-bridge-1.log` |
| 18:17:03.124 | Hub validates Red's creation mutation with stream content `Type:1`, its stream ID, one intended target, positive size and identity orientation. | `qaros-13-launcher_stdout.log` |
| 18:17:03 | GUI crashes at the WebCore offset above. | New crash report |
| 18:17:04.985 | Launcher records PID 20104 stopped, `crashed=true`, exit `0xC0000005`. | Launcher log |
| 18:17:05.014 | Launcher starts replacement GUI PID 25588. | Launcher log |
| About 18:17:05.11 | Red registration check returns; first panel begin-frame polling begins. | Host elapsed 7310.77 / 7310.86 ms |
| 18:17:05.227 / 07.181 | Hub validates Yellow and Green creation mutations, both `Type:1`. | Launcher log |
| 18:17:08.161 / .480 | Replacement process reports StereoKit and model initialization complete. | `qaros-5-mixer_…_stdout.log` |
| 18:17:08.581–.601 | `BrowserControl` connects all three panel streams at 756×292. | Mixer/GUI log |
| About 18:17:09.16–.19 | First panel images submitted: Green, Red, Yellow. | Host elapsed 11360.10 / 11376.00 / 11382.90 ms |
| 18:17:09.637 / .673 | Both volume transfers reconnect and replay Resume. | Host SDK log |
| 18:17:19.844 onward | Python frame counters resume advancing; later reports include both volumes. | `host-python-1.log` |

Process launch is not equivalent to the first displayed image. The recorded GUI
restart was fast, while subsequent model initialization, stream reconnection and
new volume-frame production have distinct timestamps. The user's observation of
a shorter visible interruption is consistent with recovery, not proof the crash
was removed.

## What the new instrumentation establishes

All three native registration snapshots report `type=1`, `stream_matches=yes`,
visible state, one target with `target_present=yes`, and size approximately
0.45 × 0.17381 m. The Hub mutation also carries stream content from creation.
The replacement GUI's `BrowserControl` subsequently connects the corresponding
video streams. The evidence does not support a plugin request accidentally
creating a website panel or passing a different stream ID.

It does **not** establish what transient state the original GUI observed before
the exception, nor whether internal UI controls use WebCore for a video panel.
An incomplete receiving-side model, initialization order or view lifetime error
cannot be distinguished without QAROS implementation/stack evidence.

The panel registration check takes approximately **2004 ms per panel** in this
run. It runs synchronously on the panel worker, between creating a panel and
trying its video frame, so it changes both first-image timing and the spacing
between panel creations. This is a measured instrumentation effect, not a
designed delay or an identified fix. Faster recovery cannot be attributed to a
specific repaired mechanism.

No `PANEL_PROBE` or `PANEL_VIDEO_GATE` markers occur in this run. It exercised
ordinary startup with instrumentation, not the manual stepped experiment. The
older run included as `host-bridge-2.log` has no panel openings, runs for about
19 minutes, and stops by GUI request after 15,327 submitted stereo frames.

The GUI stderr also says it could not open `ultralight.log` for writing. This
explains missing browser diagnostics but does not by itself explain the access
violation. Do not treat administrator elevation or filesystem permissions as
a proven crash repair. The Windows `RADAR_PRE_LEAK_64` record is from 17:25,
not the new crash; it is not evidence of this run exhausting memory.

## Experiment proposed after 18:17 (completed above at 18:34)

The installed r4 build supported the following experiment without a new plugin
installation. It is retained here for the investigation history; the failed
step-1 result above supersedes it as a request for another user test:

1. Enable **Test panel startup step by step** before Start, keeping slice panels
   enabled. Wait until both volumes are visible and responsive.
2. Click only **1. Open Red panel without video**. Do not advance to video or
   additional panels. Collect logs whether this stays up or crashes.

If it crashes, initialization of the one new panel/sender also reproduces after
the volume streams are established. If it stays up, the difference between
immediate startup and later panel creation becomes the next controlled variable.
Neither outcome alone proves a named race or fixes the implementation.

For the QAROS-side developer, inspect the dynamic new-panel notification path
versus rebuilding panels from stored state during GUI startup. In particular,
follow panel model readiness, content dispatch, and any WebCore/Ultralight view
or control creation and updates before `BrowserControl: connecting GUI panel
stream` is logged. After restart those connections succeed for the same panels.
These are investigation targets, not a claim that a particular source line is
faulty.

The QAROS GUI implementation is not in this plugin repository and was not
accessible through the available source connection. A matching symbolized
build, or matching module binaries plus the crash dump and QAROS source, is
needed to move from module+offset to the actual caller. No speculative plugin
delay, content replacement or automatic disabling is shipped for this finding.
