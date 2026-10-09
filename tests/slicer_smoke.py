"""Run in a new Slicer process with --python-script; exits with pass/fail code."""
from pathlib import Path
import sys
import tempfile
import traceback
import os
from unittest.mock import patch
import vtk
import slicer
import qt

plugin = Path(__file__).resolve().parents[1] / "package" / "QAROS-VTK-plugins" / "slicer"
sys.path.insert(0, str(plugin))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from qarvtk_slicer import export_node
from fixture_support import make_sdk, wait_ready


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
    # Module discovery/registration is part of the test, not just a direct import.
    assert hasattr(slicer.modules, "qarosvtk"), "Packaged module was not discovered"
    widget = slicer.modules.qarosvtk.widgetRepresentation().self()
    widget.node.setCurrentNode(segmentation)
    assert widget.segment.count == 1
    assert widget.segment.itemData(0) == sid
    with tempfile.TemporaryDirectory() as directory:
        for node, segment in ((model, None), (segmentation, sid)):
            path = Path(directory) / "surface.vtp"
            export_node(node, path, segment)
            reader = vtk.vtkXMLPolyDataReader()
            reader.SetFileName(str(path)); reader.Update()
            assert reader.GetOutput().GetBounds() == (99.5, 100.5, 199.5, 200.5, 299.5, 300.5)
            assert node.GetTransformNodeID() == transform.GetID()
        sdk = make_sdk(directory)
        widget.exe.currentPath = os.environ["QARVTK_TEST_BACKEND"]
        widget.sdk.currentPath = str(sdk)
        widget.identity.currentPath = str(Path(directory) / "identity.txt")
        widget.code.text = "fixture-pairing"
        with patch.object(slicer.util, "errorDisplay", side_effect=AssertionError):
            widget.start_stream()
        wait_ready(widget.backend)
        assert not widget.code.text, "Pairing code was not cleared"
        assert widget.backend.running
        assert widget.backend.scene.is_file()
        widget.publish_surface()
        widget.backend.request_stop()
        widget.backend.process.wait(timeout=5)
        widget.poll()
        assert widget.backend.poll() == 0
        assert not widget.backend.forced_stop
        widget.cleanup()
        assert not widget.backend.scene.exists()
    for node in (model, segmentation, transform):
        slicer.mrmlScene.RemoveNode(node)
    print("PASS: packaged Slicer module discovered; transformed surfaces; Start/Update/Stop with process fixture")


try:
    run()
except Exception:
    traceback.print_exc()
    slicer.app.exit(1)
else:
    slicer.app.exit(0)
