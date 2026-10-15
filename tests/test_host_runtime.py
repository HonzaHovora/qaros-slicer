"""Control-flow regression tests without a Windows SDK or graphics context."""
import ctypes as c
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "slicer"))
from qarvtk_host_runtime import EXPECTED_SDK, Frame, HostTimingLog, HostTransport, library


class FakeDll:
    def __init__(self):
        self.polls = self.destroys = self.stops = 0
        self.finished = []

    def qarvtk_host_poll(self, handle, out):
        self.polls += 1
        frame = c.cast(out, c.POINTER(Frame)).contents
        frame.serial = self.polls
        frame.near_plane, frame.far_plane = .025, 10.
        for eye in frame.eyes:
            eye.width, eye.height = 640, 480
            eye.depth_width, eye.depth_height = 320, 240
        return 1

    def qarvtk_host_finish(self, handle, serial):
        self.finished.append(serial)
        return 0

    def qarvtk_host_status(self, handle, text, size):
        text.value = b"fixture status"

    def qarvtk_host_stop(self, handle):
        self.stops += 1

    def qarvtk_host_destroy(self, handle):
        self.destroys += 1
        return 1


class HostRuntimeTest(unittest.TestCase):
    def test_old_placement_abi_is_rejected_before_binding_create(self):
        for abi, size in ((2, 64), (3, 112)):
            old_info = dict(host_abi=abi, header_sha256=EXPECTED_SDK, modern_api=0,
                            eye_size=104, frame_size=232, placement_size=size)
            old_dll = type("OldDll", (), {"qarvtk_host_info": staticmethod(lambda: json.dumps(old_info).encode())})()
            with patch("qarvtk_host_runtime.c.CDLL", return_value=old_dll):
                with self.assertRaisesRegex(RuntimeError, "ABI or SDK fingerprint"):
                    library("old-host.dll")

    def test_preview_failure_preserves_stereo_and_restores_context(self):
        with tempfile.TemporaryDirectory() as folder:
            events = []
            t = self.transport(folder, lambda *args, **kwargs: None)
            t.host.window = type("Window", (), {"MakeCurrent": lambda self: events.append("context")})()
            def fail(): raise RuntimeError("Preview-only failure")
            t.panels = type("Panels", (), {"tick": staticmethod(fail), "close": staticmethod(lambda: events.append("closed"))})()
            t.tick()
            self.assertEqual(t.dll.finished, [1])
            self.assertFalse(t.stopping)
            self.assertIsNone(t.panels)
            self.assertEqual(events, ["closed", "context"])
            t.tick()
            self.assertEqual(t.dll.finished, [1, 2])
            t.request_stop()

    def transport(self, folder, render):
        # Bypass Windows/SDK creation; exercise the actual poll/render/finish
        # lifecycle with a render callback that emulates nested Qt events.
        transport = HostTransport.__new__(HostTransport)
        transport.dll = FakeDll()
        transport.handle = c.c_void_p(1)
        transport.frame = Frame()
        transport.stopping = transport._ticking = False
        transport.last_status = "fixture"
        transport.diagnostics = HostTimingLog(folder)
        transport.host = type("Host", (), {"last_timings": {"frame_wall_ms": 10.},
                                           "last_render_sizes": [(320, 240)]*2, "last_desktop_size": (800, 600),
                                           "render": staticmethod(render), "close": staticmethod(lambda: None)})()
        return transport

    def test_nested_timer_cannot_overwrite_live_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            def render(eyes, consumer, near, far):
                self.assertEqual((near, far), (.025, 10.))
                self.assertEqual(eyes[0]["depth_size"], (320, 240))
                serial = consumer.frame.serial
                consumer.tick()
                self.assertEqual(consumer.frame.serial, serial)
            t = self.transport(folder, render)
            t.tick()
            self.assertEqual(t.dll.polls, 1)
            self.assertEqual(t.dll.finished, [1])
            t.tick()
            self.assertEqual(t.dll.finished, [1, 2])
            t.request_stop()
            record = Path(folder, "host-python.log").read_text().split("PERF_HOST ")[1].splitlines()[0]
            metrics = json.loads(record)
            self.assertEqual(metrics["frames"], 2)
            self.assertEqual(metrics["last_serial"], 2)
            self.assertEqual(metrics["eye_sizes"], [[640, 480], [640, 480]])
            self.assertEqual(metrics["render_sizes"], [[320, 240], [320, 240]])
            self.assertEqual(metrics["depth_sizes"], [[320, 240], [320, 240]])
            self.assertEqual(metrics["desktop_size"], [800, 600])
            self.assertEqual(metrics["frame_wall_ms"], 10.)

    def test_nested_stop_cannot_destroy_transport_inside_render(self):
        with tempfile.TemporaryDirectory() as folder:
            def render(eyes, consumer, near, far):
                consumer.request_stop()
                consumer.tick()
                self.assertEqual(consumer.dll.destroys, 0)
                raise RuntimeError("render cancelled by observer")
            t = self.transport(folder, render)
            with self.assertRaisesRegex(RuntimeError, "cancelled by observer"):
                t.tick()
            self.assertEqual(t.dll.stops, 1)
            self.assertFalse(t._ticking)
            self.assertEqual(t.dll.finished, [])
            t.tick()
            self.assertEqual(t.dll.destroys, 1)
            self.assertFalse(t.running)
            self.assertIn("render cancelled by observer", Path(folder, "host-python.log").read_text())

    def test_first_stop_reason_survives_repeated_stop_and_worker_shutdown(self):
        with tempfile.TemporaryDirectory() as folder:
            t = self.transport(folder, lambda *args, **kwargs: None)
            t.request_stop("Slicer scene closing")
            t.request_stop("Module cleanup or application exit")
            self.assertIn("Slicer scene closing", t.status())
            t.tick()
            self.assertFalse(t.running)
            self.assertIn("Slicer scene closing", t.status())
            self.assertEqual(t.dll.stops, 1)
            events = [json.loads(line.split("STOP_REQUEST ")[1])
                      for line in Path(folder, "host-python.log").read_text().splitlines()
                      if "STOP_REQUEST " in line]
            self.assertEqual(events, [{"reason": "Slicer scene closing"}])


if __name__ == "__main__":
    unittest.main()
