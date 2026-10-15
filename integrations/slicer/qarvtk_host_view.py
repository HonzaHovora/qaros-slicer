"""Stereo frames from Slicer's existing view. No scene export or pixel readback.

The consumer must copy the supplied GPU textures before returning. Texture names
are borrowed from the host context, not handles that can be sent to a process.
"""
import math
from contextlib import contextmanager

import vtk


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

    def __init__(self, view, fit=True):
        self.view = view
        self.window = view.renderWindow()
        self.renderer = view.renderWindow().GetRenderers().GetFirstRenderer()
        self.camera = self.renderer.GetActiveCamera()
        self._busy = False
        self.scale = .001
        self.center = (0., 0., 0.)
        # Placement is fixed at Start. Live changes never unexpectedly refit it.
        if fit:
            bounds = self.renderer.ComputeVisiblePropBounds()
            if not all(math.isfinite(x) for x in bounds) or any(bounds[2*i] > bounds[2*i+1] for i in range(3)):
                raise ValueError("The selected Slicer 3D view has no visible content")
            extent = max(bounds[2*i+1] - bounds[2*i] for i in range(3))
            if extent <= 0:
                raise ValueError("The visible content has empty bounds")
            self.scale = .65 / extent
            self.center = tuple((bounds[2*i] + bounds[2*i+1]) * .5 for i in range(3))
        for method in ("GetDisplayFramebuffer", "GetFrameBlitMode", "SetUseOffScreenBuffers"):
            if not hasattr(self.window, method):
                raise RuntimeError("This Slicer render window lacks " + method)
        self.volume()  # Fail before connecting if the depth path cannot handle this view.

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
        def ras(vector):
            return (vector[0], -vector[2], vector[1])
        p = tuple(c + x / self.scale for c, x in zip(self.center, ras(position)))
        forward = ras(_rotate(orientation, (0., 0., -1.)))
        up = ras(_rotate(orientation, (0., 1., 0.)))
        self.camera.SetPosition(p)
        self.camera.SetFocalPoint(tuple(a + b / self.scale for a, b in zip(p, forward)))
        self.camera.SetViewUp(up)
        self.camera.SetParallelProjection(False)
        self.camera.SetClippingRange(near / self.scale, far / self.scale)
        self.camera.SetExplicitProjectionTransformMatrix(projection(fov, near / self.scale, far / self.scale))
        self.camera.SetUseExplicitProjectionTransformMatrix(True)

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
        try:
            window.SetFrameBlitMode(vtk.vtkOpenGLRenderWindow.NoBlit)
            window.SetUseOffScreenBuffers(True)
            window.SetSwapBuffers(True)  # Resolve MSAA to the host display textures.
            window.SetStereoRender(False)  # Explicit QAROS eyes, never host anaglyph/interlace.
            window.SetFramebufferFlipY(False)  # Transport normalizes both planes to top-left.
            yield
        finally:
            self.camera.DeepCopy(saved_camera)
            window.SetSize(size)
            window.SetFrameBlitMode(blit)
            window.SetUseOffScreenBuffers(offscreen)
            window.SetSwapBuffers(swap)
            window.SetStereoRender(stereo)
            window.SetFramebufferFlipY(flip_y)
            if camera_node:
                camera_node.EndModify(modifying)
            self._busy = False
            # Restore the desktop framebuffer as well as the camera. No Qt event
            # processing is permitted while either XR eye is installed.
            window.Render()

    def _textures(self):
        framebuffer = self.window.GetDisplayFramebuffer()
        color = framebuffer.GetColorAttachmentAsTextureObject(0)
        depth = framebuffer.GetDepthAttachmentAsTextureObject()
        if not color or not depth or not color.GetHandle() or not depth.GetHandle():
            raise RuntimeError("The host did not expose resolved color/depth GPU textures")
        return color, depth

    def render(self, eyes, consumer, near=.05, far=20.):
        """consumer.color/depth copy borrowed textures synchronously on the GPU.

        color(index, color, depth, width, height) receives the unmodified host
        image. depth(index, color, depth, volume_color, volume_depth, width,
        height) receives a supplementary host-mapper depth pass when needed.
        All texture arguments are vtkTextureObject, except absent volume planes.
        """
        if len(eyes) != 2:
            raise ValueError("Exactly two eye requests are required")
        mapper = self.volume()
        with self._frame_state():
            for index, eye in enumerate(eyes):
                width, height = eye["size"]
                if not (1 <= width <= 8192 and 1 <= height <= 8192):
                    raise ValueError("Invalid host render size")
                self._camera_for_eye(eye, near, far)
                self.window.SetSize(width, height)
                self.window.Render()
                color, depth = self._textures()
                consumer.color(index, color, depth, width, height)
                if mapper:
                    self._volume_depth(index, mapper, consumer, width, height)
                else:
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
            self.window.Render()
            color, depth = self._textures()
            vc, vd = mapper.GetColorTexture(), mapper.GetDepthTexture()
            if not vc or not vd or not vc.GetHandle() or not vd.GetHandle():
                raise RuntimeError("The live host volume mapper did not expose depth")
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
