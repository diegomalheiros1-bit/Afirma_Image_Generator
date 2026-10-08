"""Prepare or open the isolated three-image pilot. Paid generation requires UI confirmation."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openpyxl import Workbook
from main import main
from src.execution_state import digest
from src.image_settings import ImageSettings
from src.studio_session import StudioSession
from studio import make_server

PILOT = ROOT / 'output' / 'piloto-real-3-imagens'
QUEUE = PILOT / 'campanha-3-imagens.xlsx'
PREFERENCES = PILOT / 'preferences.json'


def prepare():
    if PILOT.exists():
        raise SystemExit('Piloto já existe. Preserve os arquivos e use --serve para abri-lo.')
    source = ROOT / 'output' / 'studio-verification'
    references = [source / 'produtos' / 'foto.png', source / 'marca' / 'foto.png']
    from src.studio_session import validate_photos
    validate_photos(references)
    PILOT.mkdir(parents=True)
    refs = PILOT / 'referencias'
    refs.mkdir()
    for origin, name in zip(references, ('produto.png', 'marca.png')):
        shutil.copyfile(origin, refs / name)
    settings = ImageSettings(quality='low', background='opaque', size='1024x1024')
    book = Workbook()
    sheet = book.active
    sheet.title = 'Fila_Geracao'
    sheet.append(['ID', 'Prompt_Padrao', 'Prompt_Variacao', 'Arquivo_Referencia',
                  'Nome_Saida', 'Status', 'Tentativas', 'Observacao', 'Quantidade'])
    variations = ('Composição frontal com os dois objetos lado a lado.',
                  'Composição em perspectiva de três quartos, caixa atrás do frasco.',
                  'Composição vista de cima com os dois objetos sobre uma superfície clara.')
    for number, variation in enumerate(variations, 1):
        sheet.append([f'PILOTO3-{number:03d}',
                      'Fotografia publicitária de um frasco de perfume roxo e uma caixa laranja, '
                      'em fundo claro, sem texto. Use as cores das referências como inspiração.',
                      variation, 'produto.png;marca.png', f'piloto_3_{number:03d}.png',
                      'PENDENTE', 0, '', 1])
    config = book.create_sheet('Configuracao')
    for row in [('Parametro', 'Valor'), ('Pasta_Referencias', 'referencias'),
                ('Pasta_Resultados', str(PILOT / 'saida')), ('Limite_Por_Execucao', 3),
                ('Dry_Run', 'SIM')]:
        config.append(row)
    book.save(QUEUE)
    book.close()
    preferences = dict(image=asdict(settings), output_dir=str(PILOT / 'saida'), timeout=120,
                       retries=0, max_jobs=3, max_images=3, safe_mode=False)
    PREFERENCES.write_text(json.dumps({'version': 1, 'preferences': preferences}, indent=2), encoding='utf-8')
    # Isolated rollback copy; never replace an existing campaign or history.
    shutil.copyfile(QUEUE, PILOT / 'campanha-3-imagens.original.xlsx')
    session = StudioSession(PREFERENCES, env={})
    session.choose_queue(QUEUE)
    plan = session.validate_campaign()
    before = digest(QUEUE)
    config, _ = session.snapshot()
    summary = main(QUEUE, env=dict(IMAGE_PROVIDER='openai', DRY_RUN='SIM', FIRST_RUN_SAFE_MODE='NAO',
                                   MAX_JOBS_PER_RUN='3', MAX_IMAGES_PER_RUN='3', OPENAI_RETRIES='0'),
                   overrides=config)
    if summary != dict(processed=3, success=3, errors=0, ignored=0) or digest(QUEUE) != before:
        raise RuntimeError('DRY RUN não aprovado; preserve a campanha para revisão.')
    (PILOT / 'preflight.json').write_text(json.dumps(dict(plan=plan, preferences=preferences,
        summary=summary, queue_sha256=before, paid_generation_executed=False), indent=2,
        ensure_ascii=False), encoding='utf-8')
    print('Piloto preparado: 3 imagens, DRY RUN aprovado, nenhuma chamada paga.')


def serve(enable_api):
    if not QUEUE.exists() or not PREFERENCES.exists():
        raise SystemExit('Prepare primeiro: python scripts/real_pilot.py')
    session = StudioSession(PREFERENCES, allow_api=enable_api)
    session.choose_queue(QUEUE)
    server = make_server(session)  # Loopback only.
    print(f'Piloto: http://127.0.0.1:{server.server_port}/\n'
          f'API paga: {"HABILITADA — confirmar na interface" if enable_api else "BLOQUEADA"}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if session.active:
            session.command('stop')
    finally:
        server.server_close()
        if session.worker:
            session.worker.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', action='store_true', help='Abre a campanha já preparada.')
    parser.add_argument('--enable-api', action='store_true', help='Habilita botão pago; não inicia geração.')
    args = parser.parse_args()
    if args.enable_api and not args.serve:
        parser.error('--enable-api exige --serve')
    serve(args.enable_api) if args.serve else prepare()
