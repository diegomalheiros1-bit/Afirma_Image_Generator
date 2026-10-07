import test_studio
from support import IsolatedTest
from src.execution_state import Journal
from src.excel_reader import load_queue
from main import main

class ReviewFindings(IsolatedTest):
    def setUp(self):
        self.fixture = test_studio.StudioTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        for name in ("queue", "refs", "session", "env", "generator", "edit_queue"):
            setattr(self, name, getattr(self.fixture, name))
    def test_prepared_studio_snapshot_can_resume(self):
        self.edit_queue(lambda b: b['Fila_Geracao'].__setitem__('F2', 'PROCESSANDO'))
        Journal(self.queue).put('1', phase='prepared')
        photo=self.refs/'unique.png'
        photo.write_bytes((self.refs/'ok.png').read_bytes())
        self.edit_queue(lambda b: b['Fila_Geracao'].__setitem__('D2', 'unique.png'))
        plan = self.session.validate_campaign()
        config, _ = self.session.snapshot()
        from pathlib import Path
        from src.execution_state import digest
        config['expected_reference_hashes'] = {p:digest(Path(p)) for job in plan['jobs'] for p in job['references']}
        # Give the interrupted row a unique reference so other pending rows cannot mask the missing hash.
        main(self.queue, generator=self.generator(), env=self.env, overrides=config)
        self.assertEqual(load_queue(self.queue).iloc[0]['Status'], 'CONCLUIDO')

    def test_direct_mode_does_not_require_unused_reference_folder(self):
        self.session.set_mode('direct')
        self.session.add_photos([self.refs/'ok.png'])
        def remove_reference_setting(book):
            sheet=book['Configuracao']
            for row in sheet.iter_rows():
                if row[0].value=='Pasta_Referencias':
                    row[1].value=None
        self.edit_queue(remove_reference_setting)
        self.assertEqual(len(self.session.validate_campaign()['jobs']),8)
