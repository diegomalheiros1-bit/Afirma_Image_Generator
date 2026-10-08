"""Windows-user-bound storage for the Studio API key; never stores plaintext."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import tempfile


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_void_p)]


def _dpapi(data, *, decrypt=False):
    if os.name != "nt":
        raise OSError("O armazenamento protegido da chave requer Windows.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [ctypes.POINTER(_DataBlob), wintypes.LPCWSTR,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob)]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(_DataBlob), ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob)]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    source = ctypes.create_string_buffer(data)
    incoming = _DataBlob(len(data), ctypes.cast(source, ctypes.c_void_p))
    outgoing = _DataBlob()
    try:
        if decrypt:
            success = crypt32.CryptUnprotectData(ctypes.byref(incoming), None, None, None,
                                                 None, 1, ctypes.byref(outgoing))
        else:
            success = crypt32.CryptProtectData(ctypes.byref(incoming), "Afirma Image Studio",
                                               None, None, None, 1, ctypes.byref(outgoing))
        if not success:
            raise OSError("Não foi possível proteger ou ler a chave neste usuário do Windows.")
        return ctypes.string_at(outgoing.pbData, outgoing.cbData)
    finally:
        if outgoing.pbData:
            if decrypt:
                ctypes.memset(outgoing.pbData, 0, outgoing.cbData)
            kernel32.LocalFree(outgoing.pbData)
        ctypes.memset(source, 0, len(source))


class CredentialStore:
    def __init__(self, settings_path):
        self.path = Path(str(settings_path) + ".api-key.dpapi")

    def exists(self):
        return self.path.is_file()

    def save(self, key):
        encrypted = _dpapi(key.encode("utf-8"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix=".api-key-",
                                             delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def read(self):
        if not self.exists():
            return None
        data = self.path.read_bytes()
        if not 1 <= len(data) <= 8192:
            raise OSError("Arquivo de chave protegido inválido; informe a chave novamente.")
        try:
            return _dpapi(data, decrypt=True).decode("utf-8")
        except (UnicodeError, OSError):
            raise OSError("Não foi possível abrir a chave protegida neste usuário do Windows.") from None

    def clear(self):
        self.path.unlink(missing_ok=True)
