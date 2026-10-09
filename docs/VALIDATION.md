# Validation and next work

## Evidence recorded on 2026-10-09

| Check | Result / scope |
| --- | --- |
| Core math/layout on Linux | PASS locally and in CI |
| Core math/layout on Windows | PASS in CI (MSVC) |
| Native VTK/OpenGL build on Ubuntu 24.04 | PASS in CI |
| GPU copy test on Mesa/Xvfb | PASS: D32F and R32F, 128/256 px, two shared contexts, stereo disparity, flips, alpha, depth, state restoration |
| Preview | PASS: five-frame hidden run in CI |
| Modern SDK sender | PASS: Linux compile/link and `--sdk-info`, no runtime loaded |
| Legacy 2540 SDK sender | PASS: Linux C++ syntax check against actual package header; no link/runtime claim |
| Surface interchange | PASS: real VTK round-trip, baked world transform, triangulation, input unchanged, invalid export preserves previous file |
| ParaView host smoke | PASS in ParaView 5.11.2 on Ubuntu: export, display transform and original active source |
| Windows native VTK/sender | Original Debug + Release build timed out; Release-only rebuild in progress (not an end-to-end runtime test) |
| Slicer host UI/segmentation smoke | PASS in Slicer 5.12.4 on Ubuntu: model, segment, world transform and widget creation |
| Hub / encoder / headset | Not run: no matching live runtime and supported NVIDIA device in this environment |

The first complete renderer test is [run 37949911874](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37949911874).
The sender/interchange Linux build is [run 37951256265](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37951256265).
The ParaView test is [run 37952481684](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37952481684).
The Slicer test is [run 37952928419](https://github.com/HonzaHovora/QAROS_VTK/actions/runs/37952928419).
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
scale. Re-export updates it; shutdown/reconnect behaves as documented. Record
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
