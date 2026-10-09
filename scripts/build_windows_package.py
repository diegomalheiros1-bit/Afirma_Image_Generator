"""Build an isolated Windows client package without workbooks or credentials."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "releases"
NAME = "Afirma-Image-Studio"


def main():
    if os.name != "nt":
        raise SystemExit("A build do executável Windows deve rodar no Windows.")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    release = OUTPUT / stamp
    destination = release / NAME
    if release.exists():
        raise SystemExit(f"Destino já existe; preserve-o: {release}")
    release.mkdir(parents=True)
    command = [sys.executable, "-m", "PyInstaller", "--onedir", "--console",
               "--name", NAME, "--add-data", f"{ROOT / 'web' / 'studio.html'};web",
               "--distpath", str(release), "--workpath", str(release / "build"),
               "--specpath", str(release / "spec"), str(ROOT / "studio.py")]
    subprocess.run(command, cwd=ROOT, check=True)
    executable = destination / f"{NAME}.exe"
    if not executable.is_file():
        raise RuntimeError("PyInstaller terminou sem criar o executável esperado.")

    (destination / "Iniciar Afirma Studio.cmd").write_text(
        '@echo off\r\ntitle Afirma Image Studio\r\ncd /d "%~dp0"\r\n'
        f'"%~dp0{NAME}.exe" --enable-api\r\n'
        'echo.\r\necho O Studio foi encerrado.\r\npause\r\n', encoding="utf-8")
    (destination / "LEIA-ME.txt").write_text(
        "AFIRMA IMAGE STUDIO - TESTE NO WINDOWS\n\n"
        "1. Extraia o ZIP inteiro em uma pasta do computador.\n"
        "2. Abra 'Iniciar Afirma Studio.cmd' e mantenha a janela preta aberta.\n"
        "3. O Studio abrirá no navegador local. Se não abrir, use o endereço mostrado na janela.\n"
        "4. Selecione a SUA planilha, suas referências e a pasta de saída.\n"
        "5. Em Configurações > Opções avançadas, informe a SUA chave da API.\n"
        "   Você pode usá-la só nesta sessão ou salvá-la protegida para seu usuário do Windows.\n"
        "6. Confira e simule a campanha antes de confirmar 'Gerar imagens - API paga'.\n"
        "   Chamadas reais podem gerar cobrança na conta associada à sua chave.\n"
        "7. Preserve planilha, imagens e arquivos de histórico juntos.\n\n"
        "O programa roda apenas neste computador (127.0.0.1). O GitHub/pacote não\n"
        "contém chave, planilha, referências ou imagens do piloto original.\n"
        "Fechar a janela encerra o Studio; mantenha-a aberta até o lote terminar.\n"
        "O .exe sozinho abre com a API paga bloqueada; use o iniciador para o teste real.\n"
        "Este pacote não é um instalador e não possui assinatura digital.\n",
        encoding="utf-8")
    forbidden = {".env", "settings.json", ".studio-settings.json"}
    if any(path.name.lower() in forbidden or path.suffix.lower() == ".xlsx"
           for path in destination.rglob("*")):
        raise RuntimeError("Arquivo sensível encontrado no pacote; publicação interrompida.")
    archive = release / f"{NAME}-Windows.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as package:
        for path in destination.rglob("*"):
            if path.is_file():
                package.write(path, path.relative_to(release))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (release / "SHA256.txt").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    (release / "build-info.json").write_text(json.dumps({
        "built_at_local": datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                                  cwd=ROOT, text=True).strip(),
        "source_tree_dirty": bool(subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=ROOT, text=True).strip()),
        "archive_sha256": digest,
    }, indent=2), encoding="utf-8")
    print(f"PACOTE={destination}\nZIP={archive}\nSHA256={digest}", flush=True)


if __name__ == "__main__":
    main()
