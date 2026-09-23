from pathlib import Path
import os
import pandas as pd
from dotenv import load_dotenv

from src.excel_reader import load_config, load_queue, save_queue
from src.prompt_builder import build_prompt
from src.file_manager import openai_output_paths, output_paths, validate_reference_paths
from src.generation_job import GenerationJob
from src.logger import get_logger

QUEUE_PATH = Path("input/fila.xlsx")
logger = get_logger()


def is_pending(status) -> bool:
    return isinstance(status, str) and status.strip().upper() == "PENDENTE"


def cell_text(value) -> str:
    return "" if pd.isna(value) else str(value).strip()


def parse_quantity(value) -> int:
    if pd.isna(value) or str(value).strip() == "":
        return 1
    try:
        quantity = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Quantidade deve ser um inteiro positivo.") from exc
    if quantity <= 0 or str(value).strip() not in (str(quantity), f"{quantity}.0"):
        raise ValueError("Quantidade deve ser um inteiro positivo.")
    return quantity


def optional_text(row, name):
    return cell_text(row[name]) if name in row else ""


def positive_limit(name, default):
    value = int(os.getenv(name, default))
    if value <= 0:
        raise ValueError(f"{name} deve ser positivo.")
    return value


def main(queue_path=QUEUE_PATH, reference_dir=None, generator=None):
    load_dotenv(queue_path.parent.parent / ".env", override=False)
    config = load_config(queue_path)
    dry_run_setting = os.getenv("DRY_RUN")
    if dry_run_setting is not None:
        if dry_run_setting.strip().upper() not in {"SIM", "NAO", "NÃO"}:
            raise ValueError("DRY_RUN deve ser SIM ou NAO.")
        config["dry_run"] = dry_run_setting.strip().upper() == "SIM"
    if reference_dir is not None:
        config["reference_dir"] = reference_dir
    df = load_queue(queue_path)
    provider = os.getenv("IMAGE_PROVIDER", "simulation").strip().lower()
    if provider not in {"simulation", "mock", "openai"}:
        raise ValueError("IMAGE_PROVIDER deve ser mock ou openai.")
    pending = [index for index, row in df.iterrows() if is_pending(row["Status"])]
    max_jobs = positive_limit("MAX_JOBS_PER_RUN", 10)
    max_images = positive_limit("MAX_IMAGES_PER_RUN", 20)
    selected = []
    planned_images = 0
    for index in pending[:min(config["limit"], max_jobs)]:
        try:
            quantity = parse_quantity(df.at[index, "Quantidade"] if "Quantidade" in df else None)
        except ValueError:
            quantity = 1  # The selected row will be marked ERRO during processing.
        if planned_images + quantity > max_images:
            break
        selected.append(index)
        planned_images += quantity
    if provider == "openai" and not config["dry_run"] and generator is None:
        if max_jobs > 1 or max_images > 1 or config["limit"] > 1:
            raise ValueError("Primeiro teste OpenAI exige limites de jobs e imagens <= 1.")
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise ValueError("OPENAI_API_KEY não configurada.")
        for index in selected:
            row = df.loc[index]
            references = validate_reference_paths(config["reference_dir"], cell_text(row["Arquivo_Referencia"]))
            quantity = parse_quantity(row.get("Quantidade"))
            if quantity != 1:
                raise ValueError("Primeiro teste OpenAI exige Quantidade=1.")
            openai_output_paths(queue_path.parent.parent / "output" / "imagens",
                                cell_text(row["Nome_Saida"]), quantity)
    if provider == "openai":
        print(f"Provider: OpenAI\nJobs encontrados: {len(pending)}\n"
              f"Imagens previstas: {planned_images}\n"
              f"Limite configurado: {max_jobs} jobs / {max_images} imagens")
        if not config["dry_run"] and generator is None:
            from src.image_generator import OpenAIImageGenerator
            generator = OpenAIImageGenerator(
                api_key=os.getenv("OPENAI_API_KEY"),
                model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst"),
                quality=os.getenv("OPENAI_IMAGE_QUALITY", "auto"),
                timeout=positive_limit("OPENAI_TIMEOUT_SECONDS", 120),
                retries=int(os.getenv("OPENAI_RETRIES", "2")),
            )
    elif provider == "mock" and not config["dry_run"] and generator is None:
        from src.image_generator import MockImageGenerator
        generator = MockImageGenerator()
    ignored = len(df) - len(selected)
    success = errors = 0
    logger.info("Início da execução | DRY RUN=%s", config["dry_run"])
    logger.info("Total=%s | Pendentes=%s | A processar=%s", len(df), len(pending), len(selected))

    for idx in selected:
        row = df.loc[idx]
        item_id = row["ID"] if not pd.isna(row["ID"]) else idx + 1
        logger.info("Iniciado ID=%s", item_id)
        try:
            if not config["dry_run"]:
                df.at[idx, "Status"] = "PROCESSANDO"
                attempts = row["Tentativas"]
                df.at[idx, "Tentativas"] = (0 if pd.isna(attempts) else int(attempts)) + 1
                save_queue(df, queue_path)
            references = validate_reference_paths(
                config["reference_dir"], cell_text(row["Arquivo_Referencia"])
            )
            quantity = parse_quantity(row.get("Quantidade"))
            if provider == "openai":
                paths = openai_output_paths(queue_path.parent.parent / "output" / "imagens",
                                            cell_text(row["Nome_Saida"]), quantity)
            else:
                paths = output_paths(config["result_dir"], cell_text(row["Nome_Saida"]), quantity)
            prompt = build_prompt(cell_text(row["Prompt_Padrao"]), cell_text(row["Prompt_Variacao"]))
            job = GenerationJob(
                id=item_id, prompt=prompt, referencias=references,
                nome_saida=cell_text(row["Nome_Saida"]), status="PROCESSANDO",
                tentativas=(0 if pd.isna(df.at[idx, "Tentativas"]) else int(df.at[idx, "Tentativas"])),
                quantidade=quantity,
                saidas=paths, tema=optional_text(row, "Tema"),
                produto=optional_text(row, "Produto"), cliente=optional_text(row, "Cliente"),
                prompt_negativo=optional_text(row, "Prompt_Negativo"),
                observacao_usuario=optional_text(row, "Observacao_Usuario"),
            )
            if config["dry_run"]:
                print(f"DRY RUN | ID: {item_id}\nPrompt final: {job.prompt}\n"
                      f"Arquivo de referência: {'; '.join(map(str, job.referencias))}\n"
                      f"Nome do arquivo de saída: {'; '.join(path.name for path in job.saidas)}\n")
            else:
                if generator is not None:
                    generator.generate(job)
                df.at[idx, "Status"] = "CONCLUIDO"
                df.at[idx, "Observacao"] = (
                    "Imagens geradas." if generator is not None else
                    "Simulação concluída com sucesso; imagem não gerada."
                )
            success += 1
            logger.info("Sucesso ID=%s", item_id)
        except Exception as exc:
            errors += 1
            if not config["dry_run"]:
                df.at[idx, "Status"] = "ERRO"
                df.at[idx, "Observacao"] = str(exc)
            logger.exception("Erro ID=%s: %s", item_id, exc)
        finally:
            if not config["dry_run"]:
                save_queue(df, queue_path)

    summary = {"processed": len(selected), "success": success, "errors": errors, "ignored": ignored}
    message = ("## Processamento finalizado\n"
               f"Processados: {len(selected)}\nSucesso: {success}\n"
               f"Erros: {errors}\nIgnorados: {ignored}")
    print(message)
    logger.info(message)
    return summary


if __name__ == "__main__":
    import argparse
    from src.image_generator import MockImageGenerator

    parser = argparse.ArgumentParser(description="Processa a fila de imagens.")
    parser.add_argument("--mock", action="store_true", help="Gera arquivos fictícios (requer Dry_Run=NAO).")
    args = parser.parse_args()
    main(generator=MockImageGenerator() if args.mock else None)
