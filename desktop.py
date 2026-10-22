"""Native desktop entry point for Windows and macOS."""
import argparse
import ctypes
import os
import sys
from pathlib import Path


def user_data_dir():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Afirma Image Studio"
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Afirma Image Studio"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Afirma Image Studio.")
    parser.add_argument("--simulation-only", action="store_true", help="Bloqueia a geração paga nesta sessão.")
    parser.add_argument("--self-test", type=Path, metavar="PASTA", help="Executa diagnóstico isolado, sem chave ou API, e fecha a janela.")
    args = parser.parse_args(argv)
    if args.self_test:
        # A diagnostic process never inherits API credentials from its caller.
        for name in tuple(os.environ):
            if name.startswith(('OPENAI_', 'AZURE_OPENAI_')):
                os.environ.pop(name, None)
    if os.name != "nt" and sys.platform != "darwin":
        raise RuntimeError("A janela nativa requer Windows ou macOS.")
    data_dir = args.self_test.resolve() if args.self_test else user_data_dir()
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        # Logs and caches belong to the Windows user, even if the package is on
        # a read-only drive or opened by a shortcut with another working folder.
        os.chdir(data_dir)
        from src.studio_session import StudioSession
        from src.desktop_app import run_desktop
        if args.self_test:
            if sys.platform == "darwin":
                from src.macos_diagnostics import prepare_diagnostics
            else:
                from src.desktop_diagnostics import prepare_diagnostics
            session, ready = prepare_diagnostics(data_dir)
        else:
            session = StudioSession(data_dir / "settings.json", allow_api=not args.simulation_only)
            ready = None
        run_desktop(session, data_dir=data_dir, on_ready=ready)
        if args.self_test:
            import json
            result = json.loads((data_dir / "diagnostics.json").read_text("utf-8"))
            return 0 if result["passed"] else 1
        return 0
    except Exception as exc:
        # GUI builds have no stderr. Keep startup failures actionable without
        # exposing any SDK response, credential or environment value.
        try:
            (data_dir / "startup-error.txt").write_text(
                f"Falha ao iniciar Afirma Image Studio ({type(exc).__name__}).\n"
                "Confira as dependências e a pasta de dados do aplicativo.\n", "utf-8")
        except OSError:
            pass  # A read-only data folder must still produce the GUI error.
        if not args.self_test and sys.platform == "darwin":
            import subprocess
            subprocess.run(['/usr/bin/osascript', '-e',
                'display alert "Afirma Image Studio" message "Não foi possível iniciar. Consulte startup-error.txt em Library/Application Support/Afirma Image Studio."'],
                check=False, timeout=60)
        elif not args.self_test:
            ctypes.windll.user32.MessageBoxW(None,
                "Não foi possível iniciar o Afirma Image Studio.\n\n"
                "Extraia o ZIP completo e confira se o Microsoft Edge WebView2 Runtime está instalado.\n"
                "Consulte o LEIA-ME.txt do pacote e startup-error.txt na pasta de dados do aplicativo.",
                "Afirma Image Studio", 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
