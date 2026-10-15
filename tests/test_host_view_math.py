"""SDK placement contract against independent homogeneous transforms; no GPU."""
from pathlib import Path
import sys
import numpy as np
import vtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "package" / "QAROS-VTK-plugins" / "slicer"))
from QarosVTKLib.qarvtk_host_view import HostView


def rotation(q):
    x, y, z, w = np.asarray(q) / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def sdk_eye(host, position, orientation=(0, 0, 0, 1), translation=(0, 0, 0)):
    # SDK documented volume -> app content conversion, using independent
    # matrix inversion. No HostView camera/conversion helpers are used here.
    r = rotation(host.app_orientation)
    p = r.T @ (np.asarray(position) - host.app_position - np.asarray(translation)) / host.app_scale
    q = [0.]*4
    vtk.vtkMath.Matrix3x3ToQuaternion((r.T @ rotation(orientation)).tolist(), q)
    return dict(position=tuple(p), orientation=(*q[1:], q[0]),
                fov=(-.4, .4, .4, -.4), size=(192, 160))


def run():
    renderer = vtk.vtkRenderer()
    window = vtk.vtkRenderWindow()
    window.AddRenderer(renderer)
    source = vtk.vtkCubeSource()
    source.SetCenter(140, -80, 55)
    source.SetXLength(240)
    source.SetYLength(180)
    source.SetZLength(320)
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(source.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    renderer.AddActor(actor)
    view = type("View", (), {"renderWindow": lambda self: window})()
    camera = renderer.GetActiveCamera()
    center = np.array([140., -80., 55.])
    for back in ([0, 1, 0], [0, -1, 0], [.7, 1, .4]):
        back = np.asarray(back, dtype=float) / np.linalg.norm(back)
        right = np.cross(-back, [0, 0, 1]); right /= np.linalg.norm(right)
        up = np.cross(right, -back)
        basis = np.column_stack((right, up, back))
        camera.SetPosition(center + back*1000)
        camera.SetFocalPoint(center)
        camera.SetViewUp(up)
        host = HostView(view)
        assert host.scale == .001, "Fit leaked into the renderer's unit conversion"
        assert np.isclose(host.app_scale, .65/.320)
        assert np.isclose(np.linalg.det(rotation(host.app_orientation)), 1), "Placement mirrors the scene"
        for orientation in ((0, 0, 0, 1), (.1, .2, -.05, .97)):
            for x in (-.032, .032):
                pose = np.array([x, .05, 1.2])
                eye = sdk_eye(host, pose, orientation)
                host._camera_for_eye(eye, *host.clip)
                assert np.allclose(camera.GetPosition(), center + basis @ pose / (host.app_scale*.001))
                assert np.allclose(camera.GetDirectionOfProjection(), basis @ rotation(orientation) @ [0, 0, -1])
                assert np.allclose(camera.GetViewUp(), basis @ rotation(orientation) @ [0, 1, 0])
        def screen(point, translation):
            host._camera_for_eye(sdk_eye(host, (0, 0, 1.2), translation=translation), *host.clip)
            matrix = camera.GetCompositeProjectionTransformMatrix(1., -1., 1.)
            result = matrix.MultiplyPoint((*point, 1.))
            return np.asarray(result[:3]) / result[3]
        initial = screen(center, (0, 0, 0))
        assert screen(center, (.1, 0, 0))[0] > initial[0] + .1, "+app_pose X moves content left"
        marker = center + right*40
        assert screen(marker, (0, 0, .1))[0] > screen(marker, (0, 0, 0))[0], "+app_pose Z moves content away"
        assert actor.GetPosition() == (0., 0., 0.), "Placement changed the host actor"
    print("PASS: SDK app_pose/app_scale, anterior/posterior/oblique alignment, stereo, head rotations, +X right and +Z toward viewer")


if __name__ == "__main__":
    run()
