"""Native Windows shell over the same authenticated, loopback-only Studio."""
from pathlib import Path
import threading


MIN_SIZE = (520, 500)


def on_ui_thread(window, callback):
    """Owned Windows dialogs must run on the form's STA thread."""
    native = getattr(window, "native", None)
    if native is not None and native.InvokeRequired:
        from System import Action
        result = {}
        native.Invoke(Action(lambda: result.update(value=callback())))
        return result.get("value")
    return callback()


def initial_size(screens):
    if not screens:
        return (1200, 800)
    screen = screens[0]
    return (max(MIN_SIZE[0], min(1360, screen.width - 80)),
            max(MIN_SIZE[1], min(900, screen.height - 90)))


class DesktopApp:
    def __init__(self, session, webview):
        self.session = session
        self.webview = webview
        self.window = None
        self.close_pending = False

    def pick_files(self, kind):
        options = dict(directory=str(Path.home()))
        if kind == "queue":
            options.update(dialog_type=self.webview.FileDialog.OPEN, file_types=("Planilhas Excel (*.xlsx)",))
        elif kind == "photos":
            options.update(dialog_type=self.webview.FileDialog.OPEN, allow_multiple=True,
                           file_types=("Imagens (*.png;*.jpg;*.jpeg;*.webp)",))
        elif kind == "folder":
            options.update(dialog_type=self.webview.FileDialog.FOLDER)
        else:
            raise ValueError("Seleção inválida.")
        return list(on_ui_thread(self.window, lambda: self.window.create_file_dialog(**options)) or ())

    def on_closing(self):
        with self.session.lock:
            active = self.session.active
        if not active:
            return True
        if self.close_pending:
            return False
        if not self.window.create_confirmation_dialog("Encerrar campanha?",
                "Há uma campanha em andamento. Deseja encerrá-la após a imagem atual?\n\n"
                "A janela continuará aberta até salvar o resultado. Nenhum novo item será iniciado."):
            return False
        with self.session.lock:
            if not self.session.active:
                return True
            self.close_pending = True
            self.session.command("stop")
            worker = self.session.worker

        def finish():
            if worker:
                worker.join()
            self.window.destroy()

        threading.Thread(target=finish, name="afirma-close-after-item", daemon=True).start()
        return False


def run_desktop(session, *, data_dir, on_ready=None, webview_module=None):
    if webview_module is None:
        import webview as webview_module
    from studio import make_server
    webview = webview_module
    webview.settings.update(ALLOW_FILE_URLS=False, ALLOW_DOWNLOADS=False,
                            IGNORE_SSL_ERRORS=False, REMOTE_DEBUGGING_PORT=None,
                            OPEN_EXTERNAL_LINKS_IN_BROWSER=True)
    app = DesktopApp(session, webview)
    session.app_mode = "desktop"
    server = make_server(session, picker=lambda kind: app.pick_files(kind))
    url = f"http://127.0.0.1:{server.server_port}/"
    thread = threading.Thread(target=server.serve_forever, name="afirma-local-server", daemon=True)
    thread.start()
    try:
        width, height = initial_size(webview.screens)
        app.window = webview.create_window("Afirma Image Studio", url=url,
            width=width, height=height, min_size=MIN_SIZE, resizable=True,
            maximized=False, frameless=False, text_select=True, zoomable=True,
            background_color="#f3f2f8")
        app.window.events.closing += app.on_closing

        engine = {"supported": False}

        def require_webview2(renderer):
            engine["supported"] = renderer == "edgechromium"
            return engine["supported"]

        app.window.events.initialized += require_webview2
        if on_ready:
            app.window.events.loaded += lambda: on_ready(app)
        webview.start(gui="edgechromium", debug=False, private_mode=True,
                      storage_path=str(Path(data_dir) / "webview-cache"),
                      localization={"global.ok": "OK", "global.cancel": "Cancelar"})
        if not engine["supported"]:
            raise RuntimeError("O Microsoft Edge WebView2 Runtime é necessário.")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
        if session.active:
            session.command("stop")
        if session.worker:
            session.worker.join()
