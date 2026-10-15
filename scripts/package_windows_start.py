#!/usr/bin/env python3
"""Package pinned, already-tested CI outputs without rebuilding or adding an SDK."""
import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = 'https://github.com/HonzaHovora/QAROS_VTK'


def verified_zip(path, expected_sha):
    data = Path(path).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha:
        raise ValueError(f'Artifact checksum mismatch: {path}: {actual}')
    return zipfile.ZipFile(io.BytesIO(data))


def package(native_archive, plugins_archive, output):
    config = json.loads((ROOT / 'releases/windows-start.json').read_text())
    filename = config['filename']
    if Path(filename).name != filename or not filename.endswith('.zip'):
        raise ValueError('Release filename must be a ZIP basename')
    date = datetime.date.fromisoformat(config['date'])
    payload = {}
    native_exes = {'qarvtk-preview.exe', 'qarvtk-sender.exe',
                   'qarvtk-core-test.exe', 'qarvtk-gpu-test.exe', 'qarvtk-volume-test.exe'}
    with verified_zip(native_archive, config['native']['sha256']) as archive:
        for name in archive.namelist():
            path = PurePosixPath(name)
            if name == 'qarvtk-sdk.json' or (
                    path.parent == PurePosixPath('Release') and
                    (path.suffix == '.dll' or path.name in native_exes)):
                payload[name] = archive.read(name)
    for name in native_exes:
        if 'Release/' + name not in payload:
            raise ValueError(f'Missing native executable: {name}')
    if config.get('host_bridge') and 'Release/qarvtk-host.dll' not in payload:
        raise ValueError('Live host release is missing qarvtk-host.dll')
    sdk = json.loads(payload['qarvtk-sdk.json'])
    if sdk['header_sha256'] != config['sdk_header_sha256']:
        raise ValueError('SDK fingerprint differs from the selected release')
    modern_api = config.get('modern_api', 1)
    if modern_api not in (0, 1):
        raise ValueError('Unknown SDK connection API')
    if sdk.get('modern_api') != modern_api or sdk.get('plugin_protocol') != 2:
        raise ValueError('Sender API mode or plugin protocol differs from the selected release')

    with verified_zip(plugins_archive, config['plugins']['sha256']) as outer:
        with zipfile.ZipFile(io.BytesIO(outer.read('QAROS-VTK-plugins.zip'))) as archive:
            for name in archive.namelist():
                path = PurePosixPath(name)
                if '..' in path.parts or path.is_absolute():
                    raise ValueError('Invalid plugin archive path')
                if (len(path.parts) >= 3 and path.parts[0] == 'QAROS-VTK-plugins'
                        and path.parts[1] in {'slicer', 'paraview'} and path.suffix == '.py'):
                    payload['plugins/' + '/'.join(path.parts[1:])] = archive.read(name)
    for name in ('plugins/slicer/QarosVTK.py',
                 'plugins/slicer/QarosVTKLib/qarvtk_runtime.py',
                 'plugins/slicer/QarosVTKLib/qarvtk_scene.py',
                 'plugins/paraview/QarosVTKPlugin.py'):
        if name not in payload:
            raise ValueError(f'Missing plugin file: {name}')
    if config.get('host_bridge'):
        for name in ('plugins/slicer/QarosLive.py', 'plugins/slicer/QarosVTKLib/qarvtk_host_view.py',
                     'plugins/slicer/QarosVTKLib/qarvtk_host_runtime.py'):
            if name not in payload:
                raise ValueError(f'Missing live host plugin: {name}')
    for target, source in {
        '01-Preview.cmd': 'scripts/windows/01-Preview.cmd',
        'ZACNI_ZDE.txt': config.get('quickstart', 'docs/WINDOWS_QUICKSTART.txt'),
        'sample/cube-200mm.vtp': 'samples/cube-200mm.vtp',
        'KHRONOS-LICENSE.txt': 'third_party/KHRONOS-LICENSE.txt',
    }.items():
        payload[target] = (ROOT / source).read_bytes()
    provenance = {
        'prepared_on': config['date'],
        'native_run': f"{REPO}/actions/runs/{config['native']['run_id']}",
        'native_commit': config['native']['commit'],
        'native_artifact_sha256': config['native']['sha256'],
        'plugins_run': f"{REPO}/actions/runs/{config['plugins']['run_id']}",
        'plugins_commit': config['plugins']['commit'],
        'plugins_artifact_sha256': config['plugins']['sha256'],
        'sdk_build_metadata': sdk,
        'included_runtime': False,
        'gpu_hub_headset_tested': False,
        'notes': 'Original CI DLLs/EXEs and packaged plugins are unchanged. '
                 'Added Czech quickstart, preview launcher and a synthetic 200 mm cube.'
    }
    payload['BUILD_INFO.json'] = (json.dumps(provenance, indent=2) + '\n').encode()
    payload['SHA256SUMS.txt'] = ''.join(
        hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
        for name, data in sorted(payload.items())).encode()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    target = output / filename
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(payload.items()):
            entry = zipfile.ZipInfo(name, (date.year, date.month, date.day, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValueError('Release ZIP failed CRC verification')
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / (filename + '.sha256')).write_text(digest + '  ' + filename + '\n')
    connection = 'QAROS Hub' if modern_api else 'QAROS session / Visualizer'
    sdk_requirement = (
        'Použij odpovídající moderní SDK s Hub onboarding API.' if modern_api else
        'Tato varianta používá session API a Legacy viewer; Hub pairing code se nevyplňuje.')
    notes = f'''Hotový balíček pro první test **Slicer → VTK/OpenGL → {connection}** na Windows x64.

Balíček **{filename}** lze stáhnout v Assets. Pro již přihlášený GitHub Desktop
použij `Fetch origin`, `Pull origin` a `START-PREVIEW.cmd` v checkoutu, jakmile je
balíček uložen v `downloads/`. Podrobný postup je v `ZACNI_ZDE.txt`.

Obsahuje odesílač, lokální náhled, potřebné VTK DLL, pluginy Slicer/ParaView a testovací kostku.
QAROS SDK, Hub ani viewer nejsou součástí balíčku. {sdk_requirement}
SHA256 hlavičky SDK musí být `{config['sdk_header_sha256']}`. Hlavičku a runtime
v instalovaném SDK neměň; plugin ověří shodu před spuštěním.

Nativní Windows sestavení a core testy prošly; pluginy byly ověřeny na Linuxu.
**Novou verzi je ještě potřeba ověřit ve Visualizeru na cílovém PC.**
Slicer podporuje osvětlené modely, viditelné segmenty a jeden CT/MR objem
s nastavením z Volume Rendering, automatickým vycentrováním a přizpůsobením velikosti.
Objem používá Composite režim bez ROI ořezu; kombinace s modely vyžaduje neprůhledné
povrchy. ParaView zatím přenáší povrchy. FPS diagnostika z r8 je zachována.

- Native build: [{config['native']['commit'][:8]}]({provenance['native_run']})
- Plugins: [{config['plugins']['commit'][:8]}]({provenance['plugins_run']})
- [Instalační postup]({REPO}/blob/main/{config.get('quickstart', 'docs/WINDOWS_QUICKSTART.txt')})
'''
    (output / 'release-notes.md').write_text(notes, encoding='utf-8')
    print(target)
    print('SHA256:', digest)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-archive', type=Path, required=True)
    parser.add_argument('--plugins-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/windows-start')
    args = parser.parse_args()
    package(args.native_archive, args.plugins_archive, args.output)
