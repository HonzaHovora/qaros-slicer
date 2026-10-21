# Slicer Live r8 with installed QAROS dev.2927

Supported installation: **0.9.0-dev.2927+f291e404**, normally
`C:\Program Files\Quaternar\QAROS`. Package: **installed-hub-update-r8**,
host ABI 5, `multi_target=1`, `target_discovery=2`, `runtime_handle_only=1`.

## Install and start

1. Close Slicer. Fetch/Pull the checkout containing r8, currently branch
   `codex/slicer-headset-streams` in draft PR #3.
2. Run `UPDATE-LIVE-PLUGIN.cmd`. It reads the 64-bit machine registry key
   `HKLM\SOFTWARE\Quaternar\QAROS\InstallFolder`, falling back to
   `%ProgramFiles%\Quaternar\QAROS`. For a custom installation use
   `UPDATE-LIVE-PLUGIN.cmd -SdkRoot "E:\Quaternar\QAROS"`.
3. Open QAROS. For Visualizer streaming, create and start one receiver in
   **Stream Graph → This PC watches** and open its **Texture Grid** tab.
   For headset streaming, connect HoloLens to the same QAROS Hub session.
   A Visualizer control window alone is not a rendering receiver.
4. Open Slicer → **QAROS Live Renderer**. The SDK folder is the installation
   root containing `include` and `bin`. The bridge DLL is
   `package\windows-start\Release\qarvtk-host.dll` in the updated checkout.
5. Select **Stream to**: **Visualizer + headset**, **Visualizer only**, or
   **Headset only**. Click **Start live streaming** and approve Slicer in
   QAROS if prompted. Slice panels start automatically when enabled; the
   manual step-by-step test mode has been removed.

## Physical size and centering

**Center model in workspace at Start** centers the content without resizing
it. **Model size (at Start)** defaults to **1x (1:1)**: one Slicer RAS millimetre
is one physical millimetre. The workspace fits the rotated physical bounds;
there is no automatic enlargement to a 65 cm longest edge.

The slider is logarithmic, from **1/8x to 8x**. Its middle is 1:1, each major
step halves or doubles the size, and the **1:1** button resets it. All volumes
use the same multiplier, preserving their relative sizes. Separate workspaces
remain side by side with 12 cm gaps. Dimensions are shown in **Workspace**.
The slider is applied at Start and is disabled during streaming. Stop, adjust,
and Start to change it. **Render resolution** independently controls pixels.

## Headset target selection

Each selected target gets one rendering sender per app volume, with both
`peer_id` and `app_volume_id` supplied. **Headset only** uses a single headset
slot and creates no Visualizer sender or Visualizer stereo render.

R8 removes the strict `Running` gate: with the pinned dev.2927 API, target
peers in `Unknown`, `Initializing`, or `Running` can negotiate a sender.
Shutting-down and retired peers, control/source/internal roles and the wrong
device category remain excluded. The current official SDK documents app
state as unsuitable for a readiness handshake; see the references in
[HEADSET_STREAMING.md](HEADSET_STREAMING.md). The newer peer-presence API is
not imported into this older installed SDK.

If no headset is discovered, the status explicitly asks for a headset in the
same Hub session. `PEER_OBSERVED`, `TARGET_SELECTED`, `SENDER_CONNECT`,
`WORKSPACE_FAILED`, and `FIRST_FRAME` distinguish discovery, negotiation and
frame submission. Python rejects older DLLs for headset and combined modes.
These changes address a restrictive selection policy and improve diagnosis;
without a current hardware log, they do not establish the cause of the
reported blank headset or prove it resolved. Follow the headset test guide.

## Runtime lifecycle and panel limitations

R7's cleanup correction remains: senders and panels close first, app volumes
close next, and the plugin releases its session and runtime handles using
`qar_runtime_handle_destroy`. It must not shut down the shared QAROS runtime.

The panel test UI, manual video gate and synchronous registration inspection
are removed in r8 (`panel_probe=0`, `panel_registration_snapshot=none`).
Normal panel creation and frame logs remain. This does not claim to fix the
remaining QAROS GUI crash on Stop/Start with the same receiver. If that
receiver becomes stuck, removing it and creating a new one remains the
observed workaround; restart Slicer streaming to select its new peer ID.

## Package checks and rollback

The unchanged pinned SDK header SHA256 is
`a32cecd4137dd3b28e0d5e0c1642a066cbea976f81b90f1f31fbac4d0fba8d4a`.
The updater verifies the complete installed SDK, archive checksum and every
payload hash. It backs up replaced files under `package/live-backup-<timestamp>`
and rolls back a failed copy. To restore a backup, close Slicer and copy its
files to matching paths under `package/windows-start`.

`START-PREVIEW.cmd` preserves an installed Live update. The older standalone
preview archive is separate and is not rebuilt here. The Live ZIP contains
the Windows x64 bridge and Python plugin, with no QAROS runtime binaries.
Cross-builds and automated tests do not verify Windows/NVIDIA encoding,
physical headset size, headset display, speed or long-running stability.
