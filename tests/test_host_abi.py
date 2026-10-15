"""Validate the DLL ABI without a QAROS runtime or a supported XR GPU."""
import ctypes as c
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "slicer"))
from qarvtk_host_runtime import Placement

dll = c.CDLL(sys.argv[1])
dll.qarvtk_host_info.restype = c.c_char_p
info = json.loads(dll.qarvtk_host_info())
assert info == dict(host_abi=2, modern_api=0,
    header_sha256="022c40b670f87a066664c37daeb06da525db37fffdf5810e72cff8a5b81e677d",
    eye_size=104, frame_size=232, placement_size=64)
dll.qarvtk_host_create.argtypes = [c.c_char_p, c.c_char_p, c.c_char_p, c.POINTER(Placement), c.POINTER(c.c_void_p), c.c_char_p, c.c_uint32]
dll.qarvtk_host_create.restype = c.c_int
for _ in range(2):
    placement = Placement((c.c_double*3)(0, 0, 0), (c.c_double*4)(0, 0, 0, 1), 1.)
    handle = c.c_void_p()
    error = c.create_string_buffer(1024)
    result = dll.qarvtk_host_create(b"no-runtime", b"visualizer", b"unused", c.byref(placement), c.byref(handle), error, len(error))
    assert result == -1 and not handle.value
    assert b"Make the Slicer render window current" in error.value, error.value
dll.qarvtk_host_destroy.argtypes = [c.c_void_p]
dll.qarvtk_host_destroy.restype = c.c_int
assert dll.qarvtk_host_destroy(None) == 1
print("PASS: VTK-free DLL loads; ABI metadata; missing host context fails cleanly and can be retried")
