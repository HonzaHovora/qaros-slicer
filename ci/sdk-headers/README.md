# Exact header used for the session sender

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
