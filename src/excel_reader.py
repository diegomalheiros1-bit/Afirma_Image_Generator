from pathlib import Path
import os
import tempfile
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


def load_config(path: Path) -> dict:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if "Configuracao" not in workbook:
            raise ValueError("Aba Configuracao ausente.")
        rows = workbook["Configuracao"].iter_rows(min_row=2, max_col=2, values_only=True)
        values = {str(key).strip(): value for key, value in rows if key is not None}
        for key in ("Pasta_Referencias", "Pasta_Resultados", "Limite_Por_Execucao"):
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
        return {
            "reference_dir": _config_path(path.parent, values["Pasta_Referencias"]),
            "result_dir": _config_path(path.parent.parent / "output", values["Pasta_Resultados"]),
            "limit": limit,
            "dry_run": dry_run == "SIM",
        }
    finally:
        workbook.close()


def _config_path(base: Path, value) -> Path:
    path = Path(str(value).strip())
    return (path if path.is_absolute() else base / path).resolve()


def load_queue(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {path}")

    # Preserve the Excel cell type: text IDs such as '001' must not become 1.
    # Text such as 'NA' is valid business content, not a pandas missing marker.
    df = pd.read_excel(path, sheet_name="Fila_Geracao", dtype=object, keep_default_na=False)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {missing}")

    df["Observacao"] = df["Observacao"].astype(object)
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
