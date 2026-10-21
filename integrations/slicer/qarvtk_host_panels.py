"""Read-only slice previews from completed VTK frames, including live video.

No Render(), screen capture, image readback or input forwarding. The latest
rendered image replaces any older pending image; slow receivers cannot queue it.
"""
from time import perf_counter
from math import hypot
import json
import vtk

PANEL_DIAGONAL_METERS = 14. * .0254


def panel_size(width, height):
    scale = min(1., 768. / max(width, height))
    return tuple(max(16, 2 * int(x * scale / 2)) for x in (width, height))


class SlicePreview:
    def __init__(self, name, view, sink, position):
        self.name, self.view, self.sink = name, view, sink
        self.window = view.renderWindow()
        self.context_stamp = self.window.GetContextCreationTime()
        self.revision, self.captured_revision = 1, 0
        self.next_capture = 0.
        self.visible = True
        self.observer = None
        self.handle = None
        self.size = panel_size(*self.window.GetSize())
        # Physical screen size is independent of voxel/model scale and pixel
        # resolution. Set it only at creation; QAROS owns later user resizing.
        self.physical_size = tuple(PANEL_DIAGONAL_METERS * x / hypot(*self.size) for x in self.size)
        self.window.MakeCurrent()
        self.handle = sink.panel_create("Slicer " + name, self.size, position, self.physical_size[0])
        self.observer = self.window.AddObserver(vtk.vtkCommand.EndEvent, self.rendered)

    def rendered(self, *unused):
        self.revision += 1

    def matches(self, view):
        return (view == self.view and view.renderWindow() == self.window
                and self.window.GetContextCreationTime() == self.context_stamp)

    def set_visible(self, visible):
        if visible != self.visible:
            self.sink.panel_visible(self.handle, visible)
            self.visible = visible
            if visible:
                self.revision += 1

    def capture(self, now, interval):
        if not self.visible or self.revision == self.captured_revision or now < self.next_capture:
            return None
        if self.window.GetNeverRendered():
            return None
        self.window.MakeCurrent()
        framebuffer = self.window.GetDisplayFramebuffer()
        texture = framebuffer.GetColorAttachmentAsTextureObject(0) if framebuffer else None
        if not texture or not texture.GetHandle():
            return None
        width, height = texture.GetWidth(), texture.GetHeight()
        if width < 1 or height < 1:
            return None
        revision = self.revision
        started = perf_counter()
        copied = self.sink.panel_capture(self.handle, texture.GetHandle(), width, height)
        if not copied:
            # Keep it dirty; retry the newest image later, without waiting.
            self.next_capture = now + min(.02, interval)
            return dict(busy=1)
        skipped = max(0, revision - self.captured_revision - 1)
        self.captured_revision = revision
        self.next_capture = now + interval
        return dict(busy=0, replaced=skipped, copy_ms=(perf_counter() - started) * 1000,
                    source_size=(width, height))

    def close(self):
        if self.observer is not None:
            self.window.RemoveObserver(self.observer)
            self.observer = None
        if self.handle is not None:
            self.sink.panel_close(self.handle)
            self.handle = None


class SlicePanels:
    def __init__(self, layout, sink, workspace_position, workspace_size, fps=15, clock=perf_counter):
        if fps not in (5, 10, 15, 30):
            raise ValueError("Slice preview FPS must be 5, 10, 15 or 30")
        self.layout, self.sink = layout, sink
        self.position, self.workspace = workspace_position, workspace_size
        self.interval, self.clock = 1. / fps, clock
        self.sources, self.errors, self.slots = {}, {}, {}
        self.next_refresh = self.next_status = 0.
        self.next_report = clock() + 5
        self.cursor = 0
        self.closed = False
        self.frames = self.busy = self.replaced = 0
        self.copy_ms = 0.
        self.source_sizes = {}
        self.status = "Waiting for visible slice views"

    def _error(self, name, error):
        self.errors[name] = str(error)
        source = self.sources.pop(name, None)
        if source:
            source.close()
        self.sink.diagnostics.event("PANEL_ERROR " + json.dumps(dict(view=name, error=str(error))))

    def refresh(self):
        names = [str(name) for name in self.layout.sliceViewNames()]
        names.sort(key=lambda name: (("Red", "Yellow", "Green").index(name)
                                    if name in ("Red", "Yellow", "Green") else 3, name))
        for name in list(self.sources):
            if name not in names:
                self.sources.pop(name).close()
        for name in names:
            if name in self.errors:
                continue
            try:
                widget = self.layout.sliceWidget(name)
                if not widget:
                    continue
                view = widget.sliceView()
                visible = bool(widget.mrmlSliceNode().IsViewVisibleInLayout() and view.isVisible())
                source = self.sources.get(name)
                if source and not source.matches(view):
                    self.sources.pop(name).close()
                    source = None
                if source:
                    source.set_visible(visible)
                elif visible and min(view.renderWindow().GetSize()) >= 16 and not view.renderWindow().GetNeverRendered():
                    if name not in self.slots:
                        if len(self.slots) >= 8:
                            raise RuntimeError("At most eight slice previews are supported per stream")
                        self.slots[name] = len(self.slots)
                    slot = self.slots[name]
                    x, y, z = self.position
                    position = (x + (slot % 3 - 1) * .5,
                                y - self.workspace[1] * .5 - .06 - (slot // 3) * .5, z + .05)
                    self.sources[name] = SlicePreview(name, view, self.sink, position)
                    self.sink.diagnostics.event("PANEL_SOURCE " + json.dumps(dict(view=name,
                        stream_size=self.sources[name].size, physical_size_m=self.sources[name].physical_size,
                        position=position, fps_limit=round(1/self.interval))))
            except Exception as error:
                self._error(name, error)

    def tick(self):
        if self.closed:
            return
        now = self.clock()
        if now >= self.next_refresh:
            self.refresh()
            self.next_refresh = now + .25
        # Fair rotation; at most one GPU capture in a GUI timer turn. Video
        # frames arriving while a capture/send is busy are naturally coalesced.
        sources = list(self.sources.values())
        for _ in sources:
            self.cursor %= len(sources)
            source = sources[self.cursor]
            self.cursor += 1
            try:
                result = source.capture(now, self.interval)
                if result:
                    self.busy += result["busy"]
                    if not result["busy"]:
                        self.frames += 1
                        self.copy_ms += result["copy_ms"]
                        self.replaced += result["replaced"]
                        self.source_sizes[source.name] = result["source_size"]
                    break
            except Exception as error:
                self._error(source.name, error)
        if now >= self.next_status:
            labels = [name + ": " + (self.sink.panel_status(s.handle) if s.visible else "hidden")
                      for name, s in self.sources.items()]
            labels += [name + ": " + error for name, error in self.errors.items()]
            self.status = "; ".join(labels) if labels else "No visible slice views in this layout"
            self.next_status = now + 1
        if now >= self.next_report:
            if self.frames or self.busy:
                self.sink.diagnostics.event("PERF_PANELS " + json.dumps(dict(frames=self.frames,
                    capture_ms=self.copy_ms / max(1, self.frames), busy_skips=self.busy,
                    replaced_frames=self.replaced, source_sizes=self.source_sizes)))
            self.frames = self.busy = self.replaced = 0
            self.copy_ms = 0.
            self.next_report = now + 5

    def close(self):
        self.closed = True
        for source in self.sources.values():
            source.close()
        self.sources.clear()
