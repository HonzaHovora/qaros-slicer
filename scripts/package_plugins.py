#!/usr/bin/env python3
"""Build portable, self-contained Python plugin folders; does not install or fetch an SDK."""
import argparse
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package(output):
    output = Path(output).resolve()
    bundle = output / "QAROS-VTK-plugins"
    for host, files in {
        "slicer": ["QarosVTK.py", "qarvtk_slicer.py"],
        "paraview": ["QarosVTKPlugin.py", "qarvtk_paraview.py"],
    }.items():
        destination = bundle / host
        destination.mkdir(parents=True, exist_ok=True)
        for name in files:
            shutil.copyfile(ROOT / "integrations" / host / name, destination / name)
        for name in ("qarvtk_bridge.py", "qarvtk_runtime.py"):
            shutil.copyfile(ROOT / "integrations" / name, destination / name)
    shutil.copyfile(ROOT / "docs" / "INSTALLATION.md", bundle / "INSTALLATION.md")
    archive = output / "QAROS-VTK-plugins.zip"
    # Explicit allowlist; never package caches, SDK files or local credentials.
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as stream:
        for host, names in {
            "slicer": ["QarosVTK.py", "qarvtk_slicer.py", "qarvtk_bridge.py", "qarvtk_runtime.py"],
            "paraview": ["QarosVTKPlugin.py", "qarvtk_paraview.py", "qarvtk_bridge.py", "qarvtk_runtime.py"],
        }.items():
            for name in names:
                path = bundle / host / name
                stream.write(path, path.relative_to(output))
        stream.write(bundle / "INSTALLATION.md", "QAROS-VTK-plugins/INSTALLATION.md")
    print("Plugin folders: " + str(bundle))
    print("Archive: " + str(archive))
    return bundle


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "package")
    package(parser.parse_args().output)
