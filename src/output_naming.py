"""Read-only output allocation; persisted allocations are never renumbered."""
from pathlib import Path
from src.file_manager import openai_output_paths, validate_output_path
from src.job_values import canonical_id, cell_text
from src.regeneration import pending_regeneration, record_token


def allocated_paths(paths, allocation):
    if allocation is None:
        return paths
    if (not isinstance(allocation, dict) or allocation.get('version') != 1
            or not isinstance(allocation.get('base'), list)
            or not isinstance(allocation.get('names'), list)):
        raise ValueError('Registro de nomes de saída inválido; confira o histórico.')
    if allocation['base'] != [p.name for p in paths]:
        return paths  # Changed format/row still must pass normal identity checks.
    names = allocation['names']
    if len(names) != len(paths) or any(not isinstance(n, str) for n in names):
        raise ValueError('Registro de nomes de saída incompatível com a quantidade.')
    result = tuple(validate_output_path(paths[0].parent, n, check_exists=False) for n in names)
    if len(set(result)) != len(result) or any(p.suffix != paths[0].suffix for p in result):
        raise ValueError('Registro de nomes de saída inválido.')
    return result


def prepare_output_allocations(frame, records, config):
    """Allocate new jobs and requested regenerations; uncertain attempts keep ownership."""
    from main import make_job
    if not config.get('studio'):
        return
    allocations = dict(config.get('output_allocations', {}))
    config['output_allocations'] = allocations
    regenerations = {canonical_id(row['ID']): record_token(records[canonical_id(row['ID'])])
        for _, row in frame.iterrows()
        if pending_regeneration(row, records.get(canonical_id(row['ID']), {}), config)}
    if 'regeneration_sources' in config:
        for key, source in config['regeneration_sources'].items():
            record = records.get(key, {})
            if record.get('regeneration_source') == source:
                continue  # A persisted new attempt must recover its own allocation.
            if regenerations.get(key) != source:
                raise ValueError('O histórico mudou desde a conferência; confira a campanha novamente.')
    else:
        config['regeneration_sources'] = regenerations
    for key, record in records.items():
        if key in regenerations:
            continue
        if record.get('output_allocation') is not None:
            allocations[key] = record['output_allocation']
        else:
            allocations.pop(key, None)
    reserved = set()
    for record in records.values():
        reserved.update(Path(p) for p in record.get('outputs', []) if isinstance(p, str))
        for previous in record.get('previous_generations', []):
            if isinstance(previous, dict):
                reserved.update(Path(p) for p in previous.get('outputs', []) if isinstance(p, str))
    for _, row in frame.iterrows():
        key = canonical_id(row['ID'])
        if (key in records and key not in regenerations) or cell_text(row.get('Status')).upper() != 'PENDENTE':
            continue
        try:
            job = make_job(row, config, True)
            if key in allocations:
                reserved.update(job.saidas)
                continue  # Frozen preview: never choose a different name at start.
            base = job.saidas
            candidate = base
            version = 1
            settings = config['image_settings']
            single = openai_output_paths(config['result_dir'], job.nome_saida, 1,
                check_exists=False, output_format=settings.output_format)[0]
            while any(p in reserved or p.exists() or p.is_symlink() for p in candidate):
                version += 1
                candidate = openai_output_paths(config['result_dir'],
                    f'{single.stem}_{version:02d}{single.suffix}', job.quantidade,
                    check_exists=False, output_format=settings.output_format)
            allocations[key] = dict(version=1, base=[p.name for p in base],
                                    names=[p.name for p in candidate])
            reserved.update(candidate)
        except (ValueError, OSError):
            continue  # Existing preflight reports the exact invalid row.
