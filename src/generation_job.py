from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class GenerationJob:
    id: object
    prompt: str
    referencias: tuple[Path, ...]
    nome_saida: str
    status: str
    tentativas: int
    quantidade: int = 1
    saidas: tuple[Path, ...] = field(default_factory=tuple)
    tema: str = ""
    produto: str = ""
    cliente: str = ""
    prompt_negativo: str = ""
    observacao_usuario: str = ""
