# Panel creation crash: evidence from the 18:17 run

## Finding

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

## Smallest next experiment and upstream investigation

The installed r4 build already supports the remaining experiment; no new plugin
installation is required:

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
