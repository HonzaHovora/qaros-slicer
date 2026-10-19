# Exact headers used for session builds

`session-c709c479/include/qar_streaming.h` is the unmodified 256428-byte header
supplied on 2026-10-19 from `QAROS-0.9.0-dev.2540+1ed038e4`.
SHA256: `c709c479cc6a1acc0040fb61a071cc7bc16e65bf5acb90d624d9d6b0a6fcd3c1`.
It retains session invites but splits OpenGL context parameters into WGL/GLX/EGL
structures and changes the gesture API. The Live update targets these exact bytes.
See [the update guide](../../docs/QAROS_DEV2540_UPDATE.md).

`session-022c40b6/include/qar_streaming.h` is the unmodified header supplied
from the existing Windows QAROS installation on 2026-10-14. It contains the
session invite API and OpenGL sender API, not the modern Hub onboarding API.

- SHA256: `022c40b670f87a066664c37daeb06da525db37fffdf5810e72cff8a5b81e677d`
- Size: 191192 bytes
- Original runtime version: not inferred from the header

This is a compile fixture. Do not copy it into a different SDK installation.
The runtime, viewer and all required QAROS DLLs must remain from the matching
installed package. The plugin still checks the installed header against the
sender's embedded hash. CI also verifies this hash before and after compilation.

The modern sender remains a separate CI artifact compiled from the pinned
upstream public header. No runtime DLLs or session credentials are included here.
