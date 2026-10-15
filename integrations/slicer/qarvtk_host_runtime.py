"""ctypes boundary to the VTK/Qt-free, in-process Windows GPU transport."""
import ctypes as c
import hashlib
import json
import os
from pathlib import Path

EXPECTED_SDK = "022c40b670f87a066664c37daeb06da525db37fffdf5810e72cff8a5b81e677d"
_libraries = {}  # Never unload a DLL while an SDK callback may still use it.


class Eye(c.Structure):
    _fields_ = [("position", c.c_double * 3), ("orientation", c.c_double * 4),
                ("fov", c.c_double * 4), ("width", c.c_uint32), ("height", c.c_uint32)]


class Frame(c.Structure):
    _fields_ = [("serial", c.c_uint64), ("eyes", Eye * 2)]


def library(path):
    path = str(Path(path).resolve())
    if path in _libraries:
        return _libraries[path]
    dll = c.CDLL(path)
    dll.qarvtk_host_info.restype = c.c_char_p
    info = json.loads(dll.qarvtk_host_info())
    if (info.get("host_abi"), info.get("header_sha256"), info.get("modern_api"),
        info.get("eye_size"), info.get("frame_size")) != (1, EXPECTED_SDK, 0, c.sizeof(Eye), c.sizeof(Frame)):
        raise RuntimeError("Host DLL ABI or SDK fingerprint does not match this plugin")
    signatures = {
        "create": ([c.c_char_p, c.c_char_p, c.c_char_p, c.POINTER(c.c_void_p), c.c_char_p, c.c_uint32], c.c_int),
        "poll": ([c.c_void_p, c.POINTER(Frame)], c.c_int),
        "color": ([c.c_void_p, c.c_uint64] + [c.c_uint32] * 5, c.c_int),
        "depth": ([c.c_void_p, c.c_uint64] + [c.c_uint32] * 7, c.c_int),
        "finish": ([c.c_void_p, c.c_uint64], c.c_int),
        "stop": ([c.c_void_p], None),
        "destroy": ([c.c_void_p], c.c_int),
        "status": ([c.c_void_p, c.c_char_p, c.c_uint32], None),
    }
    for name, (args, result) in signatures.items():
        function = getattr(dll, "qarvtk_host_" + name)
        function.argtypes, function.restype = args, result
    _libraries[path] = dll
    return dll


class HostTransport:
    def __init__(self, dll_path, sdk_root, target, log_folder, host_view):
        if os.name != "nt":
            raise RuntimeError("Live QAROS transport currently requires Windows x64")
        sdk = Path(sdk_root).resolve()
        header = sdk / "include" / "qar_streaming.h"
        if not header.is_file() or hashlib.sha256(header.read_bytes()).hexdigest() != EXPECTED_SDK:
            raise RuntimeError("SDK header differs from the host DLL; select the complete matching D:/install SDK")
        self.host = host_view
        self.dll = library(dll_path)
        self.handle = c.c_void_p()
        self.frame = Frame()
        self.stopping = False
        self.last_status = "Starting live host transport"
        self.log_folder = Path(log_folder)
        self.host.window.MakeCurrent()
        error = c.create_string_buffer(2048)
        result = self.dll.qarvtk_host_create(str(sdk).encode("utf-8"), target.encode("utf-8"),
            str(self.log_folder).encode("utf-8"), c.byref(self.handle), error, len(error))
        if result != 0:
            raise RuntimeError(error.value.decode("utf-8", "replace"))

    @property
    def running(self):
        return bool(self.handle.value)

    def status(self):
        if self.running:
            text = c.create_string_buffer(2048)
            self.dll.qarvtk_host_status(self.handle, text, len(text))
            self.last_status = text.value.decode("utf-8", "replace")
        return self.last_status

    def _check(self, result):
        if result != 0:
            raise RuntimeError(self.status())

    def color(self, index, color, depth, width, height):
        self._check(self.dll.qarvtk_host_color(self.handle, self.frame.serial, index,
            color.GetHandle(), depth.GetHandle(), width, height))

    def depth(self, index, color, depth, vc, vd, width, height):
        self._check(self.dll.qarvtk_host_depth(self.handle, self.frame.serial, index,
            color.GetHandle(), depth.GetHandle(), vc.GetHandle() if vc else 0,
            vd.GetHandle() if vd else 0, width, height))

    def tick(self):
        if not self.running:
            return
        if self.stopping:
            self.status()
            if self.dll.qarvtk_host_destroy(self.handle):
                self.handle = c.c_void_p()
                self.last_status = "Stopped. " + self.last_status
            return
        result = self.dll.qarvtk_host_poll(self.handle, c.byref(self.frame))
        if result < 0:
            error = self.status()
            self.request_stop()
            raise RuntimeError(error)
        if result == 2:
            self.request_stop()
            return
        if result == 0:
            return
        eyes = [dict(position=tuple(eye.position), orientation=tuple(eye.orientation),
                     fov=tuple(eye.fov), size=(eye.width, eye.height)) for eye in self.frame.eyes]
        try:
            self.host.render(eyes, self)
            self._check(self.dll.qarvtk_host_finish(self.handle, self.frame.serial))
        except Exception:
            self.request_stop()
            raise

    def request_stop(self):
        if self.running and not self.stopping:
            self.stopping = True
            self.dll.qarvtk_host_stop(self.handle)
