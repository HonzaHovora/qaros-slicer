# Slicer Live r8.1: Visualizer and HoloLens

Connecting HoloLens to QAROS does not itself stream Slicer content. Slicer
creates a rendering sender for that target peer and each app volume.
One Visualizer receiver and one headset can receive independent stereo views
of the same workspaces. Slice panels are shared previews. R8.1 gives each new
panel a 14-inch diagonal, independent of model scale; resize it in QAROS as needed.

## Install and test

1. Close Slicer. Fetch/Pull branch `codex/slicer-headset-streams` containing
   r8.1 and run `UPDATE-LIVE-PLUGIN.cmd`. See the
   [installation guide](QAROS_DEV2927_UPDATE.md).
2. Connect HoloLens in QAROS to the same Hub session used by Slicer. For the
   first test, choose **Headset only** and do not create a Visualizer receiver.
3. Open the two-volume scene in Slicer. Leave **Separate QAROS workspace for
   each volume**, centering and slice previews enabled. Set **Model size** to
   **1x (1:1)**. Click **Start live streaming**, approving Slicer if requested.
4. The status should show **Headset**, two connected volumes and an increasing
   frame count. Two volumes in this mode create two senders. There should be
   no Visualizer target or Visualizer rendering sender in the log.
5. Check both volumes and visible slice panels in HoloLens. Move your head:
   perspective must follow it. Change a transfer function or ROI in Slicer;
   the change should appear in the glasses. Check the physical dimensions
   against the **Workspace** readout and the source data's millimetre spacing.
6. Stop, change Model size to 0.5x or 2x and Start. Dimensions should halve or
   double; 1:1 resets the slider. Centering alone must never change size.
7. Compare **Headset only** with **Visualizer + headset**, using the same
   scene, scale, panel settings and render resolution. The combined mode
   creates four senders for two volumes. Compare measured FPS/timings; no
   speedup is assumed before measurement. The ordinary Slicer desktop view
   still exists in both modes.
8. Test a late headset: start combined mode with just the Visualizer receiver,
   then connect HoloLens. Visualizer frames should continue during headset
   negotiation, and existing panels should become visible in the glasses.
9. Repeat Stop/Start three times with the same receivers. QAROS and target
   applications must remain running. A GUI crash or failed restart remains
   a separate open issue; r8 does not claim to resolve it.

## If the headset stays blank

The log folder is displayed in the module. In `host-bridge.log`, check:

- `Host build: installed-hub-update-r8` and `Target mode: headset` confirm
  the intended DLL and mode.
- `PEER_OBSERVED` reports target/headset peers, their role, category, app state
  and eligibility. If no headset target appears, check the Hub session and
  that its target app is connected, not only the physical device pairing.
- `TARGET_SELECTED type=Headset` means a headset was selected.
- `SENDER_CONNECT ... target=Headset ... app_volume=...` starts negotiation.
  `WORKSPACE_FAILED` gives a failure for that volume. No usable sender causes
  startup to end with an error; a discovered device alone is not success.
- `FIRST_FRAME` and growing frame counts confirm SDK submission. They do not
  independently prove the image is visible in the physical glasses.

Use a current attempt's log: previous sessions cannot establish why a new
attempt is blank. Do not reset all Hub data to collect this distinction.

## Selection and implementation

A target must advertise role `TARGET` and the requested category (`HEADSET`
or `VISUALIZER`). R8 accepts `Unknown`, `Initializing` and `Running` app
states on the pinned dev.2927 header; shutting-down/retired and unrelated
roles are excluded. Multiple available targets of one category are reported
as ambiguous. Keep one of that category connected. A chosen peer stays pinned
until Stop; restart streaming after replacing a receiver.

The current official
[Vulkan source example](https://github.com/Quaternar/qaros/blob/2314325dbc931637007c7e4afe72883314e7a31e/qar-streaming-c/examples/vulkan_cube/main.cpp)
subscribes before enumerating peers, selects targets and passes both
`QarRenderSenderInit.peer_id` and `app_volume_id`. The current
[peer guide](https://github.com/Quaternar/qaros/blob/2314325dbc931637007c7e4afe72883314e7a31e/docs/website/docs/developer-guide/peers.mdx)
uses peer presence for discovery and deprecates app state as a readiness
signal. Our installed dev.2927 header predates presence: r8 removes the
strict Running requirement while leaving sender negotiation responsible for
connection. It does not load new SDK functions into the older runtime.
This is a compatibility adjustment, not proof of today's hardware failure.

Per-target startup is independent of frame delivery to another target. Each
sender has its own graphics context, camera pose and FOV. Headset-only uses
slot zero for the headset, never a Visualizer fallback. Panels gain a late
target after its senders finish connecting; their audience is never emptied
because the SDK treats an empty list as everyone. Panel interaction is not
implemented. Startup waits up to two minutes if no usable sender appears.

ABI 5 remains unchanged. Both headset and combined modes require metadata
`multi_target=1` and `target_discovery=2`; the loader also requires r7's
`runtime_handle_only=1` cleanup. Local selection, routing, cancellation,
physical-placement and installer tests cannot replace a Windows/NVIDIA/
HoloLens run. On 2026-10-21 the user confirmed r8 works, including the headset.
No measured performance comparison was supplied. R8.1 reuses the same native
DLL and only changes the initial panel size; its appearance needs a user check.
