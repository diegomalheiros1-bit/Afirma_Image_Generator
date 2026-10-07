from pathlib import Path
import os
import tempfile
import re
import pandas as pd
from openpyxl import load_workbook
from src.execution_state import PersistenceError

REQUIRED_COLUMNS = [
    "ID",
    "Prompt_Padrao",
    "Prompt_Variacao",
    "Arquivo_Referencia",
    "Nome_Saida",
    "Status",
    "Tentativas",
    "Observacao",
]


def load_config(path: Path, *, reference_mode="spreadsheet") -> dict:
    if reference_mode not in {"spreadsheet", "direct"}:
        raise ValueError("Modo de referências inválido.")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if "Configuracao" not in workbook:
            raise ValueError("Aba Configuracao ausente.")
        rows = workbook["Configuracao"].iter_rows(min_row=2, max_col=2, values_only=True)
        values = {str(key).strip(): value for key, value in rows if key is not None}
        required = ("Pasta_Resultados", "Limite_Por_Execucao")
        if reference_mode == "spreadsheet":
            required += ("Pasta_Referencias",)
        for key in required:
            if key not in values or values[key] is None or str(values[key]).strip() == "":
                raise ValueError(f"Configuracao ausente: {key}")
        raw_limit = values["Limite_Por_Execucao"]
        try:
            limit = int(raw_limit)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("Limite_Por_Execucao deve ser inteiro positivo.") from exc
        if limit <= 0 or str(raw_limit).strip() != str(limit):
            raise ValueError("Limite_Por_Execucao deve ser inteiro positivo.")
        dry_run = str(values.get("Dry_Run", "SIM")).strip().upper()
        if dry_run not in ("SIM", "NAO", "NÃO"):
            raise ValueError("Dry_Run deve ser SIM ou NAO.")
        reference_dirs = {}
        if "Pastas_Referencias" in workbook and reference_mode != "direct":
            sheet = workbook["Pastas_Referencias"]
            if next(sheet.iter_rows(min_row=1, max_row=1, max_col=2, values_only=True)) != ("Alias", "Caminho"):
                raise ValueError("Pastas_Referencias deve conter as colunas Alias e Caminho.")
            for alias, folder in sheet.iter_rows(min_row=2, max_col=2, values_only=True):
                if alias is None and folder is None:
                    continue
                alias = str(alias or "").strip()
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", alias):
                    raise ValueError("Alias de pasta inválido: use letras, números, hífen ou sublinhado; comece com letra.")
                if alias.casefold() in {key.casefold() for key in reference_dirs}:
                    raise ValueError(f"Alias de pasta duplicado: {alias}")
                if folder is None or not str(folder).strip():
                    raise ValueError(f"Caminho de pasta ausente: {alias}")
                root = _config_path(path.parent, folder)
                if not root.is_dir():
                    raise ValueError(f"Pasta de referência não encontrada: {alias}")
                reference_dirs[alias] = root
        return {
            "reference_dirs": reference_dirs,
            "reference_dir": (_config_path(path.parent, values["Pasta_Referencias"])
                              if str(values.get("Pasta_Referencias") or "").strip() else None),
            "result_dir": _config_path(path.parent.parent / "output", values["Pasta_Resultados"]),
            "limit": limit,
            "dry_run": dry_run == "SIM",
        }
    finally:
        workbook.close()


def _config_path(base: Path, value) -> Path:
    path = Path(str(value).strip())
    return (path if path.is_absolute() else base / path).resolve()


def load_queue(path: Path, *, reference_mode="spreadsheet") -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {path}")

    # Preserve the Excel cell type: text IDs such as '001' must not become 1.
    # Text such as 'NA' is valid business content, not a pandas missing marker.
    df = pd.read_excel(path, sheet_name="Fila_Geracao", dtype=object, keep_default_na=False)

    if reference_mode not in {"spreadsheet", "direct"}:
        raise ValueError("Modo de referências inválido.")
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns
               and not (reference_mode == "direct" and col == "Arquivo_Referencia")]
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {missing}")

    df["Observacao"] = df["Observacao"].astype(object)
    if "Arquivo_Referencia" not in df:
        df["Arquivo_Referencia"] = ""
    return df


def save_queue(df: pd.DataFrame, path: Path) -> None:
    try:
        _save_queue(df, path)
    except Exception:
        raise PersistenceError(
            "Não foi possível salvar o Excel (arquivo aberto, permissão ou disco). "
            "Novas gerações interrompidas; feche o Excel e preserve o .state.json."
        ) from None


def _save_queue(df: pd.DataFrame, path: Path) -> None:
    """Update queue cells while retaining all other sheets and workbook content."""
    workbook = load_workbook(path)
    sheet = workbook["Fila_Geracao"]
    columns = {cell.value: cell.column for cell in sheet[1]}
    for index, row in df.iterrows():
        for name in ("Status", "Tentativas", "Observacao"):
            value = row[name]
            sheet.cell(row=index + 2, column=columns[name]).value = (
                None if pd.isna(value) else value
            )

    try:
        _save_workbook_atomic(workbook, path)
    finally:
        workbook.close()


def _save_workbook_atomic(workbook, path):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
        workbook.save(temporary)
        os.replace(temporary, path)
    finally:
        workbook.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)
