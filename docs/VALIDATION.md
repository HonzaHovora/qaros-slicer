# Validation and next work

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
| Windows native VTK/sender | Original Debug + Release build timed out; Release-only rebuild in progress (not an end-to-end runtime test) |
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
and [37986750101](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37986750101) track the replacement builds.
See [all runs](https://github.com/HonzaHovora/QAROS_VTK/actions) for the current commit;
these historic passes must not be read as proof for later untested changes.

Inspected SDK header fingerprints:

- Modern pinned public header: `00f96316f50ad9c7e1e94daaf9a229e704fffb1acf89aa2a585af32dde000069`
- Package 2540 header: `c709c479cc6a1acc0040fb61a071cc7bc16e65bf5acb90d624d9d6b0a6fcd3c1`

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
