# Architecture

## Data and frame paths

Host path: a Slicer scripted module or a ParaView Python pipeline plugin controls
one child sender through `integrations/qarvtk_runtime.py`. The plugins and backend
are separate installable components from the start.

Scene path: Slicer exports lit models/segments and one scalar CT/MR volume as
an atomic `.vtm` manifest with immutable VTP/VTI payloads. Surface transforms
are baked in world RAS mm; volume physical spacing and its image-to-world
matrix are retained. Colors, opacity and transfer-function nodes are explicit
field data. ParaView retains its surface-only `.vtp` path. CPU/file work happens
on publication/reload, never per video frame.

Frame path: QAROS begin-frame → SDK camera pose/FOV for each eye → VTK color/depth
FBO → two shader copies per eye to SDK-owned textures → `glFinish` → show-frame.
No video pixels are read back to CPU by production code. Tests read texture data
only to compare it with known geometry. This is GPU-to-GPU copying, **not** zero-copy.

`glFinish` is deliberately conservative for the first shared-context prototype.
It blocks for completion and must be profiled with the real encoder; fences or
SDK-supported external synchronization are a later optimization. A GLFW preview
blit is optional and not part of the stream.

## Coordinates and depth

- Content coordinates: right-handed, metres, +Y up, camera forward −Z.
- SDK quaternion order: x, y, z, w. Each eye uses its own pose and asymmetric FOV.
- SDK poses are already in app content space. Do not reapply volume transforms.
- VTK explicit projection uses OpenGL NDC depth −1…+1. Texture depth is 0…1,
  conventional near-to-far, and is sent unchanged with matching near/far.
- Current clipping: 0.05–20 app metres, `depth_scale=1`. No reverse-Z.
- Slicer: export world RAS mm, then `(x,y,z) → 0.001 × (x,z,−y)` in the renderer.
  This is a proper axis rotation preserving handedness. Parent MRML transforms
  are baked before unit/axis conversion.
- ParaView plugin: preserve pipeline coordinates; set Metres Per Unit explicitly.
  Use an upstream Transform filter. Display-only Position/Scale/Orientation are
  not included by the plugin. The older `export_active` convenience helper also
  bakes the active view's display transform. The sender assumes Y-up unless
  `--ras` is selected.

Slicer defaults to the explicitly labelled Center and fit option: one common
transform centers all scene objects and maps the longest bound to 0.65 m.
Disabling it preserves physical size and world position. Original `.vtp` imports
keep their original position and command-line unit scale.

## Texture contract

The sender requests separated LEFT color/depth and RIGHT color/depth textures.
It consumes returned metadata rather than assuming texture/view order. Layout
validation rejects missing/duplicate eyes or planes, bounds violations, overlap,
zero handles, oversized textures and array layers. Reversed rectangle corners
are treated as flips. Color and depth dimensions may differ; sampling covers
each destination rectangle.

The sender negotiates RGBA8 and D32_FLOAT and accepts R32_FLOAT depth if reported.
The GL copy validates actual shared texture handles, dimensions and internal
formats. The lower-level copier handles native depth or R32F color attachments;
MSAA is disabled. Layered textures, external-memory import from Vulkan, and
multisampled targets are not supported.

Copy operations restore the GL state they modify. VTK's normal framebuffer and
shader state remain intact. The output background is transparent with depth 1.
Surfaces use camera-relative key/fill/back lights and Phong normals. The volume
uses vtkOpenGLGPUVolumeRayCastMapper in RenderToImage mode. Its color and
first nonzero-opacity sample depth are GPU textures; GlComposite combines them
with the surface framebuffer without CPU readback. Opaque surface depth terminates
rays. Empty rays have depth 1. Culling is disabled so each eye's offscreen image
is cleared even when a volume is outside the view.

One depth sample approximates a translucent volume; it cannot encode every
contributing tissue layer. One scalar volume with opaque surfaces is supported;
translucent surface/volume combinations are rejected by the exporter. ROI/MIP,
multiple volumes, tone mapping and color-space calibration remain future work.

## Plugin boundary and process protocol

ParaView and Slicer package different VTK/Qt versions. Loading an independently
built VTK library into either process risks ABI and graphics-context conflicts.
Python host plugins control the existing renderer without loading the SDK or
another VTK into the host. The C++ `Renderer::set_polydata` entry point is available
for a later native adapter but is not ABI-safe across unrelated VTK builds.

Protocol 2 adds scene/volume snapshots; protocol 1 remains readable for the
legacy ParaView/VTP route. The process contract consists of:

- `--sdk-info`: JSON with exact header SHA-256, `modern_api` and `plugin_protocol`.
  The plugin checks these and the presence of the platform runtime before launch.
- A private working directory per instance, atomically updated `scene.vtp` or `scene.vtm`, and
  `--watch`. Only scene updates use CPU/files; every video frame stays on GPU.
- `--stop-file`: the owner requests cooperative shutdown by creating its own file.
  `--parent-pid` terminates the render/wait loop if the host disappears. Windows
  holds a process handle; Linux checks whether the parent PID still exists.
- Pairing code on stdin, a persistent identity outside the checkout, and a log.
  The Slicer UI clears the code after launch. ParaView reuses prior pairing so
  that no code is stored as a pipeline property in a saved state.
- Explicit Start commands only: loading a Slicer scene or a ParaView state never
  starts streaming automatically. `running` reports process liveness, not a
  confirmed viewer connection.

SDK calls can block until their configured 60-second timeout. Slicer's Stop
requests shutdown without blocking the UI; polling enforces a 65-second deadline.
Cleanup/ParaView Stop waits up to three seconds before killing an unresponsive
child. That fallback cannot guarantee SDK-side cleanup. Private geometry is
deleted on cleanup, logs are retained for diagnosis. A host crash can leave a
temporary VTP/VTI generations; no patient data belongs in the repository.

Slicer settings hold paths and host name, not pairing codes. Its optional one-second
publication is intentionally opt-in and skips unchanged surfaces. Volumes update
only on Start/Update scene. Immutable generations are kept until cleanup to avoid
racing an in-progress reader; repeated manual CT updates use additional disk.
All generation folders are removed when the owning backend closes.
ParaView publishes on pipeline updates, supports only the local built-in session,
and rejects pvserver/MPI execution before writing a scene or starting a process.

`scripts/package_plugins.py` copies an explicit allowlist into self-contained
host folders. It bundles neither the SDK nor backend binaries. The Slicer CMake
extension entry point supports the standard developer packaging route; the ZIP
is a portable manual-install bundle, not an Extensions Manager package.

## Next integration stages

1. Validate end-to-end WGL → QAROS → viewer with known cube dimensions/depth.
2. Repeat the Linux-validated ParaView/Slicer host smoke scripts on the target
   Windows installations and verify the resulting stream in the viewer.
3. Extend scenes with ROI clipping, translucent surface/volume composition,
   multiple volumes and bounded acknowledged snapshot retention.
4. Build a native ParaView view plugin against a pinned ParaView version, using
   render requests and host pipeline updates instead of VTP snapshots.
5. Extend the Slicer plugin with debounced MRML change observation, medical
   volume/segmentation visibility and calibrated world transforms; publish a
   validated extension package.
6. Add per-viewer senders/cameras, picking/gestures, then benchmark and replace
   conservative synchronization where the SDK contract permits it.

OpenGL is the shortest path for the existing VTK OpenGL2 backend. QAROS's existing
Vulkan support can be used by another renderer later; this repo does not add a
second backend or claim a working Vulkan/VTK path.
