"""Build and verify the native Windows client, excluding private campaign data."""
from datetime import datetime
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.app_info import APP_VERSION
OUTPUT = ROOT / "output" / "releases"
NAME = "Afirma-Image-Studio"


def package_files(destination):
    forbidden = {".env", "settings.json", ".studio-settings.json", "processamento.log", "startup-error.txt"}
    files = sorted(path for path in destination.rglob('*') if path.is_file())
    for path in files:
        if (path.name.lower() in forbidden or path.name.lower().startswith('.env.')
                or path.suffix.lower() in {'.xlsx', '.xls', '.dpapi'}
                or path.name.lower().endswith('.state.json')):
            raise RuntimeError(f"Arquivo privado encontrado no pacote: {path.name}")
    return files


def main():
    if os.name != 'nt':
        raise SystemExit('A build do executável Windows deve rodar no Windows.')
    release = OUTPUT / datetime.now().strftime('%Y%m%d-%H%M%S')
    destination = release / NAME
    release.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed',
               '--name', NAME, '--add-data', f"{ROOT / 'web' / 'studio.html'};web",
               '--hidden-import', 'webview.platforms.winforms',
               '--hidden-import', 'webview.platforms.edgechromium',
               '--distpath', str(release), '--workpath', str(release / 'build'),
               '--specpath', str(release / 'spec')]
    # Only the Windows WebView2 backend is supported by this entry point.
    for module in ['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'qtpy', 'cefpython3', 'gi',
                   'webview.platforms.qt', 'webview.platforms.gtk', 'webview.platforms.cocoa',
                   'webview.platforms.android', 'webview.platforms.cef', 'tkinter', 'src.native_picker']:
        command.extend(['--exclude-module', module])
    command.append(str(ROOT / 'desktop.py'))
    subprocess.run(command, cwd=ROOT, check=True)
    executable = destination / f'{NAME}.exe'
    if not executable.is_file():
        raise RuntimeError('PyInstaller terminou sem criar o executável esperado.')
    # PE subsystem 2 is Windows GUI. The delivered app must not open a console.
    import struct
    contents = executable.read_bytes()
    pe_offset = struct.unpack_from('<I', contents, 0x3c)[0]
    if struct.unpack_from('<H', contents, pe_offset + 24 + 68)[0] != 2:
        raise RuntimeError('O executável não foi compilado como aplicativo de janela.')

    (destination / 'LEIA-ME.txt').write_text(
        'AFIRMA IMAGE STUDIO - APLICATIVO WINDOWS\n\n'
        '1. Extraia o ZIP inteiro. Preserve a pasta _internal junto do executável.\n'
        f'2. Abra {NAME}.exe. Não precisa instalar Python nem abrir um navegador.\n'
        '3. A janela permite minimizar, maximizar, restaurar e redimensionar.\n'
        '   Em janelas menores, os painéis se organizam em uma coluna.\n'
        '4. Selecione SUA planilha, referências e pasta de saída.\n'
        '5. Em Configurações > Opções avançadas, informe SUA chave da API.\n'
        '   Use apenas nesta sessão ou salve protegida para seu usuário do Windows.\n'
        '6. Confira e simule a campanha antes de confirmar Gerar imagens - API paga.\n'
        '   A geração real exige confirmação e pode gerar cobrança na sua conta.\n'
        '7. Ao fechar durante uma campanha, é possível cancelar ou aguardar a imagem\n'
        '   atual terminar e salvar o resultado antes de encerrar.\n\n'
        'Em Configurações > Sobre, consulte a versão, informações da API e links oficiais.\n\n'
        'REQUISITOS\nWindows 10/11 de 64 bits e Microsoft Edge WebView2 Runtime.\n'
        'O WebView2 é o componente da janela e não abre o navegador Edge.\n'
        'Se necessário, instale o Runtime oficial da Microsoft:\n'
        'https://developer.microsoft.com/microsoft-edge/webview2/\n'
        'Conexão com a internet é necessária para verificar a chave e gerar imagens.\n\n'
        'DADOS\nPreferências, chave protegida, logs e cache ficam em:\n'
        r'%LOCALAPPDATA%\Afirma Image Studio' '\n'
        'O campo da chave permanece vazio ao reabrir para não expor a credencial.\n'
        'Histórico e planilhas permanecem nas pastas escolhidas para a campanha.\n'
        'O pacote não inclui chave, planilha ou imagens reais.\n'
        'O processamento local usa somente 127.0.0.1; não altera o Firewall.\n\n'
        'SUPORTE\nEm caso de falha ao abrir, confira a extração completa e o WebView2.\n'
        'Consulte startup-error.txt e logs/processamento.log na pasta de dados.\n'
        'Este pacote é portátil, sem instalador e sem assinatura digital.\n'
        'Não há processamento com o aplicativo fechado ou computador desligado.\n'
        'Para bloquear o botão pago, inicie com o argumento --simulation-only.\n',
        encoding='utf-8')
    files = package_files(destination)
    # Exercise the actual frozen .exe, WebView2 renderer and UI in isolated data.
    verification = release / 'verification'
    subprocess.run([str(executable), '--self-test', str(verification)],
                   cwd=release, check=True, timeout=120)
    diagnostics = json.loads((verification / 'diagnostics.json').read_text('utf-8'))
    if not diagnostics.get('passed'):
        raise RuntimeError('O diagnóstico nativo falhou; ZIP não gerado.')

    archive = release / f'{NAME}-Windows.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for path in files:
            package.write(path, path.relative_to(release))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (release / 'SHA256.txt').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    source_files = [ROOT / 'desktop.py', ROOT / 'studio.py', ROOT / 'web/studio.html',
                    *sorted((ROOT / 'src').glob('*.py')), ROOT / 'requirements-desktop.txt',
                    ROOT / 'requirements-build-windows.txt', Path(__file__).resolve()]
    info = {
        'built_at_local': datetime.now().isoformat(timespec='seconds'),
        'python': sys.version.split()[0],
        'app_version': APP_VERSION,
        'packages': {name: version(name) for name in ('pywebview', 'pythonnet', 'pyinstaller', 'openai', 'pandas', 'Pillow')},
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_tree_dirty': bool(subprocess.check_output(
            ['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=ROOT, text=True).strip()),
        'source_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files},
        'archive_sha256': digest,
        'native_diagnostics_passed': True,
        'native_layouts_checked': len(diagnostics['layouts']),
        'pe_subsystem': 'Windows GUI',
    }
    (release / 'build-info.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    print(f'PACOTE={destination}\nZIP={archive}\nSHA256={digest}', flush=True)


if __name__ == '__main__':
    main()
