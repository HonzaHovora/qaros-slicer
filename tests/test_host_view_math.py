"""SDK placement contract against independent homogeneous transforms; no GPU."""
from pathlib import Path
from itertools import product
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
    corners = np.asarray([center + np.array(signs)*[120., 90., 160.]
                          for signs in product((-1, 1), repeat=3)])
    for back in ([0, 1, 0], [0, -1, 0], [.7, 1, .4]):
        back = np.asarray(back, dtype=float) / np.linalg.norm(back)
        right = np.cross(-back, [0, 0, 1]); right /= np.linalg.norm(right)
        up = np.cross(right, -back)
        basis = np.column_stack((right, up, back))
        camera.SetPosition(center + back*1000)
        camera.SetFocalPoint(center)
        camera.SetViewUp(up)
        host = HostView(view)
        # Independent corner transform verifies all axes, including oblique
        # views where permuting the source dimensions would be incorrect.
        extents = np.ptp(corners @ basis, axis=0)
        assert np.isclose(host.app_scale, .65 / extents.max())
        assert np.allclose(host.workspace_size, extents * host.app_scale)
        placed = corners @ rotation(host.app_orientation).T * host.app_scale + host.app_position
        assert np.allclose(placed.min(axis=0), -np.asarray(host.workspace_size)/2)
        assert np.allclose(placed.max(axis=0), np.asarray(host.workspace_size)/2)
        assert np.allclose(host.workspace_position, [0., 0., -1.5])
        assert np.isclose(max(host.workspace_size), .65)

        physical = HostView(view, fit=False)
        assert physical.app_scale == .001
        assert np.allclose(physical.workspace_size, extents*.001)
        physical_app = corners @ rotation(physical.app_orientation).T*.001 + physical.app_position
        physical_room = physical_app + physical.workspace_position
        assert np.allclose(physical_room, corners @ basis*.001 + [0., 0., -1.5]), "Physical placement changed"
        assert np.allclose((physical_app.min(axis=0)+physical_app.max(axis=0))/2, 0.), "Workspace misses its content"
        assert np.isclose(np.linalg.det(rotation(host.app_orientation)), 1), "Placement mirrors the scene"
        for orientation in ((0, 0, 0, 1), (.1, .2, -.05, .97)):
            for x in (-.032, .032):
                pose = np.array([x, .05, 1.2])
                eye = sdk_eye(host, pose, orientation)
                host._camera_for_eye(eye, *host.clip)
                assert np.allclose(camera.GetPosition(), center + basis @ pose / host.app_scale)
                assert np.allclose(camera.GetPosition(), eye["position"]), "Eye pose was transformed again in the renderer"
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
    # Distant native coordinates must not inflate a centred workspace. A
    # hidden prop must not influence the working bounds either.
    actor.SetPosition(10000., -20000., 30000.)
    distant = HostView(view, match_view=False, fit=False)
    assert np.allclose(distant.workspace_size, [.24, .32, .18])
    stray = vtk.vtkActor()
    stray.SetMapper(mapper)
    stray.SetPosition(-90000., 80000., 70000.)
    stray.VisibilityOff()
    renderer.AddActor(stray)
    assert np.allclose(HostView(view, match_view=False).workspace_size, [.4875, .65, .365625])
    stray.VisibilityOn()
    stray.UseBoundsOff()
    assert np.allclose(HostView(view, match_view=False).workspace_size, [.4875, .65, .365625])
    renderer.RemoveActor(stray)
    source.SetZLength(0.)
    flat = HostView(view, match_view=False)
    assert min(flat.workspace_size) == .001, "Flat scenes need a positive workspace thickness"
    print("PASS: scene-derived XYZ workspace; fit/physical size and room position; oblique/distant/hidden/flat bounds; "
          "SDK app_pose/app_scale, anterior/posterior/oblique alignment, stereo, head rotations, +X right and +Z toward viewer")


if __name__ == "__main__":
    run()
