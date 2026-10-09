"""Run in a new Slicer process with --python-script; exits with pass/fail code."""
from pathlib import Path
import sys
import tempfile
import traceback
import vtk
import slicer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "slicer"))
from qarvtk_slicer import export_node


def run():
    cube = vtk.vtkCubeSource(); cube.Update()
    transform = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode")
    matrix = vtk.vtkMatrix4x4()
    for axis, value in enumerate((100, 200, 300)):
        matrix.SetElement(axis, 3, value)
    transform.SetMatrixTransformToParent(matrix)
    model = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode")
    model.SetAndObservePolyData(cube.GetOutput())
    model.SetAndObserveTransformNodeID(transform.GetID())
    segmentation = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    sid = segmentation.AddSegmentFromClosedSurfaceRepresentation(cube.GetOutput(), "Cube", [0, 1, 0])
    segmentation.SetAndObserveTransformNodeID(transform.GetID())
    with tempfile.TemporaryDirectory() as directory:
        for node, segment in ((model, None), (segmentation, sid)):
            path = Path(directory) / "surface.vtp"
            export_node(node, path, segment)
            reader = vtk.vtkXMLPolyDataReader()
            reader.SetFileName(str(path)); reader.Update()
            assert reader.GetOutput().GetBounds() == (99.5, 100.5, 199.5, 200.5, 299.5, 300.5)
            assert node.GetTransformNodeID() == transform.GetID()
    for node in (model, segmentation, transform):
        slicer.mrmlScene.RemoveNode(node)
    print("PASS: Slicer model and segmentation exported with world RAS transform")


try:
    run()
except Exception:
    traceback.print_exc()
    slicer.app.exit(1)
else:
    slicer.app.exit(0)
