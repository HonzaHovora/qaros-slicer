#!/usr/bin/env python3
"""Package the installed dev.2927 Live plugin and its Windows x64 bridge."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SDK_SHA = 'a32cecd4137dd3b28e0d5e0c1642a066cbea976f81b90f1f31fbac4d0fba8d4a'


def package(dll, output, compiler):
    native = Path(dll).read_bytes()
    offset = struct.unpack_from('<I', native, 0x3c)[0]
    if (native[:2] != b'MZ' or native[offset:offset + 4] != b'PE\0\0' or
            struct.unpack_from('<H', native, offset + 4)[0] != 0x8664):
        raise ValueError('Expected a Windows x64 DLL')
    if ('"header_sha256":"' + SDK_SHA + '"').encode() not in native:
        raise ValueError('DLL does not contain the exact dev.2927 SDK fingerprint')
    payload = {'Release/qarvtk-host.dll': native,
               'plugins/slicer/QarosLive.py': (ROOT / 'integrations/slicer/QarosLive.py').read_bytes(),
               'plugins/slicer/QarosVTKLib/__init__.py': b'"""Private support package, not a Slicer module."""\n'}
    for name in ('runtime', 'view', 'gpu', 'panels', 'diagnostics'):
        path = 'qarvtk_host_' + name + '.py'
        payload['plugins/slicer/QarosVTKLib/' + path] = (ROOT / 'integrations/slicer' / path).read_bytes()
    payload['plugins/slicer/QarosVTKLib/qarvtk_runtime.py'] = (ROOT / 'integrations/qarvtk_runtime.py').read_bytes()
    info = dict(sdk_version='0.9.0-dev.2927+f291e404', sdk_header_sha256=SDK_SHA,
                host_abi=5, build='installed-hub-update-r3-panels-off',
                native_build='installed-hub-update-r2', compiler=compiler,
                slice_previews_default=False,
                runtime_included=False, live_gpu_tested=False,
                files={name: hashlib.sha256(data).hexdigest() for name, data in payload.items()})
    payload['HOST_UPDATE_INFO.json'] = (json.dumps(info, indent=2) + '\n').encode()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / 'qarvtk-live-dev2927.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            entry = zipfile.ZipInfo(name, (2026, 10, 19, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip():
            raise ValueError('ZIP CRC verification failed')
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    archive_path.with_suffix('.zip.sha256').write_text(digest + '  ' + archive_path.name + '\n')
    print(str(archive_path) + ': ' + digest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'downloads')
    parser.add_argument('--compiler', required=True)
    args = parser.parse_args()
    package(args.dll, args.output, args.compiler)
