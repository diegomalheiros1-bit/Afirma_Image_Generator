"""Small local journal and OS lock. Neither stores prompts nor credentials."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
from itertools import product
from numbers import Real
from src.job_values import canonical_id, cell_text, parse_quantity

from PIL import Image


class PersistenceError(RuntimeError):
    pass


@contextmanager
def queue_lock(queue):
    # Keep the inode: removing the lock file can create two independent locks.
    path = Path(str(queue.resolve()) + ".lock")
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise PersistenceError("Outra instância está usando esta fila. Aguarde seu término.") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verified_outputs(paths):
    hashes = {}
    for path in paths:
        with Image.open(path) as image:
            if image.format != "PNG":
                raise ValueError("A saída não é PNG.")
            image.verify()
        hashes[str(path)] = digest(path)
    if not hashes:
        raise ValueError("Nenhuma saída gerada.")
    return hashes


def validate_output_directory(path):
    """Create and probe the output directory before any paid API call."""
    path = Path(path)
    probe = None
    try:
        if path.exists() and not path.is_dir():
            raise PersistenceError(f"Pasta_Resultados aponta para um arquivo: {path}")
        path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise PersistenceError(f"Pasta_Resultados não é um diretório: {path}")
        with tempfile.NamedTemporaryFile(prefix=".afirma-write-test-", suffix=".tmp",
                                         dir=path, delete=False) as handle:
            probe = Path(handle.name)
            handle.write(b"storage-check")
            handle.flush()
            os.fsync(handle.fileno())
    except PersistenceError:
        raise
    except PermissionError:
        raise PersistenceError(f"Sem permissão de escrita em Pasta_Resultados: {path}") from None
    except OSError as exc:
        raise PersistenceError(
            f"Falha de armazenamento ao validar Pasta_Resultados ({type(exc).__name__}): {path}"
        ) from None
    finally:
        if probe is not None:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                raise PersistenceError(
                    f"Falha ao remover arquivo de teste em Pasta_Resultados: {path}"
                ) from None


class Journal:
    def __init__(self, queue):
        self.path = Path(str(queue.resolve()) + ".state.json")
        try:
            self.records = json.loads(self.path.read_text("utf-8")) if self.path.exists() else {}
            if not isinstance(self.records, dict):
                raise ValueError()
        except (ValueError, OSError):
            raise PersistenceError("Registro de execução ilegível; restaure o backup antes de gerar.") from None

    def put(self, key, **values):
        self.records.setdefault(key, {}).update(values)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(self.records, handle, ensure_ascii=True, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except OSError:
            raise PersistenceError("Falha ao salvar registro de execução. Novas gerações interrompidas.") from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def fingerprint(job, model, quality):
    value = [job.prompt, str(job.id), model, quality,
             [(str(path), digest(path)) for path in job.referencias],
             [str(path) for path in job.saidas]]
    return hashlib.sha256(json.dumps(value, ensure_ascii=True).encode()).hexdigest()


ROW_FINGERPRINT_VERSION = 2
ROW_FIELDS = ("ID", "Prompt_Padrao", "Prompt_Variacao", "Arquivo_Referencia", "Nome_Saida",
              "Tema", "Produto", "Cliente", "Prompt_Negativo", "Quantidade", "Observacao_Usuario")


def canonical_row(row):
    values = {name: cell_text(row.get(name)) for name in ROW_FIELDS}
    values["ID"] = canonical_id(row.get("ID"))
    values["Quantidade"] = str(parse_quantity(row.get("Quantidade")))
    return [[name, values[name]] for name in ROW_FIELDS]


def _row_hash(values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=True).encode()).hexdigest()


def row_fingerprint(row):
    return _row_hash(canonical_row(row))


def matches_v1(row, expected):
    """Prove compatibility against the stored hash, never adopt the current row blindly.

    Only ID numeric representation and equivalent valid quantity representations
    are enumerated. Every text field must match exactly under the old trim rule.
    """
    values = dict(canonical_row(row))
    quantity = parse_quantity(row.get("Quantidade"))
    quantities = [str(quantity), f"{quantity}.0"] + ([""] if quantity == 1 else [])
    ids = [canonical_id(row.get("ID"))]
    raw_id = row.get("ID")
    if isinstance(raw_id, Real) and not isinstance(raw_id, bool) and float(raw_id).is_integer():
        ids.append(f"{int(raw_id)}.0")
    for id_value, quantity_value in product(ids, quantities):
        candidate = {**values, "ID": id_value, "Quantidade": quantity_value}
        if _row_hash([[name, candidate[name]] for name in ROW_FIELDS]) == expected:
            return True
    return False
