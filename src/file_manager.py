from pathlib import Path
import re


def validate_reference_path(reference_dir: Path, filename: str) -> Path:
    if not filename:
        raise ValueError("Arquivo_Referencia não informado.")

    root = reference_dir.resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Arquivo_Referencia fora da pasta de referências.")
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError(f"Extensão de referência não suportada: {filename}")
    if not path.is_file():
        raise FileNotFoundError(f"Imagem de referência não encontrada: {path}")

    return path


def validate_reference_paths(reference_dir: Path, filenames: str, reference_dirs=None) -> tuple[Path, ...]:
    names = [name.strip() for name in filenames.split(";")]
    if not filenames.strip() or any(not name for name in names):
        raise ValueError("Arquivo_Referencia não informado ou lista inválida.")
    paths = []
    for name in names:
        root = reference_dir
        if "::" in name:
            alias, name = name.split("::", 1)
            alias, name = alias.strip(), name.strip()
            if alias not in (reference_dirs or {}):
                raise ValueError(f"Pasta de referência não cadastrada: {alias}")
            root = reference_dirs[alias]
            # Aliased names must be relative to the explicitly selected root.
            if Path(name).is_absolute() or Path(name).drive or name.startswith(("/", "\\")):
                raise ValueError("Use um arquivo relativo à pasta de referência cadastrada.")
        paths.append(validate_reference_path(root, name))
    return tuple(paths)


def validate_output_path(result_dir: Path, filename: str, *, check_exists=True) -> Path:
    if not filename or filename in (".", ".."):
        raise ValueError("Nome_Saida não informado ou inválido.")
    if (Path(filename).name != filename or
            re.search(r'[<>:"/\\|?*\x00-\x1f]', filename) or
            filename.endswith((" ", ".")) or
            filename.split(".")[0].upper() in
            {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
             *(f"LPT{i}" for i in range(1, 10))}):
        raise ValueError(f"Nome_Saida inválido: {filename}")
    path = result_dir / filename
    if check_exists and (path.exists() or path.is_symlink()):
        raise FileExistsError(f"Arquivo de saída já existe: {path}")
    return path


def output_paths(result_dir: Path, filename: str, quantity: int) -> tuple[Path, ...]:
    validate_output_path(result_dir, filename)
    base = Path(filename)
    names = ([filename] if quantity == 1 else
             [f"{base.stem}_{number:03d}{base.suffix}" for number in range(1, quantity + 1)])
    return tuple(validate_output_path(result_dir, name) for name in names)


def openai_output_paths(result_dir: Path, filename: str, quantity: int, *, check_exists=True, output_format="png") -> tuple[Path, ...]:
    extensions = {"png": {".png"}, "jpeg": {".jpg", ".jpeg"}, "webp": {".webp"}}
    # Validate the supplied name before adjusting it; normalization must not hide
    # invalid paths or Windows reserved names. Check only the effective targets.
    validate_output_path(result_dir, filename, check_exists=False)
    base = Path(filename)
    if base.suffix.lower() not in extensions[output_format]:
        image_extensions = set().union(*extensions.values())
        # Dots can belong to product codes (e.g. 1.01.06.2702.1), so replace
        # only recognized image extensions and otherwise preserve the full name.
        stem = base.stem if base.suffix.lower() in image_extensions else filename
        filename = f"{stem}.{output_format}"
        base = Path(filename)
    validate_output_path(result_dir, filename, check_exists=check_exists)
    names = ([filename] if quantity == 1 else
             [f"{base.stem}_{number:02d}{base.suffix}" for number in range(1, quantity + 1)])
    return tuple(validate_output_path(result_dir, name, check_exists=check_exists) for name in names)
