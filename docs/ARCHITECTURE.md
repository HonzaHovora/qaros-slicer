# Architecture

## Data and frame paths

Host snapshot path: ParaView active surface or Slicer model/segment → world
transform → triangulated `.vtp` written atomically → standalone VTK scene.
This is a CPU/file geometry transfer only on export or reload, not on every video
frame. Host appearance and volume rendering are not transferred.

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
- ParaView: preserve world coordinates; choose `--meters-per-unit` explicitly if
  they are not metres. Source pipeline transforms and display transforms are
  included. The sender currently assumes Y-up unless `--ras` is selected.

The scene is one opaque green surface at its original position; it is not
silently centered or resized. The demo cube is centered at the content origin.

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
The current unlit surface emits fixed RGB values; tone mapping, color-space
conversion, translucent surfaces, clinical transfer functions and multi-layer
occlusion need separate design and validation.

## Why standalone first

ParaView and Slicer package different VTK/Qt versions. Loading an independently
built VTK library into either process risks ABI and graphics-context conflicts.
The file bridge allows us to validate QAROS's frame and synchronization contract
before building native host plugins against each host's exact source/version.
The C++ `Renderer::set_polydata` entry point is a starting point for a future
adapter, but it is not ABI-safe across unrelated VTK builds.

## Next integration stages

1. Validate end-to-end WGL → QAROS → viewer with known cube dimensions/depth.
2. Verify the two host exports in their actual applications; automate their
   smoke scripts in the supported host environments.
3. Add a scene abstraction for actors, colors, transforms and volumes.
4. Build a native ParaView view plugin against a pinned ParaView version, using
   render requests and host pipeline updates instead of VTP snapshots.
5. Build a Slicer extension against its pinned VTK/Qt: MRML change observation,
   medical volume/segmentation visibility and calibrated world transforms.
6. Add per-viewer senders/cameras, picking/gestures, then benchmark and replace
   conservative synchronization where the SDK contract permits it.

OpenGL is the shortest path for the existing VTK OpenGL2 backend. QAROS's existing
Vulkan support can be used by another renderer later; this repo does not add a
second backend or claim a working Vulkan/VTK path.
