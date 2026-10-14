"""QAROS scripted Slicer module; rendering/SDK work stays in a child process."""
from pathlib import Path
import sys
import qt
import ctk
import slicer
from slicer.ScriptedLoadableModule import ScriptedLoadableModule, ScriptedLoadableModuleWidget

sys.path.insert(0, str(Path(__file__).resolve().parent))
if (Path(__file__).resolve().parent / "QarosVTKLib").is_dir():
    from QarosVTKLib.qarvtk_slicer import export_node, export_selection
    from QarosVTKLib.qarvtk_runtime import Backend, user_directory
else:  # Source checkout, before packaging.
    from qarvtk_slicer import export_node, export_selection
    from qarvtk_runtime import Backend, user_directory


class QarosVTK(ScriptedLoadableModule):
    def __init__(self, parent):
        super().__init__(parent)
        parent.title = "QAROS Streaming"
        parent.categories = ["QAROS"]
        parent.contributors = ["QuaternAR"]
        parent.helpText = ("Stream lit models, segments and one CT/MR volume through the QAROS VTK backend. "
                           "World RAS millimetres are converted to QAROS metres. "
                           "See docs/INSTALLATION.md in QAROS_VTK.")
        parent.acknowledgementText = "QAROS VTK integration prototype."


class QarosVTKWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        super().setup()
        self._cleaned_up = False
        self.backend = Backend(slicer.util.startupEnvironment(), scene_suffix=".vtm")
        self.settings = qt.QSettings()
        form = qt.QFormLayout()
        self.layout.addLayout(form)
        self.scope = qt.QComboBox()
        self.scope.addItems(["Selected object", "Visible 3D scene (first view)"])
        form.addRow("Stream", self.scope)
        self.fit = qt.QCheckBox("Center and fit into 65 cm workspace")
        self.fit.checked = True
        self.fit.toolTip = "Turn off to preserve world RAS position and physical size."
        form.addRow(self.fit)
        self.node = slicer.qMRMLNodeComboBox()
        self.node.nodeTypes = ["vtkMRMLModelNode", "vtkMRMLSegmentationNode", "vtkMRMLScalarVolumeNode"]
        self.node.addEnabled = False
        self.node.removeEnabled = False
        self.node.noneEnabled = True
        self.node.setMRMLScene(slicer.mrmlScene)
        form.addRow("Model, segmentation or CT/MR", self.node)
        self.segment = qt.QComboBox()
        form.addRow("Segment", self.segment)
        self.exe = self.path_field(form, "Sender executable", "Executable", False)
        self.sdk = self.path_field(form, "QAROS SDK folder", "Sdk", True)
        self.identity = self.path_field(form, "Hub identity file", "Identity", False,
                                        str(user_directory() / "onboarding-id.txt"))
        self.code = qt.QLineEdit()
        self.code.echoMode = qt.QLineEdit.Password
        self.code.placeholderText = "First connection only; not saved"
        form.addRow("Hub pairing code", self.code)
        self.hub = qt.QLineEdit()
        self.hub.text = str(self.settings.value("QAROS_VTK/Hub", ""))
        form.addRow("Hub host (optional)", self.hub)
        self.invite = self.path_field(form, "Legacy invite (optional)", "Invite", False)
        self.target = qt.QComboBox()
        self.target.addItems(["visualizer", "quest"])
        form.addRow("Legacy viewer", self.target)
        self.startButton = qt.QPushButton("Start streaming")
        self.stopButton = qt.QPushButton("Stop streaming")
        self.updateButton = qt.QPushButton("Update scene")
        form.addRow(self.startButton, self.stopButton)
        form.addRow(self.updateButton)
        self.autoUpdate = qt.QCheckBox("Update surfaces automatically (one second interval)")
        self.autoUpdate.checked = False
        form.addRow(self.autoUpdate)
        self.sceneInfo = qt.QLabel("CT/MR: enable Volume Rendering, choose a preset, then Start. Use Update scene after changes. One volume; Composite mode; cropping off.")
        self.sceneInfo.wordWrap = True
        form.addRow(self.sceneInfo)
        self.path = ctk.ctkPathLineEdit()
        self.path.filters = ctk.ctkPathLineEdit.Files
        self.path.nameFilters = ["VTK surface (*.vtp)"]
        self.path.currentPath = str(Path.home() / "qarvtk-surface.vtp")
        form.addRow("Optional export file", self.path)
        self.button = qt.QPushButton("Export surface to file")
        form.addRow(self.button)
        self.status = qt.QLabel("Choose an object or visible scene, then configure the sender and SDK paths.")
        self.status.wordWrap = True
        form.addRow(self.status)
        self.log = qt.QPlainTextEdit()
        self.log.readOnly = True
        self.log.maximumHeight = 150
        form.addRow("Sender log", self.log)
        self.node.connect("currentNodeChanged(vtkMRMLNode*)", self.update_segments)
        self.scope.connect("currentIndexChanged(int)", self.update_scope)
        self.button.connect("clicked()", self.export)
        self.startButton.connect("clicked()", self.start_stream)
        self.stopButton.connect("clicked()", self.backend.request_stop)
        self.updateButton.connect("clicked()", self.publish_surface)
        self.timer = qt.QTimer(self.parent)
        self.timer.setInterval(1000)
        self.timer.connect("timeout()", self.poll)
        self.timer.start()
        self.sceneObserver = slicer.mrmlScene.AddObserver(
            slicer.mrmlScene.StartCloseEvent, self.on_scene_close)
        slicer.app.connect("aboutToQuit()", self.cleanup)
        self.update_segments(self.node.currentNode())
        self.layout.addStretch(1)

    def path_field(self, form, label, key, directory, default=""):
        field = ctk.ctkPathLineEdit()
        field.filters = ctk.ctkPathLineEdit.Dirs if directory else ctk.ctkPathLineEdit.Files
        field.currentPath = str(self.settings.value("QAROS_VTK/" + key, default))
        form.addRow(label, field)
        return field

    def update_segments(self, node):
        self.segment.clear()
        is_segmentation = node is not None and node.IsA("vtkMRMLSegmentationNode")
        self.segment.enabled = bool(is_segmentation)
        if is_segmentation:
            segmentation = node.GetSegmentation()
            for index in range(segmentation.GetNumberOfSegments()):
                sid = segmentation.GetNthSegmentID(index)
                self.segment.addItem(segmentation.GetSegment(sid).GetName(), sid)

    def update_scope(self, index):
        self.node.enabled = index == 0
        self.update_segments(self.node.currentNode())
        if index != 0:
            self.segment.enabled = False

    def write_surface(self, path):
        sid = self.segment.itemData(self.segment.currentIndex) if self.segment.enabled else None
        if Path(path).suffix.lower() == ".vtp":
            return export_node(self.node.currentNode(), path, sid)
        result, volumes, objects = export_selection(self.node.currentNode(), path, sid,
            visible_scene=self.scope.currentIndex == 1, fit=self.fit.checked)
        if volumes:
            self.autoUpdate.checked = False
        self.autoUpdate.enabled = not bool(volumes)
        self.sceneInfo.text = "{} objects, {} CT/MR volume. {}".format(objects, volumes,
            "Use Update scene after changing the volume preset or data." if volumes else "Lighting and model colors enabled.")
        return result

    def export(self):
        try:
            self.status.text = "Exported: " + self.write_surface(self.path.currentPath)
        except Exception as error:
            slicer.util.errorDisplay(str(error))

    def publish_surface(self):
        try:
            self.write_surface(self.backend.scene)
            self.status.text = "Scene updated. " + self.backend.status()
        except Exception as error:
            self.autoUpdate.checked = False
            self.status.text = str(error)

    def start_stream(self):
        try:
            self.write_surface(self.backend.scene)
            self.backend.start(self.exe.currentPath, self.sdk.currentPath, scale=0.001, ras=True,
                pairing_code=self.code.text, hub=self.hub.text, identity=self.identity.currentPath,
                invite=self.invite.currentPath, target=self.target.currentText)
            for key, value in (("Executable", self.exe.currentPath), ("Sdk", self.sdk.currentPath),
                               ("Identity", self.identity.currentPath), ("Hub", self.hub.text),
                               ("Invite", self.invite.currentPath)):
                self.settings.setValue("QAROS_VTK/" + key, value)
            self.poll()
        except Exception as error:
            self.status.text = str(error)
            slicer.util.errorDisplay(str(error))
        finally:
            self.code.clear()

    def poll(self):
        self.status.text = self.backend.status()
        self.startButton.enabled = not self.backend.running
        self.stopButton.enabled = self.backend.running
        self.log.setPlainText(self.backend.log_tail())
        if self.autoUpdate.checked and self.backend.running:
            self.publish_surface()

    def on_scene_close(self, caller=None, event=None):
        self.autoUpdate.checked = False
        self.backend.close()

    def cleanup(self):
        if getattr(self, "_cleaned_up", False):
            return
        self._cleaned_up = True
        slicer.app.disconnect("aboutToQuit()", self.cleanup)
        if hasattr(self, "timer"):
            self.timer.stop()
        if getattr(self, "sceneObserver", None):
            slicer.mrmlScene.RemoveObserver(self.sceneObserver)
            self.sceneObserver = None
        if hasattr(self, "backend"):
            self.backend.close()
