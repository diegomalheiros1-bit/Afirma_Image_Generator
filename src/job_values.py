"""Business normalization shared by Excel, job construction and signatures."""
from numbers import Real, Integral
from decimal import Decimal, InvalidOperation
import pandas as pd


def cell_text(value):
    return "" if pd.isna(value) else str(value).strip()


def canonical_id(value):
    if pd.isna(value):
        return ""
    # Only actual numeric cells are normalized. Text '001' and '1.0' stay text.
    if isinstance(value, Integral) and not isinstance(value, bool):
        return str(int(value))
    if isinstance(value, Real) and not isinstance(value, bool) and float(value).is_integer():
        return str(int(value))
    return str(value).strip()


def ambiguous_legacy_key(key, records):
    """Detect potential old pandas ID coercion, without equating textual IDs."""
    try:
        numeric = Decimal(key)
        if not numeric.is_finite():
            return False
        for historic in records:
            try:
                if historic != key and Decimal(historic) == numeric:
                    return True
            except InvalidOperation:
                continue
    except InvalidOperation:
        pass
    return False


def parse_quantity(value):
    if pd.isna(value) or str(value).strip() == "":
        return 1
    try:
        quantity = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Quantidade deve ser um inteiro positivo.") from None
    if (isinstance(value, bool) or not quantity.is_finite()
            or quantity <= 0 or quantity != quantity.to_integral_value()):
        raise ValueError("Quantidade deve ser um inteiro positivo.")
    return int(quantity)
