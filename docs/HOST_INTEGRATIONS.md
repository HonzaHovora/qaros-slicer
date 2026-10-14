# Host plugins and export API

The primary workflow is an installed plugin. Use [INSTALLATION.md](INSTALLATION.md)
for installation and Start/Stop instructions. The Slicer scripted module and the
ParaView Python plugin both control `qarvtk-sender` through the shared process
controller. They do not load QAROS SDK libraries inside the host.

| Host | Plugin entry point | Geometry and update behavior |
| --- | --- | --- |
| Slicer | `integrations/slicer/QarosVTK.py` | Selected model/segment/CT/MR, or visible models/segments and one volume in the first 3D view. Colors, linear volume transforms, transfer functions, optional scene fit. Manual volume updates; optional automatic changed-surface updates. |
| ParaView | `integrations/paraview/QarosVTKPlugin.py` | Pipeline filter; surface extraction from dataset/composite input; geometry republishes when the pipeline updates. Local built-in connection only. |

The backend watches a private VTP or VTM manifest. It preserves the previous scene
if a new file cannot be read. Slicer snapshots carry materials and scalar CT/MR
voxels with RGB, scalar-opacity and gradient-opacity transfer functions. Annotations,
slice planes, overlays and picking are not transferred. ParaView remains surface-only.
One volume is supported, in Composite mode without ROI cropping, combined only
with opaque surfaces. The plugin rejects unsupported combinations with a message.

## Optional ParaView Python helper

The older export API remains useful for a manual snapshot including the active
view's **display transform**. This differs from the plugin, where transforms must
be in the pipeline (e.g. a standard Transform filter).

```python
import sys
sys.path.insert(0, r"C:/dev/QAROS_VTK/integrations/paraview")
import qarvtk_paraview
qarvtk_paraview.export_active(r"C:/data/paraview-surface.vtp")
```

`ExtractSurface` executes on the selected output and `Fetch` gathers geometry to
the client. Composite outputs are flattened. The temporary filter is deleted and
the active source restored. This helper can gather remote/MPI data, which may be
expensive; the streaming plugin deliberately rejects those sessions.

ParaView data has no universal physical unit. Choose the correct scale and Y-up
orientation; a pipeline Transform is required to change the plugin's coordinates.

## Optional Slicer Python helper

```python
import sys
sys.path.insert(0, r"C:/dev/QAROS_VTK/integrations/slicer")
import qarvtk_slicer
node = slicer.util.getNode("MyModel")
qarvtk_slicer.export_node(node, r"C:/data/slicer-surface.vtp")

segmentation = slicer.util.getNode("Segmentation")
segment_id = segmentation.GetSegmentation().GetSegmentIdBySegmentName("Liver")
qarvtk_slicer.export_node(segmentation, r"C:/data/liver.vtp", segment_id)
```

Closed surfaces are created when necessary. All parent MRML transforms are baked,
including nonlinear transforms supported by VTK. Source geometry and transforms
are preserved; a closed-surface representation may be added to a segmentation.
File coordinates remain world RAS mm. For a manual launch:

```powershell
py -3 scripts/run_sender.py --exe build-windows-release/Release/qarvtk-sender.exe --sdk D:/install --scene C:/data/slicer-surface.vtp --ras --meters-per-unit 0.001 --watch --preview
```

For a scene snapshot with the Slicer bridge (requires protocol 2 sender):

```python
qarvtk_slicer.export_selection(node, r"C:/data/scene.vtm", fit=True)
qarvtk_slicer.export_selection(None, r"C:/data/scene.vtm", visible_scene=True, fit=False)
```

Keep the adjacent `scene-data-*` folders with the manifest. The selected scalar
volume must have a configured Volume Rendering display/property node. `fit=False`
preserves world RAS mm; launch with `--ras --meters-per-unit 0.001`. `fit=True`
centers the whole scene and sets its maximum dimension to 0.65 m.

## Reproduce host tests

Use a fresh host process and its own Python, not a separate pip VTK installation.
The process fixture is a test double and does not connect to QAROS.

```bash
python3 scripts/package_plugins.py
cmake -S . -B build-fixture -DQARVTK_BUILD_RENDERER=OFF
cmake --build build-fixture --parallel 2
export QARVTK_TEST_BACKEND="$PWD/build-fixture/qarvtk-process-fixture"
pvpython tests/paraview_smoke.py
pvpython tests/paraview_plugin_smoke.py
Slicer --no-splash --no-main-window --ignore-slicerrc --additional-module-paths "$PWD/package/QAROS-VTK-plugins/slicer" --python-script tests/slicer_smoke.py
```

For a headless Linux machine prefix host commands with
`xvfb-run -a env LIBGL_ALWAYS_SOFTWARE=1`. On Windows use the corresponding `.exe`
fixture from the `Release` build folder and set `$env:QARVTK_TEST_BACKEND`.

## API sources

- [ParaView Python plugin decorators](https://www.paraview.org/paraview-docs/v5.12.0/python/paraview.util.vtkAlgorithm.html)
- [ParaView Fetch](https://www.paraview.org/paraview-docs/v5.12.0/python/paraview.servermanager.html#paraview.servermanager.Fetch)
- [Slicer extensions and module paths](https://slicer.readthedocs.io/en/latest/developer_guide/extensions.html)
- [Slicer model transforms](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/models.html)
- [Slicer segmentation surfaces](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html)
