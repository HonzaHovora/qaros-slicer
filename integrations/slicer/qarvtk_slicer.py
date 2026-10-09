"""3D Slicer surface bridge. Coordinates stay in world RAS millimetres."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qarvtk_bridge import export_polydata, vtk_module


def export_node(node, destination, segment_id=None):
    """Export a model or one segmentation surface, baking all parent transforms."""
    import slicer
    vtk = vtk_module()
    if node is None:
        raise ValueError("Select a model or segmentation")
    if node.IsA("vtkMRMLModelNode"):
        data = node.GetPolyData()
    elif node.IsA("vtkMRMLSegmentationNode"):
        segmentation = node.GetSegmentation()
        if segment_id is None:
            if segmentation.GetNumberOfSegments() != 1:
                raise ValueError("Choose one segment ID for a multi-segment segmentation")
            segment_id = segmentation.GetNthSegmentID(0)
        if segmentation.GetSegment(segment_id) is None:
            raise ValueError("Segment ID does not exist")
        node.CreateClosedSurfaceRepresentation()
        data = vtk.vtkPolyData()
        if not node.GetClosedSurfaceRepresentation(segment_id, data):
            raise ValueError("Cannot create this segment's closed surface")
    else:
        raise ValueError("Only model and segmentation nodes are supported")
    transform = vtk.vtkGeneralTransform()
    slicer.vtkMRMLTransformNode.GetTransformBetweenNodes(node.GetParentTransformNode(), None, transform)
    return export_polydata(data, destination, transform)
