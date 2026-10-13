"""Read-only, evidence-based selection shared by preview and execution."""
from src.job_values import canonical_id, cell_text, parse_quantity, ambiguous_legacy_key
from src.execution_state import execution_identity, row_fingerprint, ROW_FINGERPRINT_VERSION

MODES = {'pending', 'errors', 'pending_errors', 'resume', 'review'}

def plan_selection(frame, records, config, max_items, max_images, mode='pending', original_ids=None):
    from main import make_job
    if mode not in MODES:
        raise ValueError('Seleção inválida.')
    if mode == 'resume' and not original_ids:
        raise ValueError('Este histórico não registra a seleção original. Informe explicitamente os IDs do lote; a composição não será inferida.')
    scope = set(original_ids or [])
    selected, decisions, images = [], [], 0
    for index, row in frame.iterrows():
        key = canonical_id(row['ID'])
        status = cell_text(row['Status']).upper()
        record = records.get(key, {})
        phase = record.get('phase')
        category, reason = 'outside', 'Fora da seleção escolhida'
        eligible = False
        if mode == 'resume' and key not in scope:
            pass
        elif status == 'CONCLUIDO' or phase == 'files_ready':
            category, reason = 'completed', 'Saídas concluídas ou disponíveis para recuperação; preservadas'
        elif phase == 'prepared':
            eligible = mode != 'errors'
        elif phase == 'retry_authorized':
            # The signed, explicit authorization remains authoritative even when
            # the sheet still says REVISAO (e.g. recovery or interrupted save).
            eligible = mode in {'review', 'resume', 'pending_errors'} and review_evidence(row, record, config)['releasable']
            if not eligible:
                category, reason = ('outside', 'Revisão liberada: use Repetir itens em revisão') if mode in {'pending', 'errors'} else ('review', 'Liberação não corresponde à linha/configuração ou há saídas locais; confira as evidências')
        elif key in records and phase not in {'rejected', 'local_rejected', 'retry_authorized', 'uncertain', 'in_flight'}:
            category, reason = 'review', 'Registro sem fase reconhecida: correspondência exige revisão'
        elif (not record and ambiguous_legacy_key(key, records)) or phase in {'in_flight', 'uncertain'} or status in {'REVISAO', 'PROCESSANDO'}:
            category, reason = 'review', 'Resultado incerto: use o fluxo de revisão'
        elif status == 'PENDENTE':
            eligible = mode != 'errors' or phase == 'retry_authorized'
        elif status == 'ERRO' and mode != 'pending':
            diagnostic = record.get('error', {})
            if not isinstance(diagnostic, dict):
                diagnostic = {}
            if phase == 'local_rejected' and record.get('local_validation_calls') == 0:
                try:
                    from src.image_generator import OpenAIImageGenerator
                    job = make_job(row, config, True)
                    OpenAIImageGenerator.validate(job)
                    eligible = all(not p.exists() and not p.is_symlink() for p in job.saidas)
                except (ValueError, OSError):
                    pass
            if phase == 'rejected' and diagnostic.get('uncertain') is False:
                # Known transient rejections did not accept the generation.
                eligible = diagnostic.get('category') in {'server', 'limit_quota'} and diagnostic.get('api_code') in {'rate_limit_exceeded', 'slow_down', 'server_is_overloaded'}
                if not eligible and diagnostic.get('category') == 'parameters':
                    try:
                        from src.image_generator import OpenAIImageGenerator
                        job = make_job(row, config, True)
                        OpenAIImageGenerator.validate(job)
                        current, _ = execution_identity(job, row)
                        old_settings = record.get('execution', {}).get('settings')
                        eligible = bool(old_settings) and current['settings'] != old_settings
                    except (ValueError, OSError):
                        pass
            category, reason = 'error', 'Erro confirmado: causa ainda não comprovadamente corrigida'
        if eligible:
            if mode == 'review' and phase != 'retry_authorized':
                eligible = False
                category, reason = 'outside', 'Esta opção executa somente revisões liberadas explicitamente'
        if eligible:
            if phase == 'retry_authorized' and not review_evidence(row, record, config)['releasable']:
                eligible = False
                category, reason = 'review', 'Liberação não corresponde mais à linha/configuração; mantenha em revisão'
        if eligible:
            # A pending label cannot override prior rejected or ambiguous evidence.
            if phase == 'rejected' and status == 'PENDENTE':
                eligible = False
                category, reason = 'error', 'Rejeição registrada: selecione erros e corrija a causa'
            else:
                try:
                    count = parse_quantity(row.get('Quantidade'))
                except ValueError:
                    count = 0  # Preflight reports invalid quantities without a call.
                if len(selected) >= max_items or images + count > max_images:
                    category, reason = 'limit', 'Aguardando limite de itens ou imagens'
                else:
                    selected.append(index)
                    images += count
                    category, reason = 'selected', 'Selecionado para esta execução'
        decisions.append(dict(id=key, category=category, reason=reason))
    return dict(indices=selected, selected_ids=[canonical_id(frame.loc[i, 'ID']) for i in selected],
                images=images, decisions=decisions)

def review_evidence(row, record, config):
    """Never adopt today's row/configuration as proof of a historical attempt."""
    from main import make_job
    from src.execution_state import verified_outputs
    from pathlib import Path
    result = dict(matching=False, recoverable=False, releasable=False, outputs=[],
                  reason='Assinatura, configuração ou referências não comprovadas')
    try:
        paths = [Path(p) for p in record.get('outputs', [])]
        result['outputs'] = [dict(path=str(p), exists=p.exists() or p.is_symlink()) for p in paths]
        job = make_job(row, config, True)
        signature_row = dict(row)
        if job.reference_mode == 'direct':
            signature_row['Arquivo_Referencia'] = ''
        _, identity = execution_identity(job, row)
        matching = (record.get('row_fingerprint_version') == ROW_FINGERPRINT_VERSION and
                    record.get('row_fingerprint') == row_fingerprint(signature_row) and
                    identity == record.get('execution_fingerprint') and tuple(paths) == tuple(job.saidas))
        result['matching'] = matching
        result['releasable'] = matching and bool(paths) and all(not p.exists() and not p.is_symlink() for p in paths)
        if matching and record.get('phase') == 'files_ready':
            result['recoverable'] = verified_outputs(paths, job.settings.output_format) == record.get('hashes')
        if result['recoverable']:
            result['reason'] = 'Linha, configuração, referências e hashes das imagens comprovados'
        elif result['releasable']:
            result['reason'] = 'Identidade comprovada; nenhuma saída local. Reenvio remoto pode gerar outra cobrança.'
        elif matching:
            result['reason'] = 'Existem saídas sem comprovação completa; mantenha em revisão'
    except (ValueError, OSError, KeyError, TypeError):
        pass
    return result
