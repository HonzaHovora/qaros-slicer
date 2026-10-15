"""ctypes boundary to the VTK/Qt-free, in-process Windows GPU transport."""
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from datetime import datetime, timezone

EXPECTED_SDK = "022c40b670f87a066664c37daeb06da525db37fffdf5810e72cff8a5b81e677d"
_libraries = {}  # Never unload a DLL while an SDK callback may still use it.


class HostTimingLog:
    """Five-second wall-time averages. No readback, GPU queries or extra waits."""
    def __init__(self, folder):
        self.path = Path(folder) / "host-python.log"
        self.started = None
        self.count = 0
        self.sums = {}
        self.last_serial = 0
        self.eye_sizes = []
        self.render_sizes = []
        self.depth_sizes = []
        self.desktop_size = []

    def event(self, message):
        try:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(datetime.now(timezone.utc).isoformat(timespec="milliseconds") + " " + message + "\n")
        except OSError:
            pass  # A diagnostic write must not invalidate a live SDK frame.

    def record(self, serial, timings, eyes, started, render_sizes=None, desktop_size=None):
        if self.started is None:
            self.started = started
        self.count += 1
        self.last_serial = serial
        self.eye_sizes = [list(eye["size"]) for eye in eyes]
        self.depth_sizes = [list(eye.get("depth_size", eye["size"])) for eye in eyes]
        self.render_sizes = [list(size) for size in (render_sizes or self.eye_sizes)]
        self.desktop_size = list(desktop_size or [])
        for key, value in timings.items():
            self.sums[key] = self.sums.get(key, 0.) + value
        self.flush()

    def flush(self, force=False):
        if not self.count:
            return
        now = perf_counter()
        elapsed = now - self.started
        if not force and elapsed < 5:
            return
        record = dict(frames=self.count, last_serial=self.last_serial,
                      rendered_fps=round(self.count / max(elapsed, 1e-9), 2), eye_sizes=self.eye_sizes,
                      depth_sizes=self.depth_sizes, render_sizes=self.render_sizes, desktop_size=self.desktop_size)
        record.update({key: round(value / self.count, 3) for key, value in self.sums.items()})
        self.event("PERF_HOST " + json.dumps(record, sort_keys=True))
        self.started = now
        self.count = 0
        self.sums = {}


class Placement(c.Structure):
    _fields_ = [("position", c.c_double * 3), ("orientation", c.c_double * 4), ("app_scale", c.c_double)]


class Eye(c.Structure):
    _fields_ = [("position", c.c_double * 3), ("orientation", c.c_double * 4),
                ("fov", c.c_double * 4), ("width", c.c_uint32), ("height", c.c_uint32),
                ("depth_width", c.c_uint32), ("depth_height", c.c_uint32)]


class Frame(c.Structure):
    _fields_ = [("serial", c.c_uint64), ("eyes", Eye * 2), ("near_plane", c.c_double), ("far_plane", c.c_double)]


def library(path):
    path = str(Path(path).resolve())
    if path in _libraries:
        return _libraries[path]
    dll = c.CDLL(path)
    dll.qarvtk_host_info.restype = c.c_char_p
    info = json.loads(dll.qarvtk_host_info())
    if (info.get("host_abi"), info.get("header_sha256"), info.get("modern_api"),
        info.get("eye_size"), info.get("frame_size"), info.get("placement_size")) != (2, EXPECTED_SDK, 0, c.sizeof(Eye), c.sizeof(Frame), c.sizeof(Placement)):
        raise RuntimeError("Host DLL ABI or SDK fingerprint does not match this plugin")
    signatures = {
        "create": ([c.c_char_p, c.c_char_p, c.c_char_p, c.POINTER(Placement), c.POINTER(c.c_void_p), c.c_char_p, c.c_uint32], c.c_int),
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
        self._ticking = False
        self.last_status = "Starting live host transport"
        self.resolution_status = "Waiting for viewer resolution"
        self.log_folder = Path(log_folder)
        self.host.window.MakeCurrent()
        error = c.create_string_buffer(2048)
        placement = Placement((c.c_double*3)(*self.host.app_position),
                              (c.c_double*4)(*self.host.app_orientation), self.host.app_scale)
        result = self.dll.qarvtk_host_create(str(sdk).encode("utf-8"), target.encode("utf-8"),
            str(self.log_folder).encode("utf-8"), c.byref(placement), c.byref(self.handle), error, len(error))
        if result != 0:
            raise RuntimeError(error.value.decode("utf-8", "replace"))
        self.diagnostics = HostTimingLog(self.log_folder)
        self.diagnostics.event("r13 SDK app_pose/app_scale and half-resolution depth; "
                               "wall times include existing GPU waits; "
                               "native copy/sync timings overlap Python copy calls")
        self.diagnostics.event("PLACEMENT " + json.dumps(dict(app_position=self.host.app_position,
            app_orientation=self.host.app_orientation, app_scale=self.host.app_scale,
            render_scale=self.host.render_scale, match_view=self.host.match_view)))

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
        # A host observer can enter a nested Qt event loop. Do not let its timer
        # overwrite self.frame or destroy the transport while render is active.
        if self._ticking:
            return
        self._ticking = True
        try:
            self._tick()
        except Exception as error:
            self.diagnostics.event("ERROR: " + str(error))
            self.request_stop()
            raise
        finally:
            self._ticking = False

    def _tick(self):
        if not self.running:
            return
        if self.stopping:
            self.status()
            if self.dll.qarvtk_host_destroy(self.handle):
                self.handle = c.c_void_p()
                self.host.close()
                self.last_status = "Stopped. " + self.last_status
                self.diagnostics.flush(force=True)
                self.diagnostics.event(self.last_status)
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
                     fov=tuple(eye.fov), size=(eye.width, eye.height),
                     depth_size=(eye.depth_width, eye.depth_height)) for eye in self.frame.eyes]
        started = perf_counter()
        try:
            self.host.render(eyes, self, near=self.frame.near_plane, far=self.frame.far_plane)
            submit = perf_counter()
            self._check(self.dll.qarvtk_host_finish(self.handle, self.frame.serial))
            timings = dict(self.host.last_timings)
            timings["finish_call_ms"] = (perf_counter() - submit) * 1000
            self.diagnostics.record(self.frame.serial, timings, eyes, started,
                                    self.host.last_render_sizes, self.host.last_desktop_size)
            def sizes(values):
                labels = [f"{w} x {h}" for w, h in values]
                return labels[0] + " / eye" if labels[0] == labels[1] else "L " + labels[0] + ", R " + labels[1]
            self.resolution_status = ("Render " + sizes(self.host.last_render_sizes) +
                "; stream color " + sizes([eye["size"] for eye in eyes]) +
                "; depth " + sizes([eye["depth_size"] for eye in eyes]) +
                "; Slicer " + " x ".join(map(str, self.host.last_desktop_size)))
        except Exception:
            self.request_stop()
            raise

    def request_stop(self):
        if self.running and not self.stopping:
            self.stopping = True
            self.dll.qarvtk_host_stop(self.handle)
            self.diagnostics.flush(force=True)
            self.diagnostics.event("Stop requested")
