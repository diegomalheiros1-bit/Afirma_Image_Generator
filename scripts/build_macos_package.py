"""Build an Apple Silicon app and DMG on macOS; require frozen UI smoke test."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.app_info import APP_VERSION
from studio import WEB_ASSETS

NAME = 'Afirma Image Studio'


def assert_public_bundle(app):
    forbidden = {'.env', 'settings.json', '.studio-settings.json', 'processamento.log', 'startup-error.txt'}
    for path in app.rglob('*'):
        if path.is_file() and (path.name.lower() in forbidden or path.name.startswith('.env.')
                or path.suffix.lower() in {'.xlsx', '.xls', '.dpapi'}
                or path.name.endswith(('.state.json', '.studio-run.json'))):
            raise RuntimeError(f'Arquivo privado no pacote: {path.name}')


def main():
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise SystemExit('Execute em macOS Apple Silicon com Python ARM64; não compila no Windows.')
    release = ROOT / 'output' / 'releases-macos' / datetime.now().strftime('%Y%m%d-%H%M%S')
    release.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed',
               '--name', NAME, '--target-arch', 'arm64',
               '--osx-bundle-identifier', 'com.afirma.imagestudio',
               '--hidden-import', 'webview.platforms.cocoa',
               '--hidden-import', 'keyring.backends.macOS',
               '--distpath', str(release / 'dist'), '--workpath', str(release / 'build'),
               '--specpath', str(release / 'spec')]
    for module in ['webview.platforms.winforms', 'webview.platforms.edgechromium',
                   'webview.platforms.qt', 'webview.platforms.gtk', 'webview.platforms.android',
                   'webview.platforms.cef', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
                   'tkinter', 'src.native_picker', 'src.desktop_diagnostics']:
        command.extend(['--exclude-module', module])
    assets = {'studio.html', *(filename for filename, _ in WEB_ASSETS.values())}
    for filename in sorted(assets):
        command.extend(['--add-data', f'{ROOT / "web" / filename}:web'])
    command.append(str(ROOT / 'desktop.py'))
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('OPENAI_', 'AZURE_OPENAI_'))}
    env['MACOSX_DEPLOYMENT_TARGET'] = '15.0'
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    app = release / 'dist' / f'{NAME}.app'
    executable = app / 'Contents' / 'MacOS' / NAME
    plist = app / 'Contents' / 'Info.plist'
    with plist.open('rb') as stream:
        info = plistlib.load(stream)
    info.update(CFBundleShortVersionString=APP_VERSION, CFBundleVersion=APP_VERSION,
                LSMinimumSystemVersion='15.0')
    with plist.open('wb') as stream:
        plistlib.dump(info, stream)
    # Updating the bundle metadata requires renewing its ad-hoc signature.
    # No Developer ID identity or Apple account is used.
    subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', str(app)], check=True)
    subprocess.run(['/usr/bin/lipo', '-verify_arch', 'arm64', str(executable)], check=True)
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    assert_public_bundle(app)
    verification = release / 'verification'
    subprocess.run([str(executable), '--self-test', str(verification)],
                   cwd=release, env=env, check=True, timeout=180)
    diagnostics = json.loads((verification / 'diagnostics.json').read_text('utf-8'))
    if not diagnostics.get('passed'):
        raise RuntimeError('Diagnóstico nativo falhou; DMG não criado.')
    stage = release / 'installer'
    stage.mkdir()
    subprocess.run(['/usr/bin/ditto', str(app), str(stage / app.name)], check=True)
    (stage / 'Applications').symlink_to('/Applications')
    shutil.copyfile(ROOT / 'docs' / 'INSTALAR_NO_MAC.txt', stage / 'LEIA-ME.txt')
    dmg = release / 'Afirma-Image-Studio-Mac-Apple-Silicon.dmg'
    subprocess.run(['/usr/bin/hdiutil', 'create', '-volname', NAME, '-srcfolder', str(stage),
                    '-ov', '-format', 'UDZO', str(dmg)], check=True)
    subprocess.run(['/usr/bin/hdiutil', 'verify', str(dmg)], check=True)
    digest = hashlib.sha256(dmg.read_bytes()).hexdigest()
    (release / 'SHA256.txt').write_text(f'{digest}  {dmg.name}\n', encoding='ascii')
    (release / 'build-info.json').write_text(json.dumps({
        'version': APP_VERSION, 'architecture': 'arm64', 'macos': platform.mac_ver()[0],
        'python': sys.version, 'signature': 'ad-hoc; not notarized',
        'native_diagnostics_passed': True, 'sha256': digest,
        'checks': diagnostics['checks'],
    }, indent=2), encoding='utf-8')
    print(f'DMG={dmg}\nSHA256={digest}')


if __name__ == '__main__':
    main()
