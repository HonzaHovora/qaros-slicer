"""Preview/video scheduling without a graphics context or SDK receiver."""
import importlib.util
from pathlib import Path
import sys
import unittest

path = Path(__file__).resolve().parents[1] / "integrations/slicer/qarvtk_host_panels.py"
spec = importlib.util.spec_from_file_location("host_panels_test_module", path)
panels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panels)


class Window:
    def __init__(self):
        self.revision = 0
        self.observers = {}
        self.size = (640, 360)
        self.stamp = 1
    def GetContextCreationTime(self): return self.stamp
    def GetSize(self): return self.size
    def MakeCurrent(self): pass
    def GetNeverRendered(self): return False
    def GetDisplayFramebuffer(self): return self
    def GetColorAttachmentAsTextureObject(self, index): return self
    def GetHandle(self): return self.revision + 100
    def GetWidth(self): return self.size[0]
    def GetHeight(self): return self.size[1]
    def AddObserver(self, event, callback):
        index = max(self.observers, default=0) + 1
        self.observers[index] = callback
        return index
    def RemoveObserver(self, index): del self.observers[index]
    def frame(self):
        self.revision += 1
        for callback in list(self.observers.values()): callback()
    def Render(self): raise AssertionError("Preview must never trigger rendering")


class Sink:
    def __init__(self):
        self.next = 0
        self.copies, self.closed, self.visibility, self.events = [], [], [], []
        self.diagnostics = type("Diagnostics", (), {"event": self.events.append})()
        self.ready, self.fail = True, False
        self.running, self.stopping, self.panels = True, False, None
        self.video_enabled, self.gates = True, []
    def panel_create(self, *args): self.next += 1; return self.next
    def panel_capture(self, handle, texture, width, height):
        if self.fail: raise RuntimeError("Panel encoder failed")
        if not self.ready: return False
        self.copies.append((handle, texture, width, height))
        return True
    def panel_visible(self, handle, visible): self.visibility.append((handle, visible))
    def panel_close(self, handle): self.closed.append(handle)
    def panel_status(self, handle):
        return "Live 640 x 360; 1 frames" if self.video_enabled else "Diagnostic: panel open, video not started"
    def panels_video_enabled(self, enabled):
        self.video_enabled = enabled
        self.gates.append(enabled)


class PanelTest(unittest.TestCase):
    def fixture(self):
        window, sink = Window(), Sink()
        view = type("View", (), {"renderWindow": lambda self: window, "isVisible": lambda self: self.visible})()
        view.visible = True
        node = type("Node", (), {"IsViewVisibleInLayout": lambda self: True})()
        widget = type("Widget", (), {"sliceView": lambda self: view, "mrmlSliceNode": lambda self: node})()
        layout = type("Layout", (), {"sliceViewNames": lambda self: ["Red"], "sliceWidget": lambda self, name: widget})()
        now = [0.]
        manager = panels.SlicePanels(layout, sink, (0, 0, -1.5), (.65, .65, .65), fps=15, clock=lambda: now[0])
        return window, sink, view, now, manager

    def test_video_frames_are_coalesced_and_rate_limited(self):
        window, sink, view, now, manager = self.fixture()
        manager.tick()
        self.assertEqual(len(sink.copies), 1)
        for _ in range(10): window.frame()
        now[0] = .03; manager.tick()
        self.assertEqual(len(sink.copies), 1)
        sink.ready = False; now[0] = .08; manager.tick()
        for _ in range(20): window.frame()
        sink.ready = True; now[0] = .11; manager.tick()
        self.assertEqual([x[1] for x in sink.copies], [100, 130])
        now[0] = .5; manager.tick()
        self.assertEqual(len(sink.copies), 2, "Static view was captured repeatedly")
        window.frame(); now[0] = .6; manager.tick()
        self.assertEqual(sink.copies[-1][1], 131)
        manager.close()
        self.assertFalse(window.observers)

    def test_hide_restore_context_recreation_and_error_are_local(self):
        window, sink, view, now, manager = self.fixture()
        manager.tick(); view.visible = False; now[0] = .3; manager.tick()
        self.assertEqual(sink.visibility[-1], (1, False))
        window.frame(); now[0] = .4; manager.tick(); self.assertEqual(len(sink.copies), 1)
        view.visible = True; now[0] = .6; manager.tick()
        self.assertEqual(sink.visibility[-1], (1, True))
        window.stamp = 2; now[0] = .9; manager.tick()
        self.assertIn(1, sink.closed); self.assertEqual(sink.copies[-1][0], 2)
        sink.fail = True; window.frame(); now[0] = 1.2; manager.tick()
        self.assertIn("Red", manager.errors)
        self.assertIn(2, sink.closed)
        self.assertFalse(window.observers)
        manager.close()

    def test_dimensions_are_bounded_and_even(self):
        self.assertEqual(panels.panel_size(1920, 1080), (768, 432))
        self.assertEqual(panels.panel_size(451, 726), (450, 726))

    def test_probe_separates_creation_video_and_additional_panels(self):
        window, sink, view, now, manager = self.fixture()
        widget = manager.layout.sliceWidget("Red")
        layout = type("Layout", (), {
            "sliceViewNames": lambda self: ["Green", "Yellow", "Red"],
            "sliceWidget": lambda self, name: widget})()
        probe = panels.PanelStartupProbe(layout, sink, (0, 0, -1.5), (.65, .65, .65))
        self.assertEqual(sink.gates, [False])
        self.assertIsNone(sink.panels)
        probe.advance()
        with self.assertRaisesRegex(RuntimeError, "not ready"):
            probe.advance()
        self.assertEqual(probe.stage, 1)
        sink.panels.tick()
        self.assertEqual(set(sink.panels.sources), {"Red"})
        self.assertEqual(sink.next, 1)
        self.assertFalse(sink.video_enabled)
        self.assertTrue(sink.copies, "Creation step must still stage a real slice locally")
        probe.advance()
        self.assertEqual(sink.gates, [False, True])
        self.assertEqual(sink.next, 1, "Starting video must keep the existing panel/sender")
        probe.advance()
        sink.panels.tick()
        self.assertEqual(set(sink.panels.sources), {"Red", "Yellow", "Green"})
        self.assertEqual(sink.next, 3)
        sink.panels.close()
        self.assertEqual(sorted(sink.closed), [1, 2, 3])

    def test_probe_cannot_advance_after_stop_or_without_visible_red(self):
        window, sink, view, now, manager = self.fixture()
        probe = panels.PanelStartupProbe(manager.layout, sink, (0, 0, -1.5), (.65, .65, .65))
        view.visible = False
        with self.assertRaisesRegex(RuntimeError, "Red slice"):
            probe.advance()
        self.assertEqual(probe.stage, 0)
        sink.stopping = True
        with self.assertRaisesRegex(RuntimeError, "Start live streaming"):
            probe.advance()
        self.assertIsNone(sink.panels)


if __name__ == "__main__": unittest.main()
