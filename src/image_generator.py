from abc import ABC, abstractmethod
import base64
from contextlib import ExitStack

from src.generation_job import GenerationJob


class ImageGenerator(ABC):
    @abstractmethod
    def generate(self, job: GenerationJob) -> tuple:
        """Generate files at job.saidas and return their paths."""


class MockImageGenerator(ImageGenerator):
    def __init__(self, fail=False):
        self.fail = fail

    def generate(self, job: GenerationJob) -> tuple:
        if self.fail:
            raise RuntimeError(f"Falha simulada para ID={job.id}")
        created = []
        try:
            for path in job.saidas:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as file:
                    file.write(f"Mock image for job {job.id}\n".encode("utf-8"))
                created.append(path)
        except Exception:
            for path in created:
                path.unlink()
            raise
        return tuple(created)


class OpenAIImageGenerator(ImageGenerator):
    def __init__(self, api_key=None, model="gpt-image-2.5-sunburst", quality="auto",
                 timeout=120, retries=2, client=None, retryable_errors=None):
        if not api_key and client is None:
            raise ValueError("OPENAI_API_KEY não configurada.")
        if quality not in {"auto", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("OPENAI_IMAGE_QUALITY inválida.")
        if timeout <= 0 or retries < 0:
            raise ValueError("Timeout ou retries inválidos.")
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, timeout=timeout, max_retries=0)
        if retryable_errors is None:
            from openai import APIConnectionError, APITimeoutError, RateLimitError, InternalServerError
            retryable_errors = (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)
        self.client = client
        self.model = model
        self.quality = quality
        self.retries = retries
        self.retryable_errors = retryable_errors

    def generate(self, job: GenerationJob) -> tuple:
        if len(job.saidas) != job.quantidade or not 1 <= job.quantidade <= 10:
            raise ValueError("Quantidade para OpenAI deve estar entre 1 e 10.")
        if len(job.referencias) > 16:
            raise ValueError("OpenAI aceita no máximo 16 referências por job.")
        for path in job.saidas:
            if path.exists():
                raise FileExistsError(f"Arquivo de saída já existe: {path}")
        prompt = job.prompt
        if job.prompt_negativo:
            prompt += f"\n\nEvitar: {job.prompt_negativo}"
        for attempt in range(self.retries + 1):
            try:
                with ExitStack() as stack:
                    images = [stack.enter_context(path.open("rb")) for path in job.referencias]
                    response = self.client.images.edit(
                        model=self.model, image=images, prompt=prompt,
                        n=job.quantidade, quality=self.quality, output_format="png",
                    )
                break
            except self.retryable_errors as exc:
                if attempt == self.retries:
                    raise RuntimeError(f"Falha temporária da OpenAI após {attempt + 1} tentativas ({type(exc).__name__}).") from None
            except Exception as exc:
                raise RuntimeError(f"Falha da OpenAI ({type(exc).__name__}).") from None

        data = getattr(response, "data", None)
        if not data or len(data) != job.quantidade:
            raise RuntimeError("OpenAI retornou quantidade inesperada de imagens.")
        try:
            decoded = [base64.b64decode(item.b64_json, validate=True) for item in data]
            if any(not image for image in decoded):
                raise ValueError("empty image")
        except (ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError("OpenAI retornou imagem inválida.") from None
        created = []
        try:
            for path, image in zip(job.saidas, decoded):
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as file:
                    file.write(image)
                created.append(path)
        except Exception:
            for path in created:
                path.unlink()
            raise
        return tuple(created)
