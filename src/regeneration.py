"""An explicit pending sheet row can request a new, completed Studio generation."""
import hashlib
import json

from src.job_values import cell_text


def pending_regeneration(row, record, config, mode=None):
    """Never turn uncertain, interrupted or unrecognized history into a new job."""
    outputs, hashes = record.get('outputs'), record.get('hashes')
    return bool(config.get('studio')
        and (mode or config.get('selection_mode', 'pending')) == 'pending'
        and cell_text(row.get('Status')).upper() == 'PENDENTE'
        and record.get('phase') == 'files_ready'
        and isinstance(outputs, list) and outputs
        and all(isinstance(p, str) and p for p in outputs)
        and isinstance(hashes, dict) and set(outputs) == set(hashes)
        and all(isinstance(h, str) and len(h) == 64 for h in hashes.values()))


def record_token(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True,
        ensure_ascii=True).encode('utf-8')).hexdigest()
