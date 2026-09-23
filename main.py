from dataclasses import replace
from pathlib import Path
import os
import uuid
import pandas as pd
from dotenv import dotenv_values

from src.excel_reader import load_config, load_queue, save_queue
from src.execution_state import (Journal, PersistenceError, fingerprint, queue_lock,
                                 row_fingerprint, validate_output_directory, verified_outputs)
from src.prompt_builder import build_prompt
from src.file_manager import openai_output_paths, output_paths, validate_reference_paths
from src.generation_job import GenerationJob
from src.image_generator import (GenerationError, MockImageGenerator, OpenAIImageGenerator,
                                 OutputStorageError)
from src.logger import get_logger

QUEUE_PATH = Path("input/fila.xlsx")
logger = get_logger()


def is_pending(status):
    return isinstance(status, str) and status.strip().upper() == "PENDENTE"


def cell_text(value):
    return "" if pd.isna(value) else str(value).strip()


def parse_quantity(value):
    if pd.isna(value) or str(value).strip() == "":
        return 1
    try:
        quantity = int(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Quantidade deve ser um inteiro positivo.") from None
    if quantity <= 0 or str(value).strip() not in (str(quantity), f"{quantity}.0"):
        raise ValueError("Quantidade deve ser um inteiro positivo.")
    return quantity


def flag(value):
    value = str(value).strip().upper()
    if value not in {"SIM", "NAO", "NÃO"}:
        raise ValueError("Configuração booleana deve ser SIM ou NAO.")
    return value == "SIM"


def positive_limit(env, name, default):
    value = int(env.get(name, default))
    if value <= 0:
        raise ValueError(f"{name} deve ser positivo.")
    return value


def make_job(row, config, real):
    text = lambda name: cell_text(row.get(name))
    quantity = parse_quantity(row.get("Quantidade"))
    name = text("Nome_Saida")
    paths = (openai_output_paths(config["result_dir"], name, quantity, check_exists=False) if real else
             output_paths(config["result_dir"], name, quantity))
    attempts = 0 if pd.isna(row["Tentativas"]) else int(row["Tentativas"])
    return GenerationJob(
        id=text("ID"), prompt=build_prompt(text("Prompt_Padrao"), text("Prompt_Variacao"),
            tema=text("Tema"), produto=text("Produto"), observacao_usuario=text("Observacao_Usuario"),
            prompt_negativo=text("Prompt_Negativo")),
        referencias=validate_reference_paths(config["reference_dir"], text("Arquivo_Referencia")),
        nome_saida=name, status=text("Status"), tentativas=attempts, quantidade=quantity, saidas=paths,
        tema=text("Tema"), produto=text("Produto"), cliente=text("Cliente"),
        prompt_negativo=text("Prompt_Negativo"), observacao_usuario=text("Observacao_Usuario"))


def recover(df, journal, queue):
    blocked = set()
    changed = False

    def update(idx, name, value):
        nonlocal changed
        current = df.at[idx, name]
        same = (pd.isna(current) and value is None) or current == value
        if not same:
            df.at[idx, name] = value
            changed = True

    for idx, row in df.iterrows():
        key = cell_text(row["ID"])
        record = journal.records.get(key)
        status = cell_text(row["Status"]).upper()
        if not record and status not in {"PROCESSANDO", "REVISAO"}:
            continue
        phase = record.get("phase") if record else None
        if phase == "rejected":
            if status == "PROCESSANDO":
                update(idx, "Status", "ERRO")
                update(idx, "Observacao", "API rejeitou a chamada; corrija a causa antes de retornar a PENDENTE.")
            continue
        if phase == "prepared":
            # Journal was persisted before PROCESSANDO; no call could have started.
            update(idx, "Status", "PENDENTE")
            update(idx, "Observacao", "Recuperado antes de chamada à API.")
            continue
        if phase == "files_ready":
            try:
                historic_paths = tuple(Path(path) for path in record["outputs"])
                files_valid = verified_outputs(historic_paths) == record["hashes"]
                row_valid = ("row_fingerprint" not in record or
                             row_fingerprint(row) == record["row_fingerprint"])
                valid = files_valid and row_valid
            except Exception:
                valid = False
            if valid:
                if status != "CONCLUIDO":
                    update(idx, "Status", "CONCLUIDO")
                    update(idx, "Tentativas", record["task_attempts"])
                    update(idx, "Observacao", "Saídas verificadas no registro; nenhuma nova chamada.")
                blocked.add(idx)
                continue
        blocked.add(idx)
        update(idx, "Status", "REVISAO")
        update(idx, "Observacao", "Resultado incerto ou divergente; confira .state.json e arquivos antes de reenviar.")
        logger.warning("ID=%s bloqueado para revisão; nenhuma chamada será repetida.", key)
    if changed:
        save_queue(df, queue)
    return blocked


def main(queue_path=QUEUE_PATH, reference_dir=None, generator=None, *, env=None):
    queue_path = Path(queue_path).resolve()
    # Explicit env lets tests run without even reading the project's secret file.
    if env is None:
        env = {**dotenv_values(queue_path.parent.parent / ".env"), **os.environ}
    with queue_lock(queue_path):
        return process_queue(queue_path, reference_dir, generator, env)


def process_queue(queue, reference_dir, generator, env):
    config = load_config(queue)
    if "DRY_RUN" in env:
        config["dry_run"] = flag(env["DRY_RUN"])
    if reference_dir is not None:
        config["reference_dir"] = Path(reference_dir).resolve()
    provider = env.get("IMAGE_PROVIDER", "simulation").strip().lower()
    if generator is not None:
        provider = "openai" if generator.is_real else "mock"
    if provider not in {"simulation", "mock", "openai"}:
        raise ValueError("IMAGE_PROVIDER deve ser simulation, mock ou openai.")
    real = provider == "openai"
    dry = config["dry_run"]
    max_jobs = positive_limit(env, "MAX_JOBS_PER_RUN", 1)
    max_images = positive_limit(env, "MAX_IMAGES_PER_RUN", 1)
    safe = flag(env.get("FIRST_RUN_SAFE_MODE", "SIM"))
    if real and not dry and safe and (max_jobs > 1 or max_images > 1 or config["limit"] > 1):
        raise ValueError("FIRST_RUN_SAFE_MODE=SIM exige todos os limites <= 1.")
    model = getattr(generator, "model", env.get("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst"))
    quality = getattr(generator, "quality", env.get("OPENAI_IMAGE_QUALITY", "auto"))
    df = load_queue(queue)
    ids = df["ID"].map(cell_text)
    if ids.eq("").any() or ids.duplicated().any():
        raise ValueError("Cada linha deve ter um ID preenchido e único, estável entre execuções.")
    journal = Journal(queue) if real else None
    blocked = set()
    if real and not dry:
        blocked = recover(df, journal, queue)
    pending = [idx for idx, row in df.iterrows() if idx not in blocked and is_pending(row["Status"])]
    selected, images = [], 0
    for idx in pending:
        try:
            count = parse_quantity(df.loc[idx].get("Quantidade"))
        except ValueError:
            count = 0  # Validation below reports an invalid row without spending credits.
        reason = None
        if len(selected) >= min(max_jobs, config["limit"]):
            reason = "limite de jobs atingido"
        elif images + count > max_images:
            reason = f"Quantidade={count} excede saldo de {max_images - images} imagens"
        if reason:
            logger.warning("ID=%s não selecionado: %s", ids[idx], reason)
            continue
        selected.append(idx)
        images += count
    print(f"Provider: {'OpenAI' if real else provider}\nJobs encontrados: {len(pending)}\n"
          f"Imagens previstas: {images}\nLimite configurado: {min(max_jobs, config['limit'])} jobs / {max_images} imagens")
    logger.info("Início | total=%s pendentes=%s selecionados=%s dry_run=%s", len(df), len(pending), len(selected), dry)
    success = errors = 0
    mock_dir = config["result_dir"] / "_mock" / uuid.uuid4().hex
    if real and not dry and selected:
        validate_output_directory(config["result_dir"])
    for idx in selected:
        key = ids[idx]
        row = df.loc[idx]
        logger.info("Iniciado ID=%s", key)
        # Validation failures are local and do not count as paid task attempts.
        try:
            job = make_job(row, config, real)
            if real:
                OpenAIImageGenerator.validate(job)
                if any(path.exists() or path.is_symlink() for path in job.saidas):
                    raise ValueError("Saída existente sem recuperação confirmada; revise os arquivos.")
        except (ValueError, OSError) as exc:
            errors += 1
            logger.error("ID=%s: validação local: %s", key, exc)
            if real and not dry:
                df.at[idx, "Status"] = "ERRO"
                df.at[idx, "Observacao"] = str(exc)
                save_queue(df, queue)
            continue
        if dry:
            print(f"DRY RUN | ID: {key}\nPrompt final: {job.prompt}\n"
                  f"Arquivo de referência: {'; '.join(map(str, job.referencias))}\n"
                  f"Nome do arquivo de saída: {'; '.join(p.name for p in job.saidas)}\n")
            success += 1
            continue
        if not real:
            try:
                if provider == "mock":
                    mock = generator or MockImageGenerator()
                    mock.generate(replace(job, saidas=tuple(mock_dir / p.name for p in job.saidas)))
                logger.info("ID=%s simulado; PENDENTE preservado.", key)
                success += 1
            except Exception:
                logger.error("ID=%s falha no mock; PENDENTE preservado.", key)
                errors += 1
            continue
        if generator is None:
            generator = OpenAIImageGenerator(api_key=env.get("OPENAI_API_KEY"), model=model, quality=quality,
                timeout=positive_limit(env, "OPENAI_TIMEOUT_SECONDS", 120), retries=int(env.get("OPENAI_RETRIES", 2)))
        attempts = job.tentativas + 1
        previous_api = journal.records.get(key, {}).get("api_attempts", 0)
        journal.put(key, phase="prepared", fingerprint=fingerprint(job, model, quality),
                    outputs=[str(p) for p in job.saidas], task_attempts=attempts,
                    api_attempts=previous_api, hashes={}, model=model, quality=quality,
                    row_fingerprint=row_fingerprint(row), result_dir=str(config["result_dir"]))
        df.at[idx, "Status"] = "PROCESSANDO"
        df.at[idx, "Tentativas"] = attempts
        save_queue(df, queue)  # MUST succeed before making a paid request.

        def before_attempt(number):
            journal.put(key, phase="in_flight", api_attempts=previous_api + number)
            logger.info("ID=%s tentativa da tarefa=%s chamada API=%s", key, attempts, previous_api + number)

        generator.before_attempt = before_attempt
        try:
            generator.generate(replace(job, tentativas=attempts, status="PROCESSANDO"))
            hashes = verified_outputs(job.saidas)
        except PersistenceError:
            raise
        except OutputStorageError as exc:
            try:
                journal.put(key, phase="uncertain", storage_failure=True)
                df.at[idx, "Status"] = "REVISAO"
                df.at[idx, "Observacao"] = str(exc)
                save_queue(df, queue)
            except PersistenceError:
                raise
            logger.error("ID=%s: %s", key, exc)
            raise PersistenceError(
                "Falha ao gravar imagem após resposta da API. Novas chamadas interrompidas; "
                "preserve arquivos e .state.json para revisão."
            ) from None
        except Exception as exc:
            uncertain = not isinstance(exc, GenerationError) or exc.uncertain
            message = str(exc) if isinstance(exc, GenerationError) else "Falha após iniciar geração; resultado requer revisão."
            journal.put(key, phase="uncertain" if uncertain else "rejected")
            df.at[idx, "Status"] = "REVISAO" if uncertain else "ERRO"
            df.at[idx, "Observacao"] = message
            save_queue(df, queue)
            errors += 1
            logger.error("ID=%s: %s", key, message)
            continue
        journal.put(key, phase="files_ready", hashes=hashes)
        df.at[idx, "Status"] = "CONCLUIDO"
        df.at[idx, "Observacao"] = "Imagens PNG verificadas; registro persistido."
        save_queue(df, queue)
        success += 1
        logger.info("Sucesso ID=%s", key)
    summary = dict(processed=len(selected), success=success, errors=errors, ignored=len(df) - len(selected))
    message = (f"Processamento finalizado\nProcessados: {len(selected)}\nSucesso: {success}\n"
               f"Erros: {errors}\nIgnorados: {summary['ignored']}")
    print(message)
    logger.info(message)
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Processa a fila de imagens.")
    parser.add_argument("--mock", action="store_true", help="Simula em subpasta _mock; mantém PENDENTE.")
    args = parser.parse_args()
    try:
        main(generator=MockImageGenerator() if args.mock else None)
    except Exception as exc:
        logger.error("Execução interrompida: %s", str(exc) if isinstance(exc, (PersistenceError, ValueError)) else type(exc).__name__)
        raise SystemExit(1)
