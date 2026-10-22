"""Read and validate local run history without touching campaign state."""
import json
from pathlib import Path


def read_history(queue):
    if not queue:
        return {'runs': [], 'warnings': []}
    paths = list(Path(str(queue) + '.studio-runs').glob('*.json'))
    paths.append(Path(str(queue) + '.studio-run.json'))
    records, warnings = {}, []
    for path in paths:
        if not path.exists():
            continue
        try:
            value = json.loads(path.read_text('utf-8'))
            if not isinstance(value, dict) or not isinstance(value.get('events', []), list):
                raise ValueError()
            if any(not isinstance(e, dict) for e in value.get('events', [])):
                raise ValueError()
            if value.get('run_id') is not None and not isinstance(value['run_id'], str):
                raise ValueError()
            for event in value.get('events', []):
                if 'outputs' in event and (not isinstance(event['outputs'], list) or
                        any(not isinstance(path, str) for path in event['outputs'])):
                    raise ValueError()
                for field in ('diagnostic', 'usage'):
                    if field in event and not isinstance(event[field], dict):
                        raise ValueError()
            for field in ('settings', 'counts', 'result'):
                if field in value and not isinstance(value[field], dict):
                    raise ValueError()
            for field in ('selected_ids', 'original_selected_ids'):
                if field in value and (not isinstance(value[field], list) or
                        any(not isinstance(key, str) or not key for key in value[field])):
                    raise ValueError()
            if 'image' in value.get('settings', {}) and not isinstance(value['settings']['image'], dict):
                raise ValueError()
            records[value.get('run_id') or path.name] = value
        except (ValueError, OSError):
            warnings.append('Histórico indisponível ou inválido: ' + path.name)
    return {'runs': sorted(records.values(), key=lambda r: str(r.get('started_at', '')), reverse=True), 'warnings': warnings}
