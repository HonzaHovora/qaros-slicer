# Slicer Live r7: Visualizer and HoloLens

R6 adds simultaneous streaming to one running Visualizer receiver and one
headset in the installed QAROS dev.2927 Hub. Connecting HoloLens in QAROS
starts its target application; Slicer must also create a rendering sender
for that target and each app volume before it can receive scene content.

## Install and first test

1. Close Slicer. Fetch/Pull the checkout containing r7 and run
   `UPDATE-LIVE-PLUGIN.cmd`. The updater checks the SDK, verifies the package,
   and backs up the previous plugin.
2. Open QAROS and connect HoloLens using its existing connection workflow.
   For a combined test also start one Visualizer receiver. A control window
   without a receiver does not count as a rendering target.
3. Open Slicer with the two-volume scene. In **QAROS Live Renderer**, leave
   **Separate QAROS workspace for each volume** and slice previews enabled.
   Leave **Test panel startup step by step** unchecked.
4. Select **Stream to → Visualizer + headset**, then **Start live streaming**.
   Approve Slicer in QAROS if prompted. The status should list Visualizer and
   Headset separately, with two connected volumes and increasing frame counts
   for each. Two volumes and two targets create four rendering senders.
5. Check both volumes and the visible slice panels in HoloLens. Move your
   head: the perspective in the glasses must follow your head independently
   of the Visualizer camera. Change a transfer function or ROI in Slicer and
   check that both targets receive the change.
6. Repeat with **Headset only**, without a Visualizer receiver. Then test
   joining late: start **Visualizer + headset** with just the Visualizer
   receiver, and connect HoloLens after it is displaying the scene. The
   existing Visualizer frames should continue while the headset connects;
   the headset should receive the same volumes and existing panels.
7. Press Stop in Slicer. QAROS and both target applications must stay running.
   Start streaming again with the same receivers, without removing/recreating
   them, and verify volumes and panels. Repeat three times. R7 fixes the
   incorrect runtime shutdown call; this Stop/Start test is still required.

## Scope and behavior

- There is one slot per device category, not per headset model. HoloLens and
  other headsets must advertise the SDK's `TARGET`, `RUNNING`, `HEADSET`
  attributes. Control, source and internal peers are excluded.
- If multiple running receivers match a free slot, its status reports the
  ambiguity. Keep one target of that category running. A connected other
  category continues rendering. A selected peer stays selected until Stop.
- A headset can join later while the other target is running. If neither
  target yields a usable sender within the initial two-minute wait, startup
  ends with an error. Failed sender negotiation is reported per workspace.
- Recreating a receiver changes its peer identity: stop and start Slicer
  streaming to select the replacement. SDK auto-reconnect remains enabled
  for the existing sender. R7 fixes the plugin's runtime shutdown during Stop;
  whether this resolves all restored-receiver/panel symptoms remains to be
  tested. See [the update guide](QAROS_DEV2927_UPDATE.md).
- The viewers share app volumes, but each has independent stereo rendering
  and a separate graphics context per sender. Two viewers therefore require
  additional rendering/encoding work. **Headset only** avoids the Visualizer
  streams; **Render resolution** controls rendering cost.
- Slice panels are video previews; remote slice interaction is not added.
  A late target is added to the existing panels' visibility list. The list
  is never emptied, because the SDK interprets an empty list as everyone.

## Implementation and verification

The flow follows the official
[Vulkan source example](https://github.com/Quaternar/qaros/blob/be62932d0dcf5919584a3a09c40f5486d0402d90/qar-streaming-c/examples/vulkan_cube/main.cpp):
subscribe before enumerating peers, select target peers, and pass both
`QarRenderSenderInit.peer_id` and `app_volume_id` for every sender. Unlike the
example's all-target policy, this version reserves one slot per selected
category. Common names remain scoped to the Slicer source peer.

Native logs identify `TARGET_SELECTED`, `SENDER_CONNECT` and `FIRST_FRAME`
with the target peer and workspace. `PANEL_TARGET_ADDED` marks a late target's
panel audience update. These distinguish discovery, negotiation and actual
frame delivery without adding synchronous diagnostic queries to startup.

Local tests cover late target discovery, role/category filtering, snapshot
races, independent target startup, frame routing with different camera poses,
and cancellation of both target negotiations. Windows x64 cross-builds cover
all three pinned SDK headers; combined mode requires dev.2927. ABI 5 is
unchanged, and an older DLL is rejected for combined mode. Hardware output
and performance still require the manual Windows/NVIDIA/HoloLens test above.

R7 replaces `qar_runtime_destroy` with `qar_runtime_handle_destroy` in both
native clients. This releases their local runtime handle without requesting
shutdown of the shared runtime. The loader additionally rejects pre-r7 DLLs
even when their frame ABI matches. No SDK header change is needed.
