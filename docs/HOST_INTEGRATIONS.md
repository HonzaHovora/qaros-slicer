# ParaView and 3D Slicer surface bridges

These bridges export geometry to a local file. Run the sender in a separate
terminal. The rendering loop uses the headset's camera; re-exporting updates
geometry when `--watch` is active. The initial scene remains in memory if a
subsequent file read fails. Exports are snapshots, not a live copy of all host
rendering settings.

## ParaView

Select the desired source/filter. Open the Python Shell and run (adjust paths):

```python
import sys
sys.path.insert(0, r"C:/dev/QAROS_VTK/integrations/paraview")
import qarvtk_paraview
qarvtk_paraview.export_active(r"C:/data/paraview-surface.vtp")
```

The same function works in `pvpython` after a pipeline has been created.
`ExtractSurface` runs on the active output, `Fetch` gathers its result to the
client, and the helper bakes the active view's display transform. Composite
outputs are flattened to a surface. The temporary filter is deleted and the
original active source restored.

For client/server or MPI datasets, exporting all geometry may be expensive.
Select an extracted/reduced surface appropriate for the first demo. The bridge
does not copy scalar color maps, time navigation, text, legends, points/lines,
materials or volume rendering. Initially the sender draws the geometry green.

```powershell
python scripts/run_sender.py --exe build-windows/Release/qarvtk-sender.exe --sdk C:/QAROS --scene C:/data/paraview-surface.vtp --meters-per-unit 1 --watch --preview
```

ParaView geometry has no universal physical unit. Use `0.001` if one input unit
means 1 mm, and prepare a Y-up surface. Rerun the export function after a change.

## Slicer UI module

1. Edit → Application Settings → Modules → Additional module paths: add
   `C:/dev/QAROS_VTK/integrations/slicer`.
2. Restart Slicer. Open **Examples → QAROS VTK Surface Bridge**.
3. Choose a model or segmentation; for a segmentation choose one segment.
4. Choose a `.vtp` filename and press **Export surface**.
5. Start the sender from PowerShell:

```powershell
python scripts/run_sender.py --exe build-windows/Release/qarvtk-sender.exe --sdk C:/QAROS --scene C:/data/slicer-surface.vtp --ras --meters-per-unit 0.001 --watch --preview
```

After editing the model or segment, press Export again. For a segmentation the
closed-surface representation is created if necessary. All parent MRML transforms
are baked, including nonlinear transforms supported by VTK. Source geometry and transforms are preserved. Slicer may add a closed-surface
representation to the segmentation node. Coordinates in the file remain world RAS
millimetres; the sender performs the conversion once.

The widget is a scripted module, not a packaged Extension Manager release.
Model/segment export, world transforms and widget creation passed the host smoke
test in Slicer 5.12.4 on Linux. Repeat it on the target Windows installation.

## Slicer Python console

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

This first stage does not export CT/MR voxels, slice widgets, transfer functions,
annotations or multiple colored segments. It is a visualization prototype; it
has not been validated for clinical measurements or clinical use.

## Host smoke scripts

Run with the **host's Python**, not a separate pip installation of `vtk`:

```bash
pvpython tests/paraview_smoke.py
Slicer --no-splash --no-main-window --python-script tests/slicer_smoke.py
```

The scripts create synthetic data and verify exported world bounds. They do not
connect to QAROS, require patient data, or modify an existing user scene on disk.
Run the Slicer script in a fresh process because it creates temporary MRML nodes.

API references used:
[ParaView Fetch](https://www.paraview.org/paraview-docs/v5.12.0/python/paraview.servermanager.html#paraview.servermanager.Fetch),
[Slicer model transforms](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/models.html),
[Slicer segmentation surfaces](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/segmentations.html).
