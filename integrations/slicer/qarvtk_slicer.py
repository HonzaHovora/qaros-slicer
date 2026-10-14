"""3D Slicer surface bridge. Coordinates stay in world RAS millimetres."""
from pathlib import Path
import sys

if __package__:
    from .qarvtk_bridge import export_polydata, vtk_module
else:
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


# Keep export_node() for existing .vtp scripts. Streaming uses the scene bridge.
if __package__:
    from .qarvtk_scene import surface, volume, export_scene
else:
    from qarvtk_scene import surface, volume, export_scene


def _world_transform(node):
    import slicer
    transform = vtk_module().vtkGeneralTransform()
    slicer.vtkMRMLTransformNode.GetTransformBetweenNodes(node.GetParentTransformNode(), None, transform)
    return transform


def _model(node):
    vtk = vtk_module()
    display = node.GetDisplayNode()
    if display is None:
        raise ValueError("Model has no display settings: " + node.GetName())
    data = vtk.vtkPolyData(); data.DeepCopy(node.GetPolyData())
    scalar_mode = 0
    if display.GetScalarVisibility():
        name = display.GetActiveScalarName()
        location = display.GetActiveAttributeLocation()
        attributes = data.GetPointData() if location == vtk.vtkAssignAttribute.POINT_DATA else data.GetCellData()
        scalars = attributes.GetArray(name) if name else attributes.GetScalars()
        color_node = display.GetColorNode()
        lut = color_node.GetScalarsToColors() if color_node else None
        if scalars is None or lut is None:
            raise ValueError("Cannot export model scalar colors: " + node.GetName())
        mapping = lut.NewInstance(); mapping.DeepCopy(lut)
        mapping.SetRange(display.GetScalarRange())
        colors = mapping.MapScalars(scalars, vtk.VTK_COLOR_MODE_MAP_SCALARS, -1)
        colors.SetName("QAROS_RGBA"); attributes.SetScalars(colors)
        scalar_mode = 1 if location == vtk.vtkAssignAttribute.POINT_DATA else 2
    return surface(data, _world_transform(node), display.GetColor(), display.GetOpacity(),
                   (0.2, 0.75, 0.25, 30.0), scalar_mode)


def _segments(node, segment_id=None, visible=False):
    vtk = vtk_module()
    segmentation = node.GetSegmentation()
    display = node.GetDisplayNode()
    if display is None:
        raise ValueError("Segmentation has no display settings: " + node.GetName())
    node.CreateClosedSurfaceRepresentation()
    ids = [segment_id] if segment_id else [segmentation.GetNthSegmentID(i)
                                         for i in range(segmentation.GetNumberOfSegments())]
    result = []
    for sid in ids:
        segment = segmentation.GetSegment(sid)
        if segment is None:
            raise ValueError("Segment no longer exists")
        if visible and (not display.GetSegmentVisibility(sid) or not display.GetSegmentVisibility3D(sid)):
            continue
        opacity = display.GetOpacity() * display.GetOpacity3D() * display.GetSegmentOpacity3D(sid)
        if opacity <= 0:
            continue
        data = vtk.vtkPolyData()
        if not node.GetClosedSurfaceRepresentation(sid, data) or not data.GetNumberOfPolys():
            raise ValueError("Cannot create closed surface: " + segment.GetName())
        color = [0.0] * 3
        display.GetSegmentColor(sid, color)
        result.append(surface(data, _world_transform(node), color, opacity))
    return result


def _volume(node, display, view_node=None):
    import slicer
    vtk = vtk_module()
    if display is None or display.GetVolumePropertyNode() is None:
        raise ValueError("Enable this CT/MR in Slicer's Volume Rendering module and choose a preset first")
    if display.GetCroppingEnabled():
        raise ValueError("ROI cropping is not yet supported; disable Crop in Volume Rendering before streaming")
    if view_node and view_node.GetRaycastTechnique() != slicer.vtkMRMLViewNode.Composite:
        raise ValueError("Choose Composite rendering in Volume Rendering (MIP/MinIP are not supported yet)")
    image = node.GetImageData()
    if image is None:
        raise ValueError("The selected volume has no image data")
    ijk = vtk.vtkMatrix4x4(); node.GetIJKToRASMatrix(ijk)
    world = vtk.vtkMatrix4x4()
    parent = node.GetParentTransformNode()
    if parent and not parent.GetMatrixTransformToWorld(world):
        raise ValueError("Harden the volume's nonlinear transform in Slicer before streaming")
    vtk.vtkMatrix4x4.Multiply4x4(world, ijk, ijk)
    # Preserve original physical sample spacing for opacity/gradient functions;
    # rotation, translation and parent scaling belong to the actor matrix.
    spacing = node.GetSpacing()
    normalized = vtk.vtkImageData(); normalized.DeepCopy(image)
    normalized.SetOrigin(0, 0, 0); normalized.SetSpacing(spacing)
    normalized.SetDirectionMatrix(1, 0, 0, 0, 1, 0, 0, 0, 1)
    for row in range(3):
        for col in range(3):
            ijk.SetElement(row, col, ijk.GetElement(row, col) / spacing[col])
    return volume(normalized, ijk, display.GetVolumePropertyNode().GetVolumeProperty())


def export_selection(node, destination, segment_id=None, visible_scene=False, fit=True):
    """Snapshot the selected object or the scene visible in the first 3D view."""
    import slicer
    logic = slicer.modules.volumerendering.logic()
    view_node = None
    manager = slicer.app.layoutManager()
    if manager and manager.threeDViewCount:
        view_node = manager.threeDWidget(0).mrmlViewNode()
    view_id = view_node.GetID() if view_node else ""

    def shown(display):
        return (display and display.GetVisibility() and display.GetVisibility3D()
                and (not view_id or display.IsDisplayableInView(view_id)))

    blocks = []
    nodes = ([n for cls in ("vtkMRMLModelNode", "vtkMRMLSegmentationNode", "vtkMRMLScalarVolumeNode")
              for n in slicer.util.getNodesByClass(cls)] if visible_scene else [node])
    for current in nodes:
        if current is None:
            raise ValueError("Select a model, segmentation or scalar CT/MR volume")
        if current.IsA("vtkMRMLScalarVolumeNode") and not current.IsA("vtkMRMLLabelMapVolumeNode"):
            display = logic.GetFirstVolumeRenderingDisplayNode(current)
            if visible_scene and not shown(display):
                continue
            blocks.append(_volume(current, display, view_node))
        elif current.IsA("vtkMRMLSegmentationNode"):
            if visible_scene and not shown(current.GetDisplayNode()):
                continue
            blocks.extend(_segments(current, None if visible_scene else segment_id, visible_scene))
        elif current.IsA("vtkMRMLModelNode"):
            # Slice-plane helper models are not anatomical surfaces.
            if visible_scene and (current.GetHideFromEditors() or not shown(current.GetDisplayNode())):
                continue
            blocks.append(_model(current))
        elif not visible_scene:
            raise ValueError("Only models, segmentations and scalar CT/MR volumes are supported")
    path = export_scene(blocks, destination, fit)
    return path, sum(b.IsA("vtkImageData") for b in blocks), len(blocks)
