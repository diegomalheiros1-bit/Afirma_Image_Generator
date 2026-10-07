"""Prepare and DRY RUN a one-image proposal. Never call OpenAI or read .env."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openpyxl import Workbook
from main import main
from src.image_settings import ImageSettings


if __name__ == '__main__':
    root=ROOT/'output'/'studio-verification'/'teste-real-proposto'
    root.mkdir(parents=True,exist_ok=True)
    queue=root/'campanha-1-imagem.xlsx'
    if queue.exists() or Path(str(queue)+'.state.json').exists():
        raise SystemExit('Proposta já existe; preserve a planilha e seu possível histórico.')
    references=[root.parent/'produtos'/'foto.png',root.parent/'marca'/'foto.png']
    if not all(p.is_file() for p in references):
        raise SystemExit('Execute primeiro scripts/verify_studio.py para criar referências fictícias.')
    settings=ImageSettings(quality='low',background='opaque',size='1024x1024')
    book=Workbook()
    sheet=book.active
    sheet.title='Fila_Geracao'
    sheet.append(['ID','Prompt_Padrao','Prompt_Variacao','Arquivo_Referencia','Nome_Saida','Status','Tentativas','Observacao'])
    sheet.append(['API-TESTE-001','Fotografia publicitária de um frasco de perfume roxo ao lado de uma caixa laranja, em fundo claro, sem texto.',
                  'Use as cores das referências como inspiração para os dois objetos.','',
                  'api_teste_001.png','PENDENTE',0,''])
    config=book.create_sheet('Configuracao')
    for row in [('Parametro','Valor'),('Pasta_Referencias',str(references[0].parent)),
                ('Pasta_Resultados',str(root/'saida')),('Limite_Por_Execucao',1),('Dry_Run','SIM')]:
        config.append(row)
    book.save(queue)
    book.close()
    preferences=dict(image=asdict(settings),output_dir=str(root/'saida'),timeout=120,retries=0,
                     max_jobs=1,max_images=1,safe_mode=True)
    (root/'preferences.json').write_text(json.dumps({'version':1,'preferences':preferences},indent=2),encoding='utf-8')
    overrides=dict(reference_mode='direct',direct_references=references,image_settings=settings,studio=True)
    summary=main(queue,env=dict(IMAGE_PROVIDER='openai',DRY_RUN='SIM',FIRST_RUN_SAFE_MODE='SIM',
                               MAX_JOBS_PER_RUN='1',MAX_IMAGES_PER_RUN='1'),overrides=overrides)
    (root/'proposal.json').write_text(json.dumps({'queue':str(queue),'references':[str(p) for p in references],
                                                'preferences':preferences,'dry_run':summary,'authorized':False},indent=2),encoding='utf-8')
    print('Proposta preparada; geração real NÃO autorizada e NÃO executada.')
