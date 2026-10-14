# Validation and next work

## Destination framebuffer: 2026-10-14, r6

The r5 diagnostics reach a successful begin-frame, four textures/four views and
the first eye's pose/FOV. The sender then exits at our generic `Destination
framebuffer is incomplete` check, before submitting a frame. `ChannelIsClosed`
warnings occur before this point without preventing negotiation. The r5 log
does not record the failing plane, actual GL target or framebuffer status, so
it cannot establish the exact on-device framebuffer cause.

The copy code incorrectly assumed that `array_layers == 1` implies
`GL_TEXTURE_2D`. The SDK C structure supplies no GL target. A one-layer
`GL_TEXTURE_2D_ARRAY` fails the old unchecked bind; queries then inspect the
previously bound 2D texture, and the attachment subsequently fails. A local
Mesa/EGL regression using the actual unmodified r5 `GlCopy` reproduced the exact
generic error with an array destination and a same-sized stale 2D binding.

The r6 copy distinguishes ordinary 2D and single-layer array destinations,
attaches the requested array layer with `glFramebufferTextureLayer`, checks GL
errors at each stage and restores both texture bindings. It keeps the existing
single-layer layout restriction and GPU-only production path. Attachments are
detached on failure too. The first frame reports each destination's eye, plane,
object, target, format, dimensions and mip range; errors include the named and
numeric framebuffer status and GL error. It does not change SDK texture storage.

The local actual-code GPU regression passed 2D and one-layer array destinations
with D32F and R32F depth, exact color/depth comparison, flips and state restoration.
The repository GPU test now covers both targets at 128 x 128 and 1920 x 1080 in
shared contexts, retaining its analytic depth, alpha and stereo assertions.
These are runtime-free graphics tests; the specific NVIDIA/QAROS texture and
end-to-end display still require an on-device attempt.

Code commit `d37a2617c4998e0fa1f73423445b76c97d814616` passed both Windows SDK
builds, core/peer/frame-wait/WGL tests and exact header fingerprint verification in
[run 38581274978](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/38581274978).
[Run 38581275009](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/38581275009)
passed the expanded VTK/Mesa GPU test (4.35 seconds), Linux and Windows
core/process tests, both Linux SDK branches, surface interchange and ParaView.
The local isolated copy regression also passed with the Mesa GL 3.3 override.

## Initial viewer pose wait: 2026-10-14, r5

The r4 log confirms the installed EXE fingerprint, successful OpenGL setup and
connected transfer. Its first begin-frame attempt then failed with 803 wrapping
`RenderingProducerMissingPoseData` (801), about 1.6 seconds after sender creation.
No frame was submitted. The earlier paused-transfer failure did not recur in this
attempt. This alone does not establish that pose data will arrive on a later call.

The declared view order (left color/depth, right color/depth, distinct textures)
matches the official QAROS `vulkan_cube/main.cpp` example; we do not change it.
The r5 compatibility policy retries this exact 803/801 diagnostic only before
the first submitted frame, with 100 ms backoff inside the existing 60-second
default deadline. It reports the wait every five seconds and preserves the
missing-pose condition in a timeout error. Pose loss after streaming has started
and unrelated errors remain fatal. No synthetic pose or FOV is substituted.

First-frame phase messages distinguish a successful begin-frame, validated
texture layout, fetched pose/FOV, rendering/copy and actual submission. This
allows the next on-device attempt to tell a delayed initial pose from a persistent
receiver/runtime problem. The existing regression test now covers both captured
startup errors, the post-start pose-loss restriction and unrelated causes.

Code commit `185b217cde955fb4ade99fa49e0f35f1bab9caac` passed both Windows SDK
builds, core/peer/frame-wait/WGL tests and exact header fingerprint verification in
[run 38577206824](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/38577206824).
[Run 38577206477](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/38577206477)
passed Windows core/process tests, Linux core/peer/frame-wait/process/Mesa GPU
tests, both Linux SDK builds, surface interchange and ParaView host tests.
These checks do not determine whether the user's runtime will supply pose data.

## Primary-transfer startup pause: 2026-10-14, r4

The r3 diagnostics confirm the WGL fix on the user's RTX 2070 Max-Q: the worker
probe passed, the SDK invoked bind/resolve/capture/restore callbacks, OpenGL
sender creation completed, and the SDK reported the transfer connected. The
first begin-frame then returned 803 wrapping internal status 602,
`MediaStreamingStreamIsPaused`. Our sender treated it as fatal, destroyed the
session and submitted no frames.

The r4 legacy sender follows the working BANC bridge: allow an interruptible
1.2-second negotiation interval, then retry a paused primary transfer with a
100 ms backoff. The original no-frame timeout and Stop handling still apply.
The supplied C header omits status 602 and provides no cause traversal API, so
the compatibility helper requires top-level 803, a diagnostic handle, and the
exact nested `Code: 602 Desc: MediaStreamingStreamIsPaused` diagnostic. Other
begin-frame failures still terminate with their original error. The unmodified
SDK header and r3 WGL callbacks are retained.

The `legacy-frame-wait` regression uses the captured diagnostic through the C
API's result-message function pointer. It also checks success, closed streams,
missing diagnostics and unrelated 803 causes. This tests our retry decision,
not a live runtime. Actual first-frame submission/display still needs the user's
Windows/NVIDIA test.

Code commit `7a065af10cdccc4354941df60c6687f6d2ff2c44` passed both Windows SDK
builds, core/peer/frame-wait/WGL tests and exact header fingerprint verification in
[run 38574633107](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/38574633107).
[Run 38574633198](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/38574633198)
passed Windows core/process tests, Linux core/peer/frame-wait/process/Mesa GPU
tests, both Linux SDK builds, surface interchange and ParaView host tests.

## WGL context callbacks: 2026-10-14, r3

The r2 diagnostics from the user's Windows PC confirmed that the exact invited
Visualizer was observed in UNKNOWN state and its volume was created. The runtime
then received a 1920 x 1080 stream request, but `qar_render_sender_create` failed:
`BackendTransformNotSupported` during OpenGL/Vulkan setup, with the nested error
`Could not load OpenGL function: glGetStringi`. The sender caught this error and
closed its volume/session. No frame was submitted. The collector found no Windows
Application crash event. That absence alone is not proof that no viewer crashed.

Commit `3b560c184f34fa124cc204c11dfdc03e21f1b13e` supplies the exact legacy
header's optional WGL callbacks: bind, unbind, capture/restore and function
resolution. The resolver uses `wglGetProcAddress` with the supplied context
current, and `opengl32.dll` exports for OpenGL 1.1 functions. It never relies on
GLFW's current-window state on a runtime-owned thread. Callback data and handles
outlive the SDK. Before session startup a separate worker checks GL_VERSION,
glGetStringi availability and Win32 import entry points, then restores its binding.
After sender creation the log records whether the SDK actually used these callbacks.

The Windows `wgl-callback` test uses real basic WGL contexts, without QAROS or VTK,
to exercise worker binding, export resolution, rejection of another context and
restoration of both an existing and empty binding. It does not require OpenGL 3.3
or claim NVIDIA/Vulkan interoperability. The r3 live SDK result remains to be
verified on the user's PC; failure may require a runtime loader fix.

Windows native [run 38572186047](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/38572186047)
passed both SDK builds, core/legacy-peer/WGL callback tests and exact SDK fingerprint
verification. [Run 38572186585](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/38572186585)
also passed Windows core/process/WGL tests, Linux core/peer/process/Mesa GPU tests,
both Linux SDK compile branches, surface interchange and ParaView host tests.

## Legacy Visualizer startup: 2026-10-14

The supplied session SDK header has SHA-256
`022c40b670f87a066664c37daeb06da525db37fffdf5810e72cff8a5b81e677d`.
The local Windows preview worked on the user's NVIDIA RTX 2070 Max-Q. The first
streaming attempt opened a blank Visualizer and ended with `Invited viewer did
not reach RUNNING before timeout`, before the OpenGL sender was created.
Its log also reported a session without persistent storage.

Commit `f290dca3784b7af499f0ed2af5a70b3124f86071` follows the startup sequence
already used in the BANC bridge: subscribe to peer updates before invitation,
accept an observation of the exact invited id even when its state is UNKNOWN,
wait two seconds for receiver subscriptions, and create the volume with its
initial viewer assigned. Other peers cannot satisfy this wait. A shutting-down
viewer aborts startup. Legacy session teardown now leaves the session explicitly.

The `legacy-peer` regression test covers early UNKNOWN observations, unrelated
RUNNING peers and later state changes without loading QAROS. Runtime-free tests
and compilation cannot verify Visualizer display or NVIDIA frame transport.
The updated starter still requires a real streaming test on the user's PC.

Both SDK branches compiled successfully on Windows in
[run 38568711354](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/38568711354).
The session EXE reported the exact header hash above and `modern_api: 0`.
Core and legacy-peer tests passed there. In
[run 38568710889](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/38568710889),
Linux core/peer/process/GPU tests, preview smoke, both SDK compile branches,
surface interchange, Windows core/process tests and ParaView host tests passed.

## Evidence recorded on 2026-10-09

| Check | Result / scope |
| --- | --- |
| Core math/layout on Linux | PASS locally and in CI |
| Core math/layout on Windows | PASS in CI (MSVC) |
| Plugin process controller on Linux and Windows | PASS: real child process fixture, stdin pairing, identity reuse, Stop/restart, per-instance isolation, SDK mismatch rejection |
| Native VTK/OpenGL build on Ubuntu 24.04 | PASS in CI |
| GPU copy test on Mesa/Xvfb | PASS: D32F and R32F, 128/256 px, two shared contexts, stereo disparity, flips, alpha, depth, state restoration |
| Preview | PASS: five-frame hidden run in CI |
| Modern SDK sender | PASS: Linux compile/link and `--sdk-info`, no runtime loaded |
| Legacy 2540 SDK sender | PASS: Linux C++ syntax check against actual package header; no link/runtime claim |
| Surface interchange | PASS: real VTK round-trip, baked world transform, triangulation, input unchanged, invalid export preserves previous file |
| ParaView host smoke | PASS in ParaView 5.11.2 on Ubuntu: export, display transform and original active source |
| Windows native VTK/sender | PASS: Release build and core tests in run 37986750101, commit d16e50cb (2026-10-09). No Windows GPU/Hub/headset test |
| Packaged Slicer plugin | PASS in official Slicer 5.12.4 on Ubuntu: module discovery, model/segment transforms, Start/Update/Stop with process fixture, cleanup without module-load/shutdown errors |
| Packaged ParaView plugin | PASS in official ParaView 5.12.1: real plugin loader, pipeline update, Start/Stop/restart with process fixture; locally and in Linux CI |
| Slicer CMake extension/CPack route | Entry point prepared; not built against a Slicer development tree. Tested installation is the packaged scripted module via Additional module paths |
| Hub / encoder / headset | Not run: no matching live runtime and supported NVIDIA device in this environment |

The first complete renderer test is [run 37949911874](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37949911874).
The sender/interchange Linux build is [run 37951256265](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37951256265).
The ParaView test is [run 37952481684](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37952481684).
The Slicer test is [run 37952928419](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37952928419).
Packaged plugin code revision **8e49a56** passed the Slicer test in
[run 37987779396](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37987779396)
and the ParaView plugin job in
[run 37987779352](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37987779352).
That ParaView job also uploaded the portable Python plugin ZIP. The process
fixture used by these tests is deliberately a test double; it neither loads
QAROS nor proves pairing, video transport, encoding or headset output.

The first packaged-plugin attempt exposed Ubuntu 24.04's ParaView 5.11.2 /
Python 3.12 loader incompatibility (`inspect.getargspec`). CI and the install
guide now use the official ParaView 5.12.1 bundle with its matching Python 3.10.
The official Linux archive is pinned by SHA-256:
`cd8d4b4dada44c8f36dc17e676cc5d8ae6b0a3c0449da9092e9df8bb8b5d48e7`.

The full Windows build is [run 37952481497](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37952481497);
it was cancelled after the 60-minute limit while vcpkg was compiling Debug VTK.
The workflow now builds Release only, with a 180-minute cold-build limit.
Runs [37985668990](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37985668990)
and [37986750101](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37986750101) both completed successfully. The 2026-10-14 Windows starter uses the latter run's unchanged binaries.
See [all runs](https://github.com/HonzaHovora/QAROS_VTK/actions) for the current commit;
these historic passes must not be read as proof for later untested changes.

Inspected SDK header fingerprints:

- Modern pinned public header: `00f96316f50ad9c7e1e94daaf9a229e704fffb1acf89aa2a585af32dde000069`
- Package 2540 header: `c709c479cc6a1acc0040fb61a071cc7bc16e65bf5acb90d624d9d6b0a6fcd3c1`

The packaged Windows build reports header SHA-256
`eed88c1e4a6c8038a96038e1850deee3241e3f3c460fd24a10c3706f1df599d9`.
For that binary, use its `--sdk-info` / bundled `qarvtk-sdk.json` rather than a
fingerprint from a different build. Exact header byte matching is required.

## Reproduce

```bash
cmake --preset core
cmake --build --preset core
ctest --preset core
python tests/test_bridge.py             # Python with VTK
xvfb-run -a env LIBGL_ALWAYS_SOFTWARE=1 bash scripts/build-linux.sh
pvpython tests/paraview_smoke.py         # ParaView's own interpreter
# Packaged plugin host tests: see HOST_INTEGRATIONS.md
```

For a local SDK compile, use `bash scripts/build-linux.sh /path/to/sdk`; actual
streaming on Linux additionally requires a native QAROS runtime and supported
hardware. Windows commands are in [WINDOWS.md](WINDOWS.md).

## Definition of the next milestone

One Windows/NVIDIA machine runs a build against its installed SDK; a compatible
QAROS viewer receives a correctly scaled stereo cube with valid depth. A Slicer
model or segment then replaces the cube, preserving RAS orientation and mm-to-m
scale. Updating the surface from the plugin changes it; shutdown/reconnect behaves as documented. Record
screenshots and logs with version/GPU details. Only then call the end-to-end
prototype validated.

## Known constraints

- One viewer, one opaque surface, fixed green color, no text/overlays.
- Installed plugins control the sender; geometry exchange remains a file snapshot, not in-process host rendering.
- No CT/MR volume rendering, transfer functions, picking or bidirectional gestures.
- Fixed clip range and fixed initial app-volume placement; no auto-fit.
- Single-sample 2D textures; no array layers, Vulkan import, reverse-Z or HDR.
- Conservative `glFinish`, no performance/latency claim or clinical validation.
- No Wayland/EGL sender path or macOS sender implementation.
- Portable Python plugin folders/ZIP are provided; no official catalog release,
  automatic update or QAROS runtime redistribution. Backend builds are separate.

The file/CPU scene exchange is intentional for this first stage; the per-frame
pixel path stays on the GPU. A future in-process adapter must match its host's
exact VTK/Qt ABI and adopt the host's render-thread lifecycle.


