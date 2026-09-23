from abc import ABC, abstractmethod
import base64
from contextlib import ExitStack
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import io
import math
import os
import random
import time

from PIL import Image
from src.generation_job import GenerationJob


class GenerationError(RuntimeError):
    def __init__(self, message, *, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


class ImageGenerator(ABC):
    is_real = False

    @abstractmethod
    def generate(self, job: GenerationJob) -> tuple:
        """Return generated paths. Real providers must persist before_attempt callbacks."""


class MockImageGenerator(ImageGenerator):
    def __init__(self, fail=False):
        self.fail = fail

    def generate(self, job):
        if self.fail:
            raise GenerationError("Falha simulada.")
        for path in job.saidas:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                handle.write(b"MOCK - not an image\n")
        return job.saidas


class OpenAIImageGenerator(ImageGenerator):
    is_real = True

    def __init__(self, api_key=None, model="gpt-image-2.5-sunburst", quality="auto",
                 timeout=120, retries=2, client=None, sleep=time.sleep):
        # Deliberately restrict this MVP to the model/parameters verified in the docs.
        if model != "gpt-image-2.5-sunburst":
            raise ValueError("Modelo não validado neste MVP; use gpt-image-2.5-sunburst.")
        if quality not in {"auto", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("OPENAI_IMAGE_QUALITY inválida.")
        if not math.isfinite(timeout) or timeout <= 0 or not 0 <= retries <= 5:
            raise ValueError("Timeout deve ser positivo; OPENAI_RETRIES deve estar entre 0 e 5.")
        if client is None:
            if not api_key or not api_key.strip():
                raise ValueError("OPENAI_API_KEY não configurada.")
            from openai import OpenAI
            client = OpenAI(api_key=api_key, timeout=timeout, max_retries=0)
        self.client, self.model, self.quality = client, model, quality
        self.retries, self.sleep = retries, sleep
        self.api_attempts = 0
        self.before_attempt = lambda number: None

    @staticmethod
    def validate(job):
        if len(job.saidas) != job.quantidade or not 1 <= job.quantidade <= 10:
            raise ValueError("Quantidade para OpenAI deve estar entre 1 e 10.")
        if not 1 <= len(job.referencias) <= 16:
            raise ValueError("OpenAI exige entre 1 e 16 referências.")
        if not job.prompt or len(job.prompt) > 32000:
            raise ValueError("Prompt deve conter entre 1 e 32000 caracteres.")
        for path in job.referencias:
            if path.stat().st_size >= 50 * 1024 * 1024:
                raise ValueError(f"Referência excede 50 MB: {path.name}")
            try:
                with Image.open(path) as image:
                    if image.format not in {"PNG", "JPEG", "WEBP"}:
                        raise ValueError()
                    image.verify()
            except Exception:
                raise ValueError(f"Imagem de referência inválida: {path.name}") from None

    @staticmethod
    def retry_delay(exc, attempt):
        headers = getattr(getattr(exc, "response", None), "headers", {})
        hint = headers.get("retry-after")
        seconds = 0
        if hint:
            try:
                seconds = float(hint)
            except ValueError:
                try:
                    seconds = (parsedate_to_datetime(hint) - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    seconds = 0
        if not math.isfinite(seconds):
            seconds = 0
        return max(2 ** attempt, seconds) + random.uniform(0, 0.25)

    def generate(self, job):
        self.api_attempts = 0
        self.validate(job)
        for path in job.saidas:
            if path.exists() or path.is_symlink():
                raise FileExistsError(f"Arquivo de saída já existe: {path.name}")
        for attempt in range(self.retries + 1):
            with ExitStack() as stack:
                images = [stack.enter_context(path.open("rb")) for path in job.referencias]
                # Outside the API exception handler: a journal failure MUST stop the queue.
                self.before_attempt(attempt + 1)
                self.api_attempts += 1
                try:
                    response = self.client.images.edit(model=self.model, image=images, prompt=job.prompt,
                                                       n=job.quantidade, quality=self.quality, output_format="png")
                    break
                except Exception as exc:
                    status = getattr(exc, "status_code", None)
                    code = getattr(exc, "code", None)
                    transient = ((status == 429 and code in {"rate_limit_exceeded", "slow_down"}) or
                                 (status == 503 and code == "server_is_overloaded"))
                    if transient and attempt < self.retries:
                        delay = self.retry_delay(exc, attempt)
                        if delay <= 60:
                            self.sleep(delay)
                            continue
                    uncertain = status is None or status >= 500 and not transient
                    # Do not log exception strings, bodies, headers or tracebacks from the SDK.
                    detail = ({401: "autenticação", 403: "permissão", 400: "parâmetros",
                               429: "limite/quota; confira faturamento e limites",
                               503: "indisponibilidade"}.get(status, "falha de comunicação"))
                    if code in {"insufficient_quota", "credit_balance_exhausted", "organization_usage_limit_exceeded",
                                "organization_spend_limit_exceeded", "project_spend_limit_exceeded",
                                "slow_down", "rate_limit_exceeded", "server_is_overloaded"}:
                        detail += f" ({code})"
                    raise GenerationError(f"OpenAI: {detail}; chamadas API: {self.api_attempts}.",
                                          uncertain=uncertain) from None
        try:
            if not response.data or len(response.data) != job.quantidade:
                raise ValueError()
            decoded = [base64.b64decode(item.b64_json, validate=True) for item in response.data]
            for payload in decoded:
                with Image.open(io.BytesIO(payload)) as image:
                    if image.format != "PNG":
                        raise ValueError()
                    image.verify()
        except Exception:
            raise GenerationError("Resposta de imagem inválida; revisar antes de reenviar.", uncertain=True) from None
        # Preserve partial files for recovery. Exclusive creation prevents overwrites.
        for path, payload in zip(job.saidas, decoded):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        return job.saidas
