"""Experimental direct streaming of Slicer's own render window."""
from datetime import datetime
from pathlib import Path
import json
import sys
import qt
import ctk
import slicer
from slicer.ScriptedLoadableModule import ScriptedLoadableModule, ScriptedLoadableModuleWidget

sys.path.insert(0, str(Path(__file__).resolve().parent))
if (Path(__file__).resolve().parent / "QarosVTKLib").is_dir():
    from QarosVTKLib.qarvtk_host_view import HostView
    from QarosVTKLib.qarvtk_host_runtime import HostTransport
    from QarosVTKLib.qarvtk_runtime import user_directory
else:
    from qarvtk_host_view import HostView
    from qarvtk_host_runtime import HostTransport
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from qarvtk_runtime import user_directory


class QarosLive(ScriptedLoadableModule):
    def __init__(self, parent):
        super().__init__(parent)
        parent.title = "QAROS Live Renderer"
        parent.categories = ["QAROS"]
        parent.contributors = ["QuaternAR"]
        parent.helpText = "Stream the first Slicer 3D view using its actual renderer. Experimental Windows session-SDK integration."
        parent.acknowledgementText = "QAROS live host-rendering prototype."


class QarosLiveWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        super().setup()
        self.transport = None
        self.cleaned_up = False
        self.settings = qt.QSettings()
        form = qt.QFormLayout()
        self.layout.addLayout(form)
        label = qt.QLabel("Live first 3D view. Changes in Slicer are rendered automatically. "
                         "Experimental: one VTK GPU Composite volume with opaque surfaces; ROI cropping is supported.")
        label.wordWrap = True
        form.addRow(label)
        self.fit = qt.QCheckBox("Center and fit into 65 cm workspace at Start")
        self.fit.checked = True
        self.fit.toolTip = "At Start, center the scene and fit the workspace's longest edge to 65 cm. " \
                           "Off keeps physical size (1 mm = 1 mm) and scene position. Workspace dimensions always follow scene bounds."
        form.addRow(self.fit)
        self.matchView = qt.QCheckBox("Use Slicer viewing direction at Start")
        self.matchView.checked = True
        form.addRow(self.matchView)
        self.workspaceStatus = qt.QLabel("Dimensions follow the visible scene at Start.")
        self.workspaceStatus.wordWrap = True
        form.addRow("Workspace", self.workspaceStatus)
        self.renderScale = qt.QComboBox()
        self.renderScale.addItems(["100%", "75%", "50%"])
        self.renderScale.toolTip = "Render width and height relative to the viewer request. 50% uses one quarter of the pixels. Applied at Start."
        form.addRow("Render resolution", self.renderScale)
        self.resolutionStatus = qt.QLabel("Resolution will be shown when the viewer connects.")
        self.resolutionStatus.wordWrap = True
        form.addRow(self.resolutionStatus)
        self.dll = ctk.ctkPathLineEdit()
        self.dll.filters = ctk.ctkPathLineEdit.Files
        default_dll = Path(__file__).resolve().parents[2] / "Release" / "qarvtk-host.dll"
        self.dll.currentPath = str(self.settings.value("QAROS_LIVE/Dll", str(default_dll)))
        form.addRow("Host bridge DLL", self.dll)
        self.sdk = ctk.ctkPathLineEdit()
        self.sdk.filters = ctk.ctkPathLineEdit.Dirs
        self.sdk.currentPath = str(self.settings.value("QAROS_VTK/Sdk", "D:/install"))
        form.addRow("QAROS SDK folder", self.sdk)
        self.target = qt.QComboBox()
        self.target.addItems(["visualizer", "quest"])
        form.addRow("Viewer", self.target)
        self.startButton = qt.QPushButton("Start live streaming")
        self.stopButton = qt.QPushButton("Stop live streaming")
        form.addRow(self.startButton, self.stopButton)
        self.stopButton.enabled = False
        self.status = qt.QLabel("Configure the first 3D view in Slicer, then Start live streaming.")
        self.status.wordWrap = True
        form.addRow(self.status)
        self.logPath = qt.QLineEdit()
        self.logPath.readOnly = True
        form.addRow("Log folder", self.logPath)
        self.startButton.connect("clicked()", self.start_stream)
        self.stopButton.connect("clicked()", self.stop_stream)
        # Application ownership keeps polling alive while SDK shutdown finishes,
        # even when Slicer unloads the module's widget.
        self.timer = qt.QTimer(slicer.app)
        self.timer.setInterval(5)
        self.timer.connect("timeout()", self.tick)
        self.timer.start()
        self.scene_observer = slicer.mrmlScene.AddObserver(slicer.mrmlScene.StartCloseEvent, self.scene_closing)
        self.layout_manager = slicer.app.layoutManager()
        if self.layout_manager:
            self.layout_manager.connect("layoutChanged(int)", self.layout_changed)
        slicer.app.connect("aboutToQuit()", self.cleanup)
        self.layout.addStretch(1)

    def start_stream(self):
        try:
            if self.transport and self.transport.running:
                return
            old = getattr(slicer.modules, "qarosvtk", None)
            if old:
                old_widget = old.widgetRepresentation().self()
                if old_widget.backend.running:
                    raise RuntimeError("Stop streaming in QAROS Streaming before starting the live renderer")
            lm = slicer.app.layoutManager()
            if not lm or lm.threeDViewCount < 1:
                raise RuntimeError("Open a Slicer layout containing a 3D view")
            view = lm.threeDWidget(0).threeDView()
            view.renderWindow().Render()
            host = HostView(view, fit=self.fit.checked, match_view=self.matchView.checked,
                            render_scale=(1., .75, .5)[self.renderScale.currentIndex])
            folder = user_directory() / "live-logs" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            self.transport = HostTransport(self.dll.currentPath, self.sdk.currentPath,
                                            self.target.currentText, folder, host)
            self.workspaceStatus.text = " × ".join(f"{x * 100:.1f}" for x in host.workspace_size) + " cm (width × height × depth)"
            self.settings.setValue("QAROS_LIVE/Dll", self.dll.currentPath)
            self.settings.setValue("QAROS_VTK/Sdk", self.sdk.currentPath)
            self.logPath.text = str(folder)
            self.startButton.enabled = False
            self.stopButton.enabled = True
            self.status.text = "Connecting the live Slicer renderer..."
        except Exception as error:
            self.status.text = str(error)
            slicer.util.errorDisplay(str(error))

    def stop_stream(self, *args):
        if self.transport:
            self.transport.request_stop("Stop button")

    def scene_closing(self, *args):
        if self.transport:
            self.transport.request_stop("Slicer scene closing")

    def layout_changed(self, layout):
        transport = self.transport
        if not transport or not transport.running or transport.stopping:
            return
        try:
            # Slicer emits layoutChanged even when maximizing the same view.
            # Continue using that view; never silently switch the source.
            widget = self.layout_manager.threeDWidget(0)
            if not widget or widget.threeDView() != transport.host.view:
                raise RuntimeError("The source 3D view was replaced")
            if not widget.mrmlViewNode().IsViewVisibleInLayout():
                raise RuntimeError("The source 3D view was removed from the layout")
            transport.host.validate_source()
        except Exception as error:
            transport.request_stop("Slicer layout changed: " + str(error))
            return
        transport.diagnostics.event("LAYOUT_CHANGED " + json.dumps(dict(
            layout=int(layout), action="continue", desktop_size=list(transport.host.window.GetSize()))))

    def tick(self):
        if self.transport:
            try:
                self.transport.tick()
                if not self.cleaned_up:
                    self.status.text = self.transport.status()
                    self.resolutionStatus.text = self.transport.resolution_status
            except Exception as error:
                self.transport.request_stop("GUI error: " + str(error))
                if not self.cleaned_up:
                    self.status.text = str(error)
            if not self.cleaned_up:
                self.startButton.enabled = not self.transport.running
                self.stopButton.enabled = self.transport.running and not self.transport.stopping
                for control in (self.fit, self.matchView, self.renderScale):
                    control.enabled = not self.transport.running
        if self.cleaned_up and (not self.transport or not self.transport.running):
            self.timer.stop()
            self.timer.disconnect("timeout()", self.tick)
            self.timer.deleteLater()

    def cleanup(self):
        if self.cleaned_up:
            return
        self.cleaned_up = True
        if self.transport:
            self.transport.request_stop("Module cleanup or application exit")
        slicer.mrmlScene.RemoveObserver(self.scene_observer)
        if self.layout_manager:
            self.layout_manager.disconnect("layoutChanged(int)", self.layout_changed)
        slicer.app.disconnect("aboutToQuit()", self.cleanup)
