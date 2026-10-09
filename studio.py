"""Afirma Studio: standard-library loopback web UI over the existing pipeline."""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import ipaddress
from http.cookies import SimpleCookie
from urllib.parse import urlsplit, parse_qs
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import webbrowser

from PIL import Image, ImageOps
from src.native_picker import select as select_native_file
from src.studio_session import StudioSession

ROOT = Path(__file__).resolve().parent


def native_select(kind):
    command = ([sys.executable, "--native-picker", kind] if getattr(sys, "frozen", False)
               else [sys.executable, str(ROOT / "src" / "native_picker.py"), kind])
    process = subprocess.run(command,
                             capture_output=True, text=True, check=True)
    return json.loads(process.stdout)


def make_server(session, port=0, picker=native_select, *, host="127.0.0.1"):
    address = ipaddress.ip_address(host)
    if address.version != 4 or not (address.is_loopback or any(address in net for net in (
            ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16")))):
        raise ValueError("Use o IPv4 da rede local; endereços públicos e 0.0.0.0 não são aceitos.")
    lan = not address.is_loopback
    if lan and session.allow_api:
        raise ValueError("Acesso pela rede local mantém a API paga bloqueada.")
    token = secrets.token_urlsafe(32)
    access_key = secrets.token_urlsafe(32) if lan else None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log request bodies, credentials or auth tokens.

        def respond(self, status, payload, content_type="application/json; charset=utf-8"):
            if not isinstance(payload, bytes):
                payload = json.dumps(payload, ensure_ascii=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def authorize(self, require_token=True):
            expected = f"{host}:{self.server.server_port}"
            if self.headers.get("Host") != expected:
                raise PermissionError("Host não autorizado.")
            if self.headers.get("Origin") not in (None, "http://" + expected):
                raise PermissionError("Origem não autorizada.")
            if lan:
                cookies = SimpleCookie()
                try:
                    cookies.load(self.headers.get("Cookie", ""))
                except Exception:
                    raise PermissionError("Use o link de acesso exclusivo mostrado no computador.") from None
                cookie = cookies.get("afirma_access")
                if not cookie or not secrets.compare_digest(cookie.value, access_key):
                    raise PermissionError("Use o link de acesso exclusivo mostrado no computador.")
            if require_token and not secrets.compare_digest(self.headers.get("X-Afirma-Token", ""), token):
                raise PermissionError("Sessão não autorizada.")

        def do_GET(self):
            try:
                request = urlsplit(self.path)
                if lan and request.path == "/" and request.query:
                    expected = f"{host}:{self.server.server_port}"
                    supplied = parse_qs(request.query).get("access", [""])[0]
                    if (self.headers.get("Host") != expected or
                            self.headers.get("Origin") not in (None, "http://" + expected) or
                            not secrets.compare_digest(supplied, access_key)):
                        raise PermissionError("Link de acesso inválido.")
                    self.send_response(303)
                    self.send_header("Location", "/")
                    self.send_header("Set-Cookie", f"afirma_access={access_key}; HttpOnly; SameSite=Strict; Path=/")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.authorize(require_token=self.path != "/")
                if self.path == "/":
                    html = (ROOT / "web" / "studio.html").read_text("utf-8")
                    self.respond(200, html.replace("__SESSION_TOKEN__", token).encode(), "text/html; charset=utf-8")
                elif self.path == "/api/state":
                    self.respond(200, session.state())
                else:
                    self.respond(404, {"error": "Recurso inexistente."})
            except PermissionError as exc:
                self.respond(403, {"error": str(exc)})

        def do_POST(self):
            try:
                self.authorize()
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= 1000000:
                    raise ValueError("Pedido inválido ou grande demais.")
                data = json.loads(self.rfile.read(length))
                result = {}
                with session.lock:
                    if self.path == "/api/select":
                        session.idle()
                        kind = data["kind"]
                        if kind not in {"queue", "photos", "folder"}:
                            raise ValueError("Seleção inválida.")
                        paths = picker(kind)
                        if paths and kind == "queue":
                            session.choose_queue(paths[0])
                        elif paths and kind == "photos":
                            session.add_photos(paths)
                        result = {"paths": paths}
                    elif self.path == "/api/mode":
                        session.set_mode(data["mode"])
                    elif self.path == "/api/photos/remove":
                        session.remove_photo(data["index"])
                    elif self.path == "/api/thumbnail":
                        index = data["index"]
                        if type(index) is not int or not 0 <= index < len(session.photos):
                            raise ValueError("Foto não selecionada.")
                        with Image.open(session.photos[index]) as original:
                            thumb = ImageOps.exif_transpose(original)
                            thumb.thumbnail((160, 120))
                            stream = io.BytesIO()
                            thumb.convert("RGBA").save(stream, "PNG")
                        result = {"url": "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()}
                    elif self.path == "/api/folders":
                        session.set_folders(data["folders"], data["default"])
                    elif self.path == "/api/folders/usage":
                        result = {"ids": session.folder_usage(data["alias"])}
                    elif self.path == "/api/folders/save":
                        session.save_folders()
                    elif self.path == "/api/preferences":
                        session.set_preferences(data["preferences"], persist=data.get("persist", False))
                    elif self.path == "/api/credential":
                        if lan:
                            raise PermissionError("Configure a chave somente no computador local.")
                        session.set_api_key(data["key"], persist=data.get("persist", False))
                    elif self.path == "/api/credential/clear":
                        if lan:
                            raise PermissionError("Remova a chave somente no computador local.")
                        session.clear_api_key()
                    elif self.path == "/api/validate":
                        session.idle()
                        result = session.validate_campaign()
                    elif self.path == "/api/start":
                        result = session.start(real=data.get("real", False) is True)
                    elif self.path == "/api/control":
                        session.command(data["action"])
                    else:
                        self.respond(404, {"error": "Ação inexistente."})
                        return
                self.respond(200, result)
            except PermissionError as exc:
                self.respond(403, {"error": str(exc)})
            except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as exc:
                self.respond(400, {"error": str(exc) if isinstance(exc, (ValueError, OSError)) else "Não foi possível concluir a operação local."})
            except Exception:
                self.respond(500, {"error": "Falha local. Preserve a planilha e o histórico; consulte o terminal."})

    server = ThreadingHTTPServer((host, port), Handler)
    server.session_token = token
    server.access_key = access_key
    return server


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--native-picker":
        print(json.dumps(select_native_file(sys.argv[2]), ensure_ascii=True))
        raise SystemExit(0)
    default_settings = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Afirma Image Studio" / "settings.json"
                        if getattr(sys, "frozen", False) else ROOT / ".studio-settings.json")
    parser = argparse.ArgumentParser(description="Abre o Afirma Image Studio local.")
    parser.add_argument("--host", default="127.0.0.1", help="IPv4 local para acesso Wi-Fi opcional e autenticado.")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--enable-api", action="store_true", help="Habilita o botão real; somente após autorização explícita.")
    parser.add_argument("--settings", type=Path, default=default_settings)
    args = parser.parse_args()
    session = StudioSession(args.settings, allow_api=args.enable_api)
    server = make_server(session, args.port, host=args.host)
    url = f"http://{args.host}:{server.server_port}/"
    if server.access_key:
        url += "?access=" + server.access_key
    print(f"Afirma Studio: {url}\nAPI real: {'habilitada' if args.enable_api else 'BLOQUEADA'}", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if session.active:
            session.command("stop")
    finally:
        server.server_close()
        if session.worker:
            session.worker.join()
