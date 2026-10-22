"""Build an immutable generation job shared by CLI, preflight and recovery."""
from dataclasses import replace
from pathlib import Path

from src.execution_state import digest
from src.file_manager import openai_output_paths, output_paths, validate_reference_paths
from src.generation_job import GenerationJob
from src.image_settings import ImageSettings
from src.job_values import canonical_id, cell_text, parse_quantity
from src.output_naming import allocated_paths
from src.prompt_builder import build_prompt


def make_job(row, config, real):
    text = lambda name: cell_text(row.get(name))
    quantity = parse_quantity(row.get("Quantidade"))
    name = text("Nome_Saida")
    settings = config.get("image_settings", ImageSettings())
    mode = config.get("reference_mode", "spreadsheet")
    paths = (openai_output_paths(config["result_dir"], name, quantity, check_exists=False,
                                output_format=settings.output_format) if real or config.get("studio") else
             output_paths(config["result_dir"], name, quantity))
    paths = allocated_paths(paths, config.get('output_allocations', {}).get(canonical_id(row['ID'])))
    attempts = 0 if not cell_text(row["Tentativas"]) else int(row["Tentativas"])
    job = GenerationJob(
        id=canonical_id(row["ID"]), prompt=build_prompt(text("Prompt_Padrao"), text("Prompt_Variacao"),
            tema=text("Tema"), produto=text("Produto"), observacao_usuario=text("Observacao_Usuario"),
            prompt_negativo=text("Prompt_Negativo")),
        referencias=(tuple(Path(p).resolve() for p in config.get("direct_references", ())) if mode == "direct" else
                     validate_reference_paths(config["reference_dir"], text("Arquivo_Referencia"), config.get("reference_dirs"))),
        nome_saida=name, status=text("Status"), tentativas=attempts, quantidade=quantity, saidas=paths,
        tema=text("Tema"), produto=text("Produto"), cliente=text("Cliente"),
        prompt_negativo=text("Prompt_Negativo"), observacao_usuario=text("Observacao_Usuario"),
        settings=settings, reference_mode=mode)
    hashes = tuple(digest(p) for p in job.referencias)
    expected = config.get("expected_reference_hashes")
    if expected is not None and any(expected.get(str(p)) != h for p, h in zip(job.referencias, hashes)):
        raise ValueError("Foto de referência alterada, movida ou substituída durante a execução; confira a campanha.")
    return replace(job, reference_hashes=hashes)
