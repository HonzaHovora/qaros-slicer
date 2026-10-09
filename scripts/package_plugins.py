#!/usr/bin/env python3
"""Build portable, self-contained Python plugin folders; never fetch/install an SDK."""
import argparse
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package(output):
    output = Path(output).resolve()
    bundle = output / "QAROS-VTK-plugins"
    files = {
        "slicer/QarosVTK.py": "integrations/slicer/QarosVTK.py",
        "slicer/QarosVTKLib/qarvtk_slicer.py": "integrations/slicer/qarvtk_slicer.py",
        "slicer/QarosVTKLib/qarvtk_bridge.py": "integrations/qarvtk_bridge.py",
        "slicer/QarosVTKLib/qarvtk_runtime.py": "integrations/qarvtk_runtime.py",
        "paraview/QarosVTKPlugin.py": "integrations/paraview/QarosVTKPlugin.py",
        "paraview/qarvtk_paraview.py": "integrations/paraview/qarvtk_paraview.py",
        "paraview/qarvtk_bridge.py": "integrations/qarvtk_bridge.py",
        "paraview/qarvtk_runtime.py": "integrations/qarvtk_runtime.py",
        "INSTALLATION.md": "docs/INSTALLATION.md",
    }
    for relative, source in files.items():
        destination = bundle / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, destination)
    init = "slicer/QarosVTKLib/__init__.py"
    (bundle / init).write_text('"""Private support package, not a Slicer module."""\n')
    # Remove only known obsolete generated files, so Slicer will not discover them
    # as separate modules after an upgrade from the first packaging layout.
    for name in ("qarvtk_slicer.py", "qarvtk_bridge.py", "qarvtk_runtime.py"):
        old = bundle / "slicer" / name
        if old.exists():
            old.unlink()
    archive = output / "QAROS-VTK-plugins.zip"
    # Explicit allowlist: no caches, SDKs, local credentials or extra user files.
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as stream:
        for relative in [*files, init]:
            path = bundle / relative
            stream.write(path, path.relative_to(output))
    print("Plugin folders: " + str(bundle))
    print("Archive: " + str(archive))
    return bundle


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "package")
    package(parser.parse_args().output)
