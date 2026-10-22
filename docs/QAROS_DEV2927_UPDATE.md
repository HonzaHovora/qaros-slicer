# Slicer Live r8.2 with installed QAROS dev.2927

Supported installation: **0.9.0-dev.2927+f291e404**, normally
`C:\Program Files\Quaternar\QAROS`. Package: **installed-hub-update-r8.2**,
host ABI 5, `multi_target=1`, `target_discovery=2`, `runtime_handle_only=1`.
R8.2 retires the separate-renderer Slicer module and supports fresh installation.
It keeps r8.1 panel defaults and reuses the verified r8 native DLL;
`Host build` in the native log therefore still reports r8.

## Install and start

1. Close Slicer. Fetch/Pull the checkout on `main`.
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

## 2D panel size

Each new slice panel starts with a **14-inch diagonal (35.56 cm)** while
preserving its initial video aspect ratio: about **31.0 × 17.4 cm** at 16:9,
or **25.1 × 25.1 cm** for a square. This replaces the previous 45 cm bounding
square with a consistent screen diagonal. It is independent of the 3D model
scale and video pixel resolution. The user can resize the panel in QAROS;
the plugin only supplies size at creation and does not reset it during frames,
hide/show or late headset joins. Recreating a panel applies the default again.

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
the user subsequently confirmed that r8 works, including headset streaming.
That functional report does not identify the original cause or quantify a
performance gain. Follow the headset test guide for further comparisons.

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

Since r8.2, `UPDATE-LIVE-PLUGIN.cmd` also performs a fresh installation and
removes the retired Slicer exporter with backup. `START-PREVIEW.cmd` redirects
to that installer; old combined preview archives are historical only and their
publishing jobs are disabled. The current Live ZIP contains
the Windows x64 bridge and Python plugin, with no QAROS runtime binaries.
Cross-builds and automated tests do not verify Windows/NVIDIA encoding,
physical headset size, headset display, speed or long-running stability.
