"""Small local journal and OS lock. Neither stores prompts nor credentials."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile

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
