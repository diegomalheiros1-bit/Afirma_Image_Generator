"""Validated immutable API settings, shared by CLI, Studio and recovery."""
from dataclasses import asdict, dataclass
import re

MODELS = ("gpt-image-2.5-sunburst", "gpt-image-2.5-flare")
FORMATS = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}


@dataclass(frozen=True)
class ImageSettings:
    model: str = MODELS[0]
    quality: str = "auto"
    output_format: str = "png"
    background: str = "auto"
    size: str = "auto"
    compression: int | None = None

    def __post_init__(self):
        if self.model not in MODELS:
            raise ValueError("Modelo não suportado pelo Studio.")
        if self.quality not in {"auto", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("Qualidade de geração inválida.")
        if self.output_format not in FORMATS:
            raise ValueError("Formato deve ser PNG, JPEG ou WebP.")
        if self.background not in {"auto", "opaque", "transparent"}:
            raise ValueError("Fundo inválido.")
        if self.background == "transparent" and self.output_format == "jpeg":
            raise ValueError("JPEG não suporta transparência. Escolha PNG/WebP ou outro fundo.")
        if self.compression is not None:
            if self.output_format == "png":
                raise ValueError("Compressão configurável não é compatível com PNG.")
            if type(self.compression) is not int or not 0 <= self.compression <= 100:
                raise ValueError("Compressão deve ser inteira entre 0 e 100%.")
        if self.size != "auto":
            match = re.fullmatch(r"([1-9][0-9]*)x([1-9][0-9]*)", self.size)
            if not match:
                raise ValueError("Resolução deve ser auto ou largura x altura em pixels.")
            width, height = map(int, match.groups())
            if width % 16 or height % 16:
                raise ValueError("Largura e altura devem ser múltiplos de 16.")
            if max(width, height) > 3840:
                raise ValueError("Nenhuma dimensão pode ultrapassar 3840 pixels.")
            if max(width, height) > 3 * min(width, height):
                raise ValueError("Proporção máxima permitida: 3:1 ou 1:3.")
            if not 655360 <= width * height <= 8294400:
                raise ValueError("Área deve estar entre 655.360 e 8.294.400 pixels.")

    @property
    def experimental(self):
        return self.size != "auto" and self.size_area > 2560 * 1440

    @property
    def size_area(self):
        width, height = map(int, self.size.split("x"))
        return width * height

    def api_params(self):
        params = asdict(self)
        compression = params.pop("compression")
        if compression is not None:
            # Official guide defines output_compression as compression %, not quality.
            params["output_compression"] = compression
        return params

    @classmethod
    def from_env(cls, env):
        return cls(model=env.get("OPENAI_IMAGE_MODEL", MODELS[0]),
                   quality=env.get("OPENAI_IMAGE_QUALITY", "auto"),
                   output_format=env.get("OPENAI_IMAGE_FORMAT", "png"),
                   background=env.get("OPENAI_IMAGE_BACKGROUND", "auto"),
                   size=env.get("OPENAI_IMAGE_SIZE", "auto"),
                   compression=(int(env["OPENAI_IMAGE_COMPRESSION"])
                                if env.get("OPENAI_IMAGE_COMPRESSION") not in (None, "") else None))
