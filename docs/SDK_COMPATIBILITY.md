# SDK compatibility

CMake inspects the chosen **local** `include/qar_streaming.h` and selects the
onboarding API when it contains `qar_runtime_onboard`. Otherwise it builds the
legacy session branch. This distinguishes the two inspected API generations; it
is not a promise of compatibility with arbitrary future V0 headers.

| API generation | Source inspected | Connection path |
| --- | --- | --- |
| Legacy | QAROS `0.9.0-dev.2540+1ed038e4` package | Create/serialize/join session, invite target, add volume |
| Supplied session SDK | Exact header `022c40b670f87a066664c37daeb06da525db37fffdf5810e72cff8a5b81e677d` | Same session branch; Windows sender compiled separately for these exact bytes |
| Modern | [Quaternar/qaros at 678e5463](https://github.com/Quaternar/qaros/blob/678e5463bb14a9d4d1f681fcdb9dfab9fe61e77e/qar-streaming-c/include/qar_streaming.h) | Hub onboarding/rejoin, get-or-create volume, subscribe to render requests |

Both use `QAR_ENABLE_OPENGL`, dynamic loading, an adopted shared WGL/GLX context,
`qar_render_sender_try_begin_frame`, `qar_render_sender_frame_opengl`, per-view
pose/FOV, `qar_render_sender_show_frame`, and frame info destruction.

The OpenGL context extension is detected separately from the session API.
The supplied `022c40b6` header uses `QarStreamParamsOpenGl`, with an explicit
WGL/GLX discriminator and native context fields. Newer headers split these into
`QarStreamParamsOpenGlWgl` and `QarStreamParamsOpenGlGlx`. CMake selects the
matching structs and default initializers; there are no casts between their
different ABI layouts. Both variants retain the separate SDK-owned shared context.

The selected adapter is read from OpenGL `GL_EXT_memory_object` (LUID on Windows,
UUID on Linux) and chained into session creation/join or onboarding/rejoin.
The inspected SDK documents NVIDIA-only support. Mesa is used only for the
renderer/copy tests; these tests do not invoke QAROS.

## Linux header issue

Both inspected headers emit `__declspec(dllimport)` declarations even on Linux.
The sender temporarily suppresses this Windows declaration annotation only while
including the header under GCC/Clang, using push/pop macro. The original header,
struct layout, symbol names and dynamic loader are unchanged. This allows compile
coverage; it does not establish availability or correctness of a Linux runtime.
Remove this compatibility block when upstream provides portable declarations.

## Ownership and cancellation

The render context is owned by the application's main thread. A second GLFW
context in the same share group is reserved for the SDK graphics thread. Its
window/native handles outlive the sender and SDK. The SDK's default native context
callbacks are used; the application never tries to bind that context while the
SDK is running.

Modern callback state is mutex-protected and outlives cancellation and SDK
shutdown. Callbacks only copy the first target peer ID and destroy the request;
they never call VTK/OpenGL. Frame info uses RAII. A frame failure terminates and
destroys the sender instead of inventing an unsupported abort-frame call.
Onboarding/rejoin, target invitations and sender creation use cancellation
timeouts, as do periods without frames. Runtime initialization and the legacy
create/join calls expose no cancellation token in the inspected API. First-run
human pairing input can wait until the user enters a code or closes stdin.

Modern volumes use a unique per-run common name, so shutdown closes only the
volume created by this process. The prototype does not yet persist a stable
volume identity across runs. Rejoin identity is persisted separately.

## Version discipline

Use `scripts/run_sender.py`: it compares the header hash against `--sdk-info`.
Never replace the header without the matching runtime binaries. The check
cannot detect a manually mixed set of DLLs with an unchanged header.
No SDK runtime binaries or invite files are vendored here. Modern CI downloads
the pinned public header for compilation. The user-supplied session header is
preserved unchanged in `ci/sdk-headers/session-022c40b6/include/qar_streaming.h`
so CI can reproduce a sender for the installed SDK. Git preserves its exact
bytes, including LF line endings, on Windows. This header alone does not install
an SDK or establish a runtime test result.
