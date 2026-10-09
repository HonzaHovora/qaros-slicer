"""Install as an Additional module path in Slicer; restart Slicer."""
from pathlib import Path
import sys
import qt
import ctk
import slicer
from slicer.ScriptedLoadableModule import ScriptedLoadableModule, ScriptedLoadableModuleWidget

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qarvtk_slicer import export_node


class QarosVTK(ScriptedLoadableModule):
    def __init__(self, parent):
        super().__init__(parent)
        parent.title = "QAROS VTK Surface Bridge"
        parent.categories = ["Examples"]
        parent.contributors = ["QuaternAR"]
        parent.helpText = ("Export a model or one segment as world RAS millimetres. "
                           "Start qarvtk-sender with --ras --meters-per-unit 0.001 --watch "
                           "and export again to update the viewer.")
        parent.acknowledgementText = "QAROS VTK integration prototype."


class QarosVTKWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        super().setup()
        form = qt.QFormLayout()
        self.layout.addLayout(form)
        self.node = slicer.qMRMLNodeComboBox()
        self.node.nodeTypes = ["vtkMRMLModelNode", "vtkMRMLSegmentationNode"]
        self.node.addEnabled = False
        self.node.removeEnabled = False
        self.node.noneEnabled = True
        self.node.setMRMLScene(slicer.mrmlScene)
        form.addRow("Model or segmentation", self.node)
        self.segment = qt.QComboBox()
        form.addRow("Segment", self.segment)
        self.path = ctk.ctkPathLineEdit()
        self.path.filters = ctk.ctkPathLineEdit.Files
        self.path.nameFilters = ["VTK surface (*.vtp)"]
        self.path.currentPath = str(Path.home() / "qarvtk-surface.vtp")
        form.addRow("Export file", self.path)
        self.button = qt.QPushButton("Export surface")
        form.addRow(self.button)
        self.status = qt.QLabel("The export contains the selected surface and its world transform.")
        self.status.wordWrap = True
        form.addRow(self.status)
        self.node.connect("currentNodeChanged(vtkMRMLNode*)", self.update_segments)
        self.button.connect("clicked()", self.export)
        self.update_segments(self.node.currentNode())
        self.layout.addStretch(1)

    def update_segments(self, node):
        self.segment.clear()
        is_segmentation = node is not None and node.IsA("vtkMRMLSegmentationNode")
        self.segment.enabled = bool(is_segmentation)
        if is_segmentation:
            segmentation = node.GetSegmentation()
            for index in range(segmentation.GetNumberOfSegments()):
                sid = segmentation.GetNthSegmentID(index)
                self.segment.addItem(segmentation.GetSegment(sid).GetName(), sid)

    def export(self):
        try:
            sid = self.segment.itemData(self.segment.currentIndex) if self.segment.enabled else None
            path = export_node(self.node.currentNode(), self.path.currentPath, sid)
            self.status.text = "Exported: " + path + "\nRe-export after edits to update a running sender."
        except Exception as error:
            slicer.util.errorDisplay(str(error))
