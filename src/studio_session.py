"""Local Studio state and worker; no browser storage or credentials in settings."""
from copy import deepcopy
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import time

from PIL import Image
from src.excel_reader import load_config, load_queue
from src.execution_state import queue_lock, PersistenceError, digest
from src.image_settings import ImageSettings
from src.job_values import cell_text, parse_quantity


def validate_photos(paths):
    resolved = tuple(Path(p).resolve(strict=True) for p in paths)
    if not 1 <= len(resolved) <= 16:
        raise ValueError("Selecione entre 1 e 16 fotos de referência.")
    for path in resolved:
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError(f"Referência não suportada: {path.name}")
        if path.stat().st_size >= 50 * 1024 * 1024:
            raise ValueError(f"Referência deve ter menos de 50 MB: {path.name}")
        try:
            with Image.open(path) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError()
                image.verify()
        except Exception:
            raise ValueError(f"Conteúdo de imagem inválido: {path.name}") from None
    return resolved


def validate_folders(folders, default):
    result = {}
    for entry in folders:
        alias = entry.get("alias", "").strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", alias):
            raise ValueError("Alias inválido: comece com letra; use até 40 letras, números, _ ou -.")
        if alias.casefold() in {a.casefold() for a in result}:
            raise ValueError(f"Alias duplicado: {alias}")
        raw = entry.get("path", "").strip()
        if not raw or not Path(raw).is_dir():
            raise ValueError(f"Pasta inexistente: {alias} ({raw})")
        result[alias] = Path(raw).resolve()
    if default and default not in result:
        raise ValueError("Pasta padrão não cadastrada.")
    return result


def save_folder_sheet(queue, folders, default):
    """Explicit user operation only; atomic write preserves other workbook sheets."""
    from openpyxl import load_workbook
    from src.excel_reader import _save_workbook_atomic
    roots = validate_folders(folders, default)
    with queue_lock(queue):
        book = load_workbook(queue)
        try:
            if "Pastas_Referencias" in book:
                del book["Pastas_Referencias"]
            sheet = book.create_sheet("Pastas_Referencias")
            sheet.append(["Alias", "Caminho"])
            for alias, path in roots.items():
                sheet.append([alias, str(path)])
            if default:
                config = book["Configuracao"]
                for row in config.iter_rows(min_row=2):
                    if row[0].value == "Pasta_Referencias":
                        row[1].value = str(roots[default])
                        break
                else:
                    config.append(["Pasta_Referencias", str(roots[default])])
            _save_workbook_atomic(book, queue)
        finally:
            book.close()


class RunControl:
    def __init__(self, callback, simulation_delay=0):
        self.condition = threading.Condition()
        self.paused = False
        self.stopped = False
        self.callback = callback
        self.delay = simulation_delay

    def event(self, kind, **values):
        self.callback(kind, values)

    def checkpoint(self):
        with self.condition:
            while self.paused and not self.stopped:
                self.condition.wait(0.25)
            if self.stopped:
                return False
        if self.delay:
            time.sleep(self.delay)
            with self.condition:
                while self.paused and not self.stopped:
                    self.condition.wait(0.25)
                return not self.stopped
        return True

    def command(self, action):
        with self.condition:
            if action == "pause":
                self.paused = True
            elif action == "resume":
                self.paused = False
            elif action == "stop":
                self.stopped = True
            else:
                raise ValueError("Comando de execução inválido.")
            self.condition.notify_all()


class StudioSession:
    def __init__(self, settings_path, *, allow_api=False, env=None):
        self.lock = threading.RLock()
        self.settings_path = Path(settings_path)
        self.allow_api = allow_api
        self.env = env  # Defaults are extracted locally; secrets never enter state/preferences.
        self.credential_file = Path(__file__).resolve().parents[1] / ".env"
        self.queue = None
        self.queue_summary = None
        self.photos = []
        self.folders = []
        self.default_folder = ""
        self.mode = "spreadsheet"
        self.preferences = dict(image=asdict(ImageSettings()), output_dir="", timeout=120, retries=2,
                                max_jobs=1, max_images=1, safe_mode=True)
        if env is None:
            from dotenv import dotenv_values
            defaults = {**dotenv_values(self.credential_file), **os.environ}
        else:
            defaults = env
        self.preferences.update(image=asdict(ImageSettings.from_env(defaults)),
                                timeout=float(defaults.get("OPENAI_TIMEOUT_SECONDS", 120)),
                                retries=int(defaults.get("OPENAI_RETRIES", 2)),
                                max_jobs=int(defaults.get("MAX_JOBS_PER_RUN", 1)),
                                max_images=int(defaults.get("MAX_IMAGES_PER_RUN", 1)))
        from main import flag
        self.preferences["safe_mode"] = flag(defaults.get("FIRST_RUN_SAFE_MODE", "SIM"))
        self.checked_preferences(self.preferences)
        if self.settings_path.exists():
            self._load_preferences(json.loads(self.settings_path.read_text("utf-8")))
        self.active = False
        self.control = None
        self.worker = None
        self.result = {}
        self.items = []
        self.total = 0
        self.status = "Pronto"
        self.error = ""

    def idle(self):
        if self.active:
            raise ValueError("Execução ativa: pause/retome ou encerre antes de alterar a campanha.")

    @staticmethod
    def checked_preferences(values):
        allowed = {"image", "output_dir", "timeout", "retries", "max_jobs", "max_images", "safe_mode"}
        if set(values) - allowed:
            raise ValueError("Configuração desconhecida; credenciais não são aceitas pelo Studio.")
        ImageSettings(**values["image"])
        if not isinstance(values.get("output_dir"), str):
            raise ValueError("Pasta de saída inválida.")
        if values["output_dir"] and not Path(values["output_dir"]).is_absolute():
            raise ValueError("Escolha uma pasta de saída absoluta.")
        if type(values["timeout"]) not in (int, float) or not math.isfinite(values["timeout"]) or values["timeout"] <= 0:
            raise ValueError("Tempo limite deve ser positivo.")
        for key in ("max_jobs", "max_images"):
            if type(values[key]) is not int or values[key] < 1:
                raise ValueError("Limites devem ser inteiros positivos.")
        if type(values["retries"]) is not int or not 0 <= values["retries"] <= 5:
            raise ValueError("Novas tentativas: escolha de 0 a 5.")
        if type(values["safe_mode"]) is not bool:
            raise ValueError("Modo seguro inválido.")
        return deepcopy(values)

    def _load_preferences(self, data):
        if set(data) - {"version", "preferences"} or data.get("version") != 1:
            raise ValueError("Arquivo de preferências inválido ou versão desconhecida.")
        self.preferences = self.checked_preferences(data["preferences"])

    def set_preferences(self, values, persist=False):
        with self.lock:
            self.idle()
            values = self.checked_preferences(values)
            if persist:
                self.settings_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.settings_path.parent,
                                                     delete=False) as handle:
                        temporary = Path(handle.name)
                        json.dump({"version": 1, "preferences": values}, handle, indent=2)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary, self.settings_path)
                finally:
                    if temporary:
                        temporary.unlink(missing_ok=True)
            self.preferences = values
            if self.queue:
                self._refresh_queue_summary()

    def _refresh_queue_summary(self, config=None):
        if not self.queue:
            self.queue_summary = None
            return
        if config is None:
            config = load_config(self.queue, reference_mode="direct")
        frame = load_queue(self.queue, reference_mode=self.mode)
        prompts = frame.apply(
            lambda row: bool(cell_text(row.get("Prompt_Padrao")) or
                             cell_text(row.get("Prompt_Variacao"))), axis=1)
        pending = frame["Status"].map(lambda value: isinstance(value, str) and value.strip().upper() == "PENDENTE")
        pending_prompts = prompts & pending
        image_count = 0
        invalid_quantities = 0
        execution_items = 0
        execution_images = 0
        item_limit = min(self.preferences["max_jobs"], config["limit"])
        for _, row in frame.loc[pending_prompts].iterrows():
            try:
                quantity = parse_quantity(row.get("Quantidade"))
                image_count += quantity
            except ValueError:
                invalid_quantities += 1
                continue
            if execution_items >= item_limit or execution_images + quantity > self.preferences["max_images"]:
                continue
            execution_items += 1
            execution_images += quantity
        completed = frame["Status"].map(
            lambda value: isinstance(value, str) and value.strip().upper() in {"CONCLUIDO", "SIMULADO"})
        review = frame["Status"].map(
            lambda value: isinstance(value, str) and value.strip().upper() in {"REVISAO", "ERRO"})
        self.queue_summary = {
            "items_with_prompt": int(prompts.sum()),
            "pending_items": int(pending_prompts.sum()),
            "estimated_images": image_count,
            "execution_items": execution_items,
            "execution_images": execution_images,
            "item_limit": item_limit,
            "image_limit": self.preferences["max_images"],
            "invalid_quantities": invalid_quantities,
            "completed_items": int((prompts & completed).sum()),
            "review_items": int((prompts & review).sum()),
        }

    def choose_queue(self, path):
        with self.lock:
            self.idle()
            path = Path(path).resolve(strict=True)
            try:
                config = load_config(path)
            except ValueError:
                if self.mode != "direct":
                    raise
                config = load_config(path, reference_mode="direct")
            self.queue = path
            self.folders = [{"alias": a, "path": str(p)} for a, p in config["reference_dirs"].items()]
            self.default_folder = next((a for a, p in config["reference_dirs"].items()
                                        if p == config["reference_dir"]), "")
            self.legacy_root = config["reference_dir"]
            self._refresh_queue_summary(config)
            self.items, self.result, self.error = [], {}, ""

    def set_mode(self, mode):
        with self.lock:
            self.idle()
            if mode not in {"spreadsheet", "direct"}:
                raise ValueError("Modo inválido.")
            self.mode = mode
            if self.queue:
                self._refresh_queue_summary()
    def add_photos(self, paths):
        with self.lock:
            self.idle()
            additions = validate_photos(paths)
            proposed = list(self.photos)
            for p in additions:
                if p not in proposed:  # deduplicate exact resolved paths, never basenames.
                    proposed.append(p)
            validate_photos(proposed)
            self.photos = proposed

    def remove_photo(self, index):
        with self.lock:
            self.idle()
            if type(index) is not int or not 0 <= index < len(self.photos):
                raise ValueError("Foto não encontrada na seleção.")
            self.photos.pop(index)

    def set_folders(self, folders, default):
        with self.lock:
            self.idle()
            validate_folders(folders, default)
            if self.default_folder and not default and self.folders:
                raise ValueError("Escolha outra pasta padrão antes de remover a pasta padrão atual. Arquivos sem alias não serão redirecionados automaticamente.")
            self.folders, self.default_folder = deepcopy(folders), default

    def folder_usage(self, alias):
        with self.lock:
            self.idle()
            if not self.queue:
                return []
            df = load_queue(self.queue, reference_mode="direct")
            used = []
            for _, row in df.iterrows():
                for ref in cell_text(row["Arquivo_Referencia"]).split(";"):
                    if (("::" in ref and ref.split("::", 1)[0].strip() == alias) or
                            alias == self.default_folder and ref.strip() and "::" not in ref):
                        used.append(str(row["ID"]))
                        break
            return used

    def save_folders(self):
        with self.lock:
            self.idle()
            if not self.queue:
                raise ValueError("Selecione uma planilha antes de salvar as pastas.")
            save_folder_sheet(self.queue, self.folders, self.default_folder)

    def snapshot(self):
        if not self.queue:
            raise ValueError("Selecione a planilha da campanha.")
        prefs = self.checked_preferences(self.preferences)
        # Session folder edits override the sheet registry without writing it.
        config = load_config(self.queue, reference_mode="direct")
        config.update(studio=True, reference_mode=self.mode,
                      image_settings=ImageSettings(**prefs["image"]))
        if self.mode == "spreadsheet":
            roots = validate_folders(self.folders, self.default_folder)
            config["reference_dirs"] = roots
            config["reference_dir"] = roots[self.default_folder] if self.default_folder else self.legacy_root
            if config["reference_dir"] is None:
                raise ValueError("Escolha uma pasta padrão para usar referências pela planilha.")
        else:
            config["direct_references"] = validate_photos(self.photos)
        if prefs["output_dir"]:
            config["result_dir"] = Path(prefs["output_dir"]).resolve()
        return config, prefs

    def validate_campaign(self):
        from main import make_job
        from src.image_generator import OpenAIImageGenerator
        from src.job_values import canonical_id
        config, _ = self.snapshot()
        df = load_queue(self.queue, reference_mode=self.mode)
        ids = df["ID"].map(canonical_id)
        if ids.eq("").any() or ids.duplicated().any():
            raise ValueError("Cada linha deve ter ID preenchido, único e estável.")
        from src.execution_state import Journal
        records = Journal(self.queue).records
        errors, plan, outputs = [], [], set()
        for _, row in df.iterrows():
            # Recovery can safely requeue prepared jobs before any API call.
            # Include their references in the same preflight snapshot as pending jobs.
            record = records.get(canonical_id(row["ID"]), {})
            if cell_text(row["Status"]).upper() != "PENDENTE" and record.get("phase") != "prepared":
                continue
            try:
                job = make_job(row, config, True)
                OpenAIImageGenerator.validate(job)
                if any(p in outputs for p in job.saidas):
                    raise ValueError("Nome de saída repetido em outra linha da campanha.")
                outputs.update(job.saidas)
                if any(p.exists() or p.is_symlink() for p in job.saidas):
                    # Recovery can prove completed outputs; only block unregistered conflicts here.
                    from src.execution_state import Journal
                    if str(job.id) not in Journal(self.queue).records:
                        raise ValueError("Saída já existe sem histórico confirmado; escolha um nome novo.")
                plan.append({"id": str(job.id), "prompt": job.prompt,
                             "references": [str(p) for p in job.referencias],
                             "outputs": [str(p) for p in job.saidas], "quantity": job.quantidade})
            except (ValueError, OSError) as exc:
                errors.append(f"ID {row['ID']}: {exc}")
        if errors:
            raise ValueError("\n".join(errors))
        return {"jobs": plan, "settings": asdict(config["image_settings"]),
                "experimental": config["image_settings"].experimental}

    def _event(self, kind, values):
        with self.lock:
            if kind == "plan":
                self.total = values["total"]
            elif kind == "item":
                self.items.append(values)

    def start(self, real=False):
        with self.lock:
            self.idle()
            if real and not self.allow_api:
                raise ValueError("API real bloqueada nesta sessão. A implementação deve ser validada antes da autorização.")
            plan = self.validate_campaign()
            config, prefs = self.snapshot()
            config["dry_run"] = not real
            config["expected_reference_hashes"] = {
                path: digest(Path(path)) for job in plan["jobs"] for path in job["references"]}
            queue = self.queue
            self.active = True
            self.error, self.result, self.items, self.total = "", {}, [], 0
            self.status = "Gerando" if real else "Simulando"
            self.control = RunControl(self._event, simulation_delay=0 if real else 0.25)
            control = self.control
            environment = dict(self.env) if self.env is not None else None

            def work():
                from main import main
                try:
                    if environment is None and real:
                        from dotenv import dotenv_values
                        effective_env = {**dotenv_values(self.credential_file), **os.environ}
                    else:
                        effective_env = dict(environment or {})
                    effective_env.update(IMAGE_PROVIDER="openai" if real else "simulation", DRY_RUN="NAO" if real else "SIM",
                                         FIRST_RUN_SAFE_MODE="SIM" if prefs["safe_mode"] else "NAO",
                                         MAX_JOBS_PER_RUN=str(prefs["max_jobs"]), MAX_IMAGES_PER_RUN=str(prefs["max_images"]),
                                         OPENAI_TIMEOUT_SECONDS=str(prefs["timeout"]), OPENAI_RETRIES=str(prefs["retries"]))
                    result = main(queue, env=effective_env, overrides=config, control=control)
                    with self.lock:
                        self.result = result
                        self.status = "Interrompido" if control.stopped else "Finalizado"
                except Exception as exc:
                    with self.lock:
                        self.error = str(exc) if isinstance(exc, (ValueError, OSError, PersistenceError)) else "Falha local; confira o log sem apagar o histórico."
                        self.status = "Erro"
                finally:
                    with self.lock:
                        self.active = False

            self.worker = threading.Thread(target=work, name="afirma-campaign", daemon=False)
            self.worker.start()
            return plan

    def command(self, action):
        with self.lock:
            if not self.active or not self.control:
                raise ValueError("Nenhuma execução ativa.")
            self.control.command(action)
            self.status = {"pause": "Pausa solicitada — após o item atual", "resume": "Executando",
                           "stop": "Encerrando após o item atual"}[action]

    def state(self):
        with self.lock:
            return dict(queue=str(self.queue) if self.queue else "", queue_summary=deepcopy(self.queue_summary), mode=self.mode,
                        photos=[{"name": p.name, "path": str(p)} for p in self.photos],
                        folders=deepcopy(self.folders), default_folder=self.default_folder,
                        preferences=deepcopy(self.preferences), active=self.active,
                        paused=bool(self.control and self.control.paused), status=self.status,
                        total=self.total, items=deepcopy(self.items), result=dict(self.result), error=self.error,
                        allow_api=self.allow_api)
