#!/usr/bin/env bash
# Optional Linux -> Windows x64 build; the usual MSVC CMake build also works.
set -euo pipefail
cd "$(dirname "$0")/.."
qarvtk_cxx="${QARVTK_CXX:-x86_64-w64-mingw32-g++-posix}"
qarvtk_strip="${QARVTK_STRIP:-x86_64-w64-mingw32-strip}"
qarvtk_sdk="ci/sdk-headers/session-022c40b6"
qarvtk_hash="022c40b670f87a066664c37daeb06da525db37fffdf5810e72cff8a5b81e677d"
test "$(sha256sum "$qarvtk_sdk/include/qar_streaming.h" | cut -d' ' -f1)" = "$qarvtk_hash"
mkdir -p build-host-cross
"$qarvtk_cxx" -std=c++17 -O2 -shared -static -static-libgcc -static-libstdc++ -pthread \
  -Iinclude -I"$qarvtk_sdk/include" -DQARVTK_HOST_GL -DQARVTK_HOST_EXPORTS \
  -DQAR_ENABLE_OPENGL -DQAR_ENABLE_DYNAMIC_LOADING -DNOMINMAX -DWIN32_LEAN_AND_MEAN \
  "-DQARVTK_HOST_SDK_HASH=\"$qarvtk_hash\"" \
  src/host_bridge.cpp src/host_panels.cpp src/host_gl.cpp src/gl_copy.cpp \
  src/gl_composite.cpp src/layout.cpp src/math.cpp src/shutdown.cpp \
  -o build-host-cross/qarvtk-host.dll -lopengl32 -lgdi32 -luser32 -Wl,--no-insert-timestamp
"$qarvtk_strip" --strip-unneeded build-host-cross/qarvtk-host.dll
sha256sum build-host-cross/qarvtk-host.dll
