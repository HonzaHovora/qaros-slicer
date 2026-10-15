"""Run inside real Slicer. CPU readback is used only as a test oracle."""
from pathlib import Path
import sys
import traceback
import numpy as np
import vtk
import slicer
from vtk.util.numpy_support import vtk_to_numpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "slicer"))
from qarvtk_host_view import HostView


def pixels(window):
    w, h = window.GetSize()
    data = vtk.vtkUnsignedCharArray()
    window.GetRGBACharPixelData(0, 0, w-1, h-1, 1, data)
    return vtk_to_numpy(data).copy().reshape(h, w, 4)


def camera_state(camera):
    return (camera.GetPosition(), camera.GetFocalPoint(), camera.GetViewUp(),
            camera.GetClippingRange(), camera.GetParallelProjection(),
            camera.GetUseExplicitProjectionTransformMatrix())


def run():
    slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
    view = slicer.app.layoutManager().threeDWidget(0).threeDView()
    window = view.renderWindow()
    renderer = window.GetRenderers().GetFirstRenderer()
    view.mrmlViewNode().SetBoxVisible(False)
    view.mrmlViewNode().SetAxisLabelsVisible(False)
    renderer.SetBackground(0., 0., 0.)
    renderer.GradientBackgroundOff()

    ct = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Live CT test")
    z, y, x = np.indices((32, 32, 32))
    data = np.where((x-15.5)**2+(y-15.5)**2+(z-15.5)**2 < 12**2, 900, 0).astype(np.int16)
    slicer.util.updateVolumeFromArray(ct, data)
    ct.SetSpacing(3., 3., 3.)
    ct.SetOrigin(100., 200., 300.)
    ct.CreateDefaultDisplayNodes()
    vr = slicer.modules.volumerendering.logic().CreateDefaultVolumeRenderingNodes(ct)
    vr.SetVisibility(True)
    prop = vr.GetVolumePropertyNode().GetVolumeProperty()
    prop.GetRGBTransferFunction().RemoveAllPoints()
    prop.GetRGBTransferFunction().AddRGBPoint(0, 0., 0., 0.)
    prop.GetRGBTransferFunction().AddRGBPoint(900, 1., .2, .1)
    prop.GetScalarOpacity().RemoveAllPoints()
    prop.GetScalarOpacity().AddPoint(0, 0.)
    prop.GetScalarOpacity().AddPoint(899, 0.)
    prop.GetScalarOpacity().AddPoint(900, .6)
    prop.ShadeOff()
    slicer.app.processEvents()
    view.resetFocalPoint()
    window.Render()
    host = HostView(view)
    print("HOST: VTK", vtk.vtkVersion.GetVTKVersion(), "window", window.GetClassName(),
          "mapper", host.volume().GetClassName(), "scale", host.scale, flush=True)
    original_camera = camera_state(host.camera)
    original_size = window.GetSize()
    original_blit = window.GetFrameBlitMode()
    original_cullers = tuple(host.renderer.GetCullers())
    mapper = host.volume()
    old_mapper = (mapper.GetRenderToImage(), mapper.GetImageSampleDistance(),
                  mapper.GetAutoAdjustSampleDistances(), mapper.GetDepthImageScalarType())
    eyes = [dict(position=(x, 0., 1.2), orientation=(0., 0., 0., 1.),
                 fov=(-.4, .4, .4, -.4), size=(192, 160)) for x in (-.032, .032)]

    class Oracle:
        def __init__(self):
            self.colors, self.depths = [], []
        def color(self, index, color, depth, width, height):
            assert color.GetWidth() == width and color.GetHeight() == height
            self.colors.append(pixels(window))
        def depth(self, index, color, depth, vc, vd, width, height):
            assert vc is not None and vd is not None
            image = vtk.vtkImageData()
            mapper.GetDepthImage(image)
            values = vtk_to_numpy(image.GetPointData().GetScalars()).copy().reshape(height, width)
            assert np.isfinite(values).all() and values.min() >= 0 and values.max() <= 1
            assert np.count_nonzero(values < .99999) > 100, "No tissue depth"
            assert values[0, 0] == 1, "Empty rays must have far depth"
            self.depths.append(values)

    oracle = Oracle()
    host.render(eyes, oracle)
    assert len(oracle.colors) == 2 and len(oracle.depths) == 2
    assert np.count_nonzero(oracle.colors[0][:, :, 0] > 100) > 100
    assert not np.array_equal(oracle.colors[0], oracle.colors[1]), "Eyes must use distinct poses"
    assert camera_state(host.camera) == original_camera
    assert window.GetSize() == original_size and window.GetFrameBlitMode() == original_blit
    assert tuple(host.renderer.GetCullers()) == original_cullers
    assert (mapper.GetRenderToImage(), mapper.GetImageSampleDistance(),
            mapper.GetAutoAdjustSampleDistances(), mapper.GetDepthImageScalarType()) == old_mapper

    # A live native actor that has no MRML/export representation must appear.
    sphere = vtk.vtkSphereSource()
    sphere.SetCenter(170., 190., 346.5)
    sphere.SetRadius(10.)
    surface_mapper = vtk.vtkPolyDataMapper()
    surface_mapper.SetInputConnection(sphere.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(surface_mapper)
    actor.GetProperty().SetColor(0., 1., 0.)
    actor.GetProperty().LightingOff()
    renderer.AddActor(actor)
    changed = Oracle()
    host.render(eyes, changed)
    assert np.count_nonzero(changed.colors[0][:, :, 1] > 150) > 30, "Host-only actor absent"
    assert not np.array_equal(changed.colors[0], oracle.colors[0])
    renderer.RemoveActor(actor)

    # Color is exactly the normal host pipeline for the same eye, before the
    # supplementary depth pass. No new actor/mapper/transfer function is built.
    with host._frame_state():
        host._camera_for_eye(eyes[0], .05, 20.)
        window.SetSize(*eyes[0]["size"])
        window.Render()
        expected = pixels(window)
    again = Oracle()
    host.render(eyes, again)
    assert np.max(np.abs(again.colors[0].astype(int)-expected.astype(int))) <= 2

    # Host ROI cropping, explicitly unsupported by the snapshot exporter.
    roi = vr.GetROINode()
    roi.SetSize(35., 96., 96.)
    vr.SetCroppingEnabled(True)
    slicer.app.processEvents()
    cropped = Oracle()
    host.render(eyes, cropped)
    assert np.count_nonzero(cropped.colors[0][:, :, 0] > 100) < np.count_nonzero(again.colors[0][:, :, 0] > 100)
    assert not np.array_equal(cropped.depths[0], again.depths[0])
    assert vr.GetCroppingEnabled(), "Host crop state was lost"

    class Broken(Oracle):
        def depth(self, *args):
            raise RuntimeError("injected consumer failure")
    try:
        host.render(eyes, Broken())
        raise AssertionError("Consumer failure did not propagate")
    except RuntimeError as error:
        assert str(error) == "injected consumer failure"
    assert camera_state(host.camera) == original_camera
    assert window.GetSize() == original_size and window.GetFrameBlitMode() == original_blit
    assert tuple(host.renderer.GetCullers()) == original_cullers
    assert (mapper.GetRenderToImage(), mapper.GetImageSampleDistance(),
            mapper.GetAutoAdjustSampleDistances(), mapper.GetDepthImageScalarType()) == old_mapper
    print("PASS: live host color/stereo; host-only actor; CT depth; ROI cropping; desktop and mapper restoration after error", flush=True)


try:
    run()
except Exception:
    traceback.print_exc()
    slicer.app.exit(1)
else:
    slicer.app.exit(0)
