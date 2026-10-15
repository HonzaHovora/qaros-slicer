"""Stereo frames from Slicer's existing view. No scene export or pixel readback.

The consumer must copy the supplied GPU textures before returning. Texture names
are borrowed from the host context, not handles that can be sent to a process.
"""
import math
from time import perf_counter
from contextlib import contextmanager, nullcontext

import vtk

from .qarvtk_host_gpu import DesktopTextures, single_pass_supported, volume_depth


def _items(collection):
    return [collection.GetItemAsObject(i) for i in range(collection.GetNumberOfItems())]


def _rotate(q, v):
    norm = math.sqrt(sum(x * x for x in q))
    if not math.isfinite(norm) or norm < 1e-12:
        raise ValueError("Invalid eye quaternion")
    x, y, z, w = (a / norm for a in q)
    a, b, c = v
    tx, ty, tz = 2 * (y * c - z * b), 2 * (z * a - x * c), 2 * (x * b - y * a)
    return (a + w * tx + y * tz - z * ty,
            b + w * ty + z * tx - x * tz,
            c + w * tz + x * ty - y * tx)


def _unit(vector):
    norm = math.sqrt(sum(x*x for x in vector))
    if not math.isfinite(norm) or norm < 1e-12:
        raise ValueError("Invalid Slicer camera direction or view-up")
    return tuple(x / norm for x in vector)


def _cross(a, b):
    return (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0])


def camera_basis(camera):
    """App right/up/back axes in the host's world space; a proper rotation."""
    forward = _unit(tuple(f-p for f, p in zip(camera.GetFocalPoint(), camera.GetPosition())))
    right = _unit(_cross(forward, camera.GetViewUp()))
    return right, _cross(right, forward), tuple(-x for x in forward)


def app_vector(ras):
    return (ras[0], ras[2], -ras[1])


def ras_vector(app):
    return (app[0], -app[2], app[1])


def projection(fov, near, far):
    if not (0 < near < far) or not all(math.isfinite(x) for x in (*fov, near, far)):
        raise ValueError("Invalid clipping or eye FOV")
    if any(abs(x) >= math.pi / 2 for x in fov):
        raise ValueError("Eye FOV outside perspective range")
    left, right, up, down = (math.tan(x) for x in fov)
    if right - left < 1e-8 or up - down < 1e-8:
        raise ValueError("Inverted eye FOV")
    result = vtk.vtkMatrix4x4()
    result.Zero()
    for r, c, value in ((0, 0, 2 / (right - left)), (0, 2, (right + left) / (right - left)),
                        (1, 1, 2 / (up - down)), (1, 2, (up + down) / (up - down)),
                        (2, 2, -(far + near) / (far - near)),
                        (2, 3, -2 * far * near / (far - near)), (3, 2, -1)):
        result.SetElement(r, c, value)
    return result


class HostView:
    """One live Slicer 3D view; all methods run on its GUI/render thread."""

    def __init__(self, view, fit=True, match_view=True, render_scale=1.):
        self.view = view
        self.window = view.renderWindow()
        self.renderer = view.renderWindow().GetRenderers().GetFirstRenderer()
        self.camera = self.renderer.GetActiveCamera()
        if not math.isfinite(render_scale) or not .25 <= render_scale <= 1.:
            raise ValueError("Render scale must be between 25% and 100%")
        self.render_scale = render_scale
        self.match_view = match_view
        self.last_render_sizes = []
        self.last_desktop_size = self.window.GetSize()
        self._busy = False
        self.last_timings = {}
        self.desktop = DesktopTextures(self.window)
        self.scale = .001
        self.app_scale = 1.
        self.center = (0., 0., 0.)
        # Placement is fixed at Start. Live changes never unexpectedly refit it.
        if fit:
            bounds = self.renderer.ComputeVisiblePropBounds()
            if not all(math.isfinite(x) for x in bounds) or any(bounds[2*i] > bounds[2*i+1] for i in range(3)):
                raise ValueError("The selected Slicer 3D view has no visible content")
            extent = max(bounds[2*i+1] - bounds[2*i] for i in range(3))
            if extent <= 0:
                raise ValueError("The visible content has empty bounds")
            self.app_scale = .65 / (extent * self.scale)
            self.center = tuple((bounds[2*i] + bounds[2*i+1]) * .5 for i in range(3))
        # App content is always world RAS converted to metres/+Y-up. Placement
        # and fitting belong to the SDK, never to the per-eye camera transform.
        # Rotate the initial Slicer view's right/up/back axes onto app-volume
        # X/Y/Z. The transpose is the inverse of this orthonormal camera basis.
        self.app_orientation = (0., 0., 0., 1.)
        if match_view:
            rotation = [list(app_vector(axis)) for axis in camera_basis(self.camera)]
            q = [0.] * 4  # VTK returns scalar first; QAROS stores scalar last.
            vtk.vtkMath.Matrix3x3ToQuaternion(rotation, q)
            self.app_orientation = (*q[1:], q[0])
        center_m = tuple(x * self.scale for x in app_vector(self.center))
        self.app_position = tuple(-self.app_scale * x for x in _rotate(self.app_orientation, center_m))
        self.clip = (.05 / self.app_scale, 20. / self.app_scale)
        for method in ("GetDisplayFramebuffer", "GetFrameBlitMode", "SetUseOffScreenBuffers"):
            if not hasattr(self.window, method):
                raise RuntimeError("This Slicer render window lacks " + method)
        self.volume()  # Fail before connecting if the depth path cannot handle this view.

    def close(self):
        self.desktop.close()

    def volume(self):
        volumes = [v for v in _items(self.renderer.GetVolumes()) if v.GetVisibility()]
        if len(volumes) > 1:
            raise ValueError("Live rendering currently validates depth for one GPU volume at a time")
        if not volumes:
            return None
        volume = volumes[0]
        mapper = volume.GetMapper()
        if not mapper or not mapper.IsA("vtkOpenGLGPUVolumeRayCastMapper"):
            raise ValueError("Live volume depth requires Slicer's VTK GPU volume rendering method")
        if volume.IsA("vtkMultiVolume") or mapper.GetBlendMode() != vtk.vtkVolumeMapper.COMPOSITE_BLEND:
            raise ValueError("Live volume depth currently requires one Composite volume")
        if mapper.GetRenderToImage():
            raise ValueError("The host volume mapper is already in RenderToImage mode")
        if any(a.GetVisibility() and a.GetProperty().GetOpacity() < 1 for a in _items(self.renderer.GetActors())):
            raise ValueError("Live depth for a volume combined with translucent surfaces is not validated")
        return mapper

    def _camera_for_eye(self, eye, near, far):
        position, orientation, fov = eye["position"], eye["orientation"], eye["fov"]
        if not all(math.isfinite(x) for x in (*position, *orientation)):
            raise ValueError("Non-finite eye pose")
        p = tuple(x / self.scale for x in ras_vector(position))
        forward = ras_vector(_rotate(orientation, (0., 0., -1.)))
        up = ras_vector(_rotate(orientation, (0., 1., 0.)))
        self.camera.SetPosition(p)
        self.camera.SetFocalPoint(tuple(a + b / self.scale for a, b in zip(p, forward)))
        self.camera.SetViewUp(up)
        self.camera.SetParallelProjection(False)
        self.camera.SetClippingRange(near / self.scale, far / self.scale)
        self.camera.SetExplicitProjectionTransformMatrix(projection(fov, near / self.scale, far / self.scale))
        self.camera.SetUseExplicitProjectionTransformMatrix(True)

    @contextmanager
    def _timed(self, name):
        start = perf_counter()
        try:
            yield
        finally:
            self.last_timings[name] = self.last_timings.get(name, 0.) + (perf_counter() - start) * 1000

    @contextmanager
    def _frame_state(self):
        if self._busy:
            raise RuntimeError("Reentrant host rendering is not supported")
        if self.renderer.GetActiveCamera() != self.camera:
            raise RuntimeError("The Slicer view camera changed; restart live streaming")
        self._busy = True
        window = self.window
        saved_camera = vtk.vtkCamera()
        saved_camera.DeepCopy(self.camera)
        size = window.GetSize()
        blit, offscreen, swap, stereo = (window.GetFrameBlitMode(), window.GetUseOffScreenBuffers(),
                                         window.GetSwapBuffers(), window.GetStereoRender())
        flip_y = window.GetFramebufferFlipY()
        camera_node = self.view.cameraNode() if hasattr(self.view, "cameraNode") else None
        modifying = camera_node.StartModify() if camera_node else None
        render_enabled = self.view.renderEnabled if hasattr(self.view, "setRenderEnabled") else None
        preserved = False
        window.MakeCurrent()
        state = window.GetState()
        viewport, scissor = [0]*4, [0]*4
        state.vtkglGetIntegerv(0x0BA2, viewport)  # GL_VIEWPORT
        state.vtkglGetIntegerv(0x0C10, scissor)  # GL_SCISSOR_BOX
        try:
            # CTK can synchronously render when a temporary camera modification
            # requests an update. Only explicit eye renders may run in this
            # scope. Restore the flag without scheduling a redundant desktop
            # render; existing queued updates and later user edits still run.
            if render_enabled is not None:
                self.view.setRenderEnabled(False)
            with self._timed("desktop_save_ms"):
                preserved = self.desktop.begin()
            window.SetFrameBlitMode(vtk.vtkOpenGLRenderWindow.NoBlit)
            window.SetUseOffScreenBuffers(True)
            window.SetSwapBuffers(True)  # Resolve MSAA to the host display textures.
            window.SetStereoRender(False)  # Explicit QAROS eyes, never host anaglyph/interlace.
            window.SetFramebufferFlipY(False)  # Transport normalizes both planes to top-left.
            yield
        finally:
            restore_start = perf_counter()
            self.camera.DeepCopy(saved_camera)
            window.SetSize(size)
            window.SetFrameBlitMode(blit)
            window.SetUseOffScreenBuffers(offscreen)
            window.SetSwapBuffers(swap)
            window.SetStereoRender(stereo)
            window.SetFramebufferFlipY(flip_y)
            try:
                self.desktop.restore()
                state.vtkglViewport(*viewport)
                state.vtkglScissor(*scissor)
                if camera_node:
                    camera_node.EndModify(modifying)
                # Qt will paint the original attachments after we return. No
                # event processing is permitted while either XR eye is installed.
                if not preserved:
                    self._render_window()
                    self.last_timings["desktop_restore_render_calls"] = 1.
            finally:
                if render_enabled is not None:
                    self.view.setRenderEnabled(render_enabled)
                self.last_timings["desktop_restore_ms"] = (perf_counter() - restore_start) * 1000
                self._busy = False

    def _render_window(self):
        self.last_timings["host_render_calls"] = self.last_timings.get("host_render_calls", 0.) + 1
        self.window.Render()

    def _textures(self):
        framebuffer = self.window.GetDisplayFramebuffer()
        color = framebuffer.GetColorAttachmentAsTextureObject(0)
        depth = framebuffer.GetDepthAttachmentAsTextureObject()
        if not color or not depth or not color.GetHandle() or not depth.GetHandle():
            raise RuntimeError("The host did not expose resolved color/depth GPU textures")
        return color, depth

    def render(self, eyes, consumer, near=None, far=None):
        """consumer.color/depth copy borrowed textures synchronously on the GPU.

        color(index, color, depth, width, height) receives the unmodified host
        image. depth(index, color, depth, volume_color, volume_depth, width,
        height) receives a supplementary host-mapper depth pass only when the
        single-pass volume hook cannot safely be applied to this pipeline.
        All texture arguments are vtkTextureObject, except absent volume planes.
        """
        if len(eyes) != 2:
            raise ValueError("Exactly two eye requests are required")
        if self._busy:
            raise RuntimeError("Reentrant host rendering is not supported")
        near = self.clip[0] if near is None else near
        far = self.clip[1] if far is None else far
        self.last_desktop_size = self.window.GetSize()
        self.last_render_sizes = []
        for eye in eyes:
            width, height = eye["size"]
            if not (1 <= width <= 8192 and 1 <= height <= 8192):
                raise ValueError("Invalid host render size")
            self.last_render_sizes.append(tuple(max(1, int(x * self.render_scale + .5)) for x in (width, height)))
        self.last_timings = dict.fromkeys(("color_render_ms", "depth_render_ms",
                                          "color_copy_call_ms", "depth_copy_call_ms",
                                          "host_render_calls", "desktop_restore_render_calls",
                                          "volume_depth_passes"), 0.)
        mapper = self.volume()
        volume = next((v for v in _items(self.renderer.GetVolumes()) if v.GetVisibility()), None)
        fast_depth = volume is not None and single_pass_supported(self.renderer, volume)
        depth_scope = volume_depth(volume) if fast_depth else nullcontext()
        with self._timed("frame_wall_ms"), self._frame_state(), depth_scope:
            for index, eye in enumerate(eyes):
                width, height = self.last_render_sizes[index]
                self._camera_for_eye(eye, near, far)
                self.window.SetSize(width, height)
                with self._timed("color_render_ms"):
                    self._render_window()
                color, depth = self._textures()
                if any((t.GetWidth(), t.GetHeight()) != (width, height) for t in (color, depth)):
                    raise RuntimeError("Host GPU texture size differs from the selected render size")
                with self._timed("color_copy_call_ms"):
                    consumer.color(index, color, depth, width, height)
                if mapper and not fast_depth:
                    dw, dh = eye.get("depth_size", (width, height))
                    dw, dh = min(dw, width), min(dh, height)
                    if dw < 1 or dh < 1:
                        raise ValueError("Invalid depth render size")
                    self.window.SetSize(dw, dh)
                    self._volume_depth(index, mapper, consumer, dw, dh)
                else:
                    with self._timed("depth_copy_call_ms"):
                        consumer.depth(index, color, depth, None, None, width, height)

    def _volume_depth(self, index, mapper, consumer, width, height):
        # The first render is the host's complete color output, including custom
        # shaders and passes. A second render asks the SAME live mapper for its
        # first contributing sample depth; it never replaces the color image.
        old = (mapper.GetRenderToImage(), mapper.GetClampDepthToBackface(),
               mapper.GetAutoAdjustSampleDistances(), mapper.GetImageSampleDistance(),
               mapper.GetDepthImageScalarType())
        cullers = _items(self.renderer.GetCullers())
        try:
            mapper.SetRenderToImage(True)
            mapper.SetClampDepthToBackface(False)
            mapper.SetAutoAdjustSampleDistances(False)
            mapper.SetImageSampleDistance(1.)
            mapper.SetDepthImageScalarType(vtk.VTK_FLOAT)
            # Even an offscreen volume must execute its clear; otherwise its
            # texture may contain the preceding eye's data.
            self.renderer.GetCullers().RemoveAllItems()
            with self._timed("depth_render_ms"):
                self.last_timings["volume_depth_passes"] += 1
                self._render_window()
            color, depth = self._textures()
            vc, vd = mapper.GetColorTexture(), mapper.GetDepthTexture()
            if not vc or not vd or not vc.GetHandle() or not vd.GetHandle():
                raise RuntimeError("The live host volume mapper did not expose depth")
            with self._timed("depth_copy_call_ms"):
                consumer.depth(index, color, depth, vc, vd, width, height)
        finally:
            mapper.SetRenderToImage(old[0])
            mapper.SetClampDepthToBackface(old[1])
            mapper.SetAutoAdjustSampleDistances(old[2])
            mapper.SetImageSampleDistance(old[3])
            mapper.SetDepthImageScalarType(old[4])
            self.renderer.GetCullers().RemoveAllItems()
            for culler in cullers:
                self.renderer.GetCullers().AddItem(culler)
