#!/usr/bin/env python3
"""Launch with a build-matched SDK and an unmodified bin/ directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--sdk", required=True, type=Path)
    args, remaining = parser.parse_known_args()
    exe, sdk = args.exe.resolve(), args.sdk.resolve()
    header = sdk / "include" / "qar_streaming.h"
    if not exe.is_file() or not header.is_file():
        parser.error("Executable and SDK include/qar_streaming.h must exist")
    # Reuse the executable's dependency path but do not inject SDK DLLs into it.
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        env.pop(key, None)
    info = json.loads(subprocess.check_output([str(exe), "--sdk-info"], text=True, env=env))
    actual = hashlib.sha256(header.read_bytes()).hexdigest()
    if actual != info["header_sha256"]:
        parser.error("SDK header differs from the one used to build this sender. Reconfigure and rebuild with this complete SDK package.")
    print("SDK header verified; API: " + ("Hub onboarding" if info["modern_api"] else "legacy session invite"), flush=True)
    return subprocess.call([str(exe), "--sdk", str(sdk), *remaining], env=env)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print("ERROR:", error, file=sys.stderr)
        sys.exit(1)
