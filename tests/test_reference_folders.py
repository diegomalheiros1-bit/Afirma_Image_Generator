import tempfile
import unittest
from pathlib import Path
from openpyxl import Workbook
from src.file_manager import validate_reference_paths
from src.excel_reader import load_config
from main import make_job


class ReferenceFoldersTests(unittest.TestCase):
    def test_mixed_roots_and_legacy_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            x, y = base/'x', base/'y'
            x.mkdir(); y.mkdir()
            (x/'same.png').touch(); (y/'same.png').touch()
            paths = validate_reference_paths(x, 'same.png; X::same.png; Y::same.png', {'X':x,'Y':y})
            self.assertEqual(paths, ((x/'same.png').resolve(), (x/'same.png').resolve(), (y/'same.png').resolve()))
            for value in ['Z::same.png', 'X::../y/same.png', 'X::', 'X::missing.png', str(y/'same.png'), 'X::'+str(x/'same.png')]:
                with self.subTest(value=value), self.assertRaises((ValueError, FileNotFoundError)):
                    validate_reference_paths(x, value, {'X':x})

    def test_config_to_job_and_duplicate_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); (base/'x').mkdir(); (base/'y').mkdir(); (base/'out').mkdir()
            (base/'x'/'front.png').touch(); (base/'y'/'back.png').touch()
            book=Workbook(); sheet=book.active; sheet.title='Configuracao'
            for row in [('Parametro','Valor'),('Pasta_Referencias','x'),('Pasta_Resultados',str(base/'out')),('Limite_Por_Execucao',1)]:sheet.append(row)
            roots=book.create_sheet('Pastas_Referencias')
            roots.append(['Alias','Caminho']);roots.append(['X','x']);roots.append(['Y','y'])
            queue=base/'fila.xlsx';book.save(queue)
            config=load_config(queue)
            row={'ID':'1','Prompt_Padrao':'test','Arquivo_Referencia':'X::front.png; Y::back.png','Nome_Saida':'result.png','Status':'PENDENTE','Tentativas':0}
            job=make_job(row,config,False)
            self.assertEqual(job.referencias,((base/'x'/'front.png').resolve(),(base/'y'/'back.png').resolve()))
            roots.append(['x','y']);book.save(queue)
            with self.assertRaisesRegex(ValueError,'duplicado'):load_config(queue)
            book.close()
