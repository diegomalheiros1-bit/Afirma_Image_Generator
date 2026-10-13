"""Opt-in native diagnostic using its own ten-item workbook and fake keys."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time


def prepare_diagnostics(root):
    from openpyxl import Workbook
    from PIL import Image
    from src.studio_session import StudioSession

    root = Path(root)
    queue, reference = root / "diagnostic-campaign.xlsx", root / "diagnostic-reference.png"
    if queue.exists():
        raise ValueError("Use uma nova pasta para o diagnóstico; arquivos existentes são preservados.")
    Image.new("RGB", (32, 32), "purple").save(reference)
    book = Workbook()
    sheet = book.active
    sheet.title = "Fila_Geracao"
    sheet.append(["ID", "Prompt_Padrao", "Prompt_Variacao", "Arquivo_Referencia", "Nome_Saida", "Status", "Tentativas", "Observacao"])
    for i in range(1, 11):
        sheet.append([str(i), "Fotografia de produto.", "Teste isolado.", reference.name,
                      f"produto.{i}", "PENDENTE", 0, ""])
    config = book.create_sheet("Configuracao")
    for row in [("Parametro", "Valor"), ("Pasta_Referencias", str(root)),
                ("Pasta_Resultados", str(root / "images")), ("Limite_Por_Execucao", 1), ("Dry_Run", "SIM")]:
        config.append(row)
    book.save(queue)
    book.close()
    import openai
    def forbidden_client(*args, **kwargs):
        raise AssertionError('Network API client forbidden in diagnostics')
    openai.OpenAI = forbidden_client
    session = StudioSession(root / "diagnostic-settings.json", allow_api=False, env={})
    values = deepcopy(session.preferences)
    values.update(max_jobs=10, max_images=10, safe_mode=False)
    session.set_preferences(values)

    def ready(app):
        window = app.window
        report = {"passed": False, "engine": window.gui.renderer, "layouts": [], "checks": []}
        before = hashlib.sha256(queue.read_bytes()).hexdigest()

        def wait(script, timeout=15):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                result = window.evaluate_js(script)
                if result:
                    return result
                time.sleep(.1)
            raise AssertionError("A interface não alcançou o estado esperado.")

        def click(selector):
            wait(f"(() => {{const e=document.querySelector({json.dumps(selector)});const r=e?.getBoundingClientRect();return r?.width>0&&r?.height>0&&!e.disabled;}})()")
            window.evaluate_js(f"document.querySelector({json.dumps(selector)}).click()")

        def capture(name):
            # Capture the actual WebView2 renderer, including CSS and native DPI.
            # DOM evaluation can finish before WebView2 paints its next frame.
            time.sleep(.2)
            from System import Action
            from System.IO import FileStream, FileMode, FileAccess
            from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
            stream = FileStream(str(root / f"{name}.png"), FileMode.Create, FileAccess.Write)
            value = {}
            try:
                def start():
                    value["task"] = window.native.browser.webview.CoreWebView2.CapturePreviewAsync(
                        CoreWebView2CapturePreviewImageFormat.Png, stream)
                window.native.Invoke(Action(start))
                value["task"].GetAwaiter().GetResult()
            finally:
                stream.Close()

        def layout(name):
            value = window.evaluate_js("""(() => {
              const bad=[...document.querySelectorAll('button,input,select,a')].filter(e=>{
                const r=e.getBoundingClientRect();return r.width&&r.height&&(r.left < -1 || r.right > innerWidth+1);
              }).map(e=>e.id||e.tagName);
              return {width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,
                scrollY:window.scrollY, columns:getComputedStyle(document.querySelector('.grid')).gridTemplateColumns,
                clippedControls:bad};
            })()""")
            assert value["scrollWidth"] <= value["width"] + 1, value
            assert not value["clippedControls"], value
            report["layouts"].append({"name": name, **value})
            capture(name)

        try:
            assert window.gui.renderer == "edgechromium"
            wait("typeof state !== 'undefined' && state !== null")
            from src.app_info import APP_VERSION
            report['app_version'] = window.evaluate_js('state.app_info.version')
            assert report['app_version'] == APP_VERSION
            assert window.evaluate_js('state.app_mode') == 'desktop'
            assert window.evaluate_js("q('history-data').textContent.includes('Nenhuma execução')")
            layout('empty-campaign-history')
            app.pick_files = lambda kind: {"queue": [str(queue)], "photos": [str(reference)], "folder": [str(root / 'images')]}[kind]
            click("#choose-queue")
            wait("state.queue_summary && state.queue_summary.items_with_prompt === 10")
            assert window.evaluate_js("state.queue_summary.execution_images") == 10
            report["checks"].append("workbook-selection")
            window.evaluate_js("document.querySelector('#reference-mode').value='direct';document.querySelector('#reference-mode').dispatchEvent(new Event('change',{bubbles:true}))")
            wait("state.mode === 'direct'")
            click("#add-photos")
            wait("state.photos.length === 1")
            click("#choose-output")
            wait("state.preferences.output_dir.length > 0")
            report["checks"].append("reference-and-output-selection")
            layout("home-default")
            default_width = report["layouts"][-1]["width"]
            window.maximize()
            wait(f"innerWidth > {default_width}")
            assert str(window.native.WindowState) == "Maximized"
            layout("home-maximized")
            window.restore()
            report["checks"].append("native-maximize-and-restore")
            for width, height in [(1024, 768), (850, 640), (700, 600), (520, 500)]:
                window.resize(width, height)
                wait(f"innerWidth <= {width} && innerWidth >= {width - 40}")
                layout(f"home-{width}")
            click("#settings-button")
            preferences_before_tabs = deepcopy(session.preferences)
            click("#settings-tab-about")
            wait("document.querySelector('#settings-tab-about').getAttribute('aria-selected') === 'true'")
            assert window.evaluate_js("document.querySelector('#about-version').textContent") == 'Versão ' + session.state()['app_info']['version']
            assert window.evaluate_js("document.querySelector('#about-model').textContent") == session.preferences['image']['model']
            assert window.evaluate_js("[...document.querySelectorAll('.about-links a')].every(a=>a.target==='_blank'&&a.rel.includes('noopener')&&a.rel.includes('noreferrer'))")
            window.evaluate_js("document.querySelector('.settings-tabs').scrollIntoView({block:'start'})")
            layout("about-small-light")
            window.evaluate_js("document.querySelector('#settings-tab-about').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true}))")
            wait("document.activeElement.id === 'settings-tab-generation'")
            window.evaluate_js("document.querySelector('#timeout').value='123';document.querySelector('#timeout').dispatchEvent(new Event('input',{bubbles:true}))")
            window.evaluate_js("document.querySelector('#model').value='gpt-image-2.5-flare';document.querySelector('#model').dispatchEvent(new Event('input',{bubbles:true}))")
            click("#settings-tab-about")
            assert window.evaluate_js("document.querySelector('#about-model').textContent") == 'gpt-image-2.5-flare'
            time.sleep(1)
            click("#settings-tab-generation")
            assert window.evaluate_js("document.querySelector('#timeout').value") == '123'
            assert window.evaluate_js("document.querySelector('#model').value") == 'gpt-image-2.5-flare'
            assert session.preferences == preferences_before_tabs
            window.evaluate_js("document.querySelector('#model').value='gpt-image-2.5-sunburst';document.querySelector('#model').dispatchEvent(new Event('input',{bubbles:true}))")
            window.evaluate_js("document.querySelector('#timeout').value='120';document.querySelector('#timeout').dispatchEvent(new Event('input',{bubbles:true}))")
            report["checks"].append("about-tab-keyboard-links-and-unsaved-preferences")
            click("#settings details > summary")
            wait("document.querySelector('#settings details').open")
            layout("settings-small")
            # Test error placement with a deliberately incomplete, local-only key.
            window.evaluate_js("document.querySelector('#api-key').value='curta';document.querySelector('#api-key').dispatchEvent(new Event('input',{bubbles:true}))")
            click("#api-key-session")
            wait("document.querySelector('#api-key-error').textContent.length > 0")
            assert session.api_key_status() == "missing"
            report["checks"].append("incomplete-key-error")
            window.evaluate_js("document.querySelector('.credential-card').scrollIntoView({block:'start'})")
            layout("api-key-small-error")
            window.evaluate_js("document.querySelector('#api-key').value='';document.querySelector('#api-key').dispatchEvent(new Event('input',{bubbles:true}))")
            click("#theme-toggle")
            window.evaluate_js("document.querySelector('.credential-card').scrollIntoView({block:'start'})")
            layout("settings-small-dark")
            window.resize(1200, 800)
            wait("innerWidth > 1100")
            layout("settings-wide-dark")
            window.evaluate_js("document.querySelector('.credential-card').scrollIntoView({block:'center'})")
            layout("api-key-wide-dark")
            from src.desktop_app import on_ui_thread
            for factor in (1.25, 1.5):
                on_ui_thread(window, lambda: setattr(window.native.browser.webview, 'ZoomFactor', factor))
                wait(f"innerWidth < {1200 / factor}")
                window.evaluate_js("document.querySelector('.credential-card').scrollIntoView({block:'start'})")
                layout(f"settings-zoom-{int(factor * 100)}")
            on_ui_thread(window, lambda: setattr(window.native.browser.webview, 'ZoomFactor', 1.0))
            wait("innerWidth > 1100")
            report["checks"].append("webview-zoom-125-and-150-percent")
            click("#settings-tab-about")
            window.evaluate_js("document.querySelector('.settings-tabs').scrollIntoView({block:'start'})")
            layout("about-wide-dark")
            window.resize(520, 500)
            wait("innerWidth < 520")
            window.evaluate_js("document.querySelector('.settings-tabs').scrollIntoView({block:'start'})")
            layout("about-small-dark")
            window.evaluate_js("document.querySelector('.about-resources').scrollIntoView({block:'start'})")
            layout("about-links-small-dark")
            window.resize(1200, 800)
            wait("innerWidth > 1100")
            click("#settings-tab-generation")
            click("#back")
            click('#settings-button')
            window.evaluate_js("q('quality').value='max';q('timeout').value=120;q('quality').dispatchEvent(new Event('input',{bubbles:true}));q('timeout').dispatchEvent(new Event('input',{bubbles:true}))")
            wait("!q('timeout-guidance').classList.contains('hidden')")
            assert window.evaluate_js("q('timeout').value") == '120'
            window.evaluate_js("q('timeout-guidance').scrollIntoView({block:'center'})")
            layout('timeout-guidance-wide-dark')
            window.evaluate_js("q('timeout').value=600;q('timeout').dispatchEvent(new Event('input',{bubbles:true}))")
            wait("q('timeout-guidance').classList.contains('hidden')")
            window.evaluate_js("q('timeout').value=120;q('timeout').dispatchEvent(new Event('input',{bubbles:true}))")
            click('#apply')
            wait("state.preferences.image.quality==='max' && state.preferences.timeout===120")
            assert session.preferences['timeout'] == 120
            click('#back')
            report['checks'].append('max-timeout-guidance-nonblocking-no-silent-preference-changes')
            click("#validate")
            wait("document.querySelector('#plan-dialog').open")
            assert ".png" in window.evaluate_js("document.querySelector('#plan-data').textContent")
            report["checks"].append("preflight-normalized-extensions")
            click("#plan-dialog button")
            # UI-only paid-flow fixture: the backend keeps allow_api=False and
            # every real start is intercepted before reaching the server.
            window.evaluate_js("""
              window.diagnosticOriginalApi=api;window.diagnosticPaidCalls=0;window.diagnosticKeyAvailable=false;
              api=async function(path,body){
                if(path==='start'&&body?.real){window.diagnosticPaidCalls++;await new Promise(resolve=>setTimeout(resolve,100));return {};}
                const result=await window.diagnosticOriginalApi(path,body);
                if(path==='state'){result.allow_api=true;result.api_key_status=window.diagnosticKeyAvailable?'session':'missing';}
                return result;
              };refresh();
            """)
            wait("!document.querySelector('#real-start').classList.contains('hidden')")
            window.resize(520, 500)
            wait("innerWidth < 520")
            for button in ('validate', 'start', 'real-start'):
                window.evaluate_js(f"document.querySelector('#{button}').scrollIntoView({{block:'center'}});document.querySelector('#{button}').focus()")
                wait("!document.querySelector('#action-tooltip').classList.contains('hidden')")
                assert window.evaluate_js("document.querySelector('#action-tooltip').textContent.length") > 40
            layout("action-tooltip-small-dark")
            click("#real-start")
            wait("document.querySelector('#generation-dialog').open")
            assert window.evaluate_js("document.querySelector('#generation-confirm').disabled")
            layout("generation-missing-key-dark")
            click("#generation-cancel")
            assert window.evaluate_js("window.diagnosticPaidCalls") == 0
            window.evaluate_js("window.diagnosticKeyAvailable=true;refresh()")
            wait("state.api_key_status === 'session'")
            window.resize(1200, 800)
            wait("innerWidth > 1100")
            click("#real-start")
            wait("document.querySelector('#generation-dialog').open")
            assert window.evaluate_js("document.querySelector('#generation-images').textContent") == 'Até 10'
            assert window.evaluate_js("document.querySelector('#generation-items').textContent") == 'Até 10'
            assert window.evaluate_js("!q('generation-timeout-guidance').classList.contains('hidden') && !q('generation-confirm').disabled")
            layout("generation-wide-dark")
            window.resize(520, 500)
            wait("innerWidth < 520")
            layout("generation-small-dark")
            window.evaluate_js("document.querySelector('#generation-dialog').dispatchEvent(new Event('cancel',{cancelable:true}))")
            wait("!document.querySelector('#generation-dialog').open")
            assert window.evaluate_js("window.diagnosticPaidCalls") == 0
            click("#theme-toggle")
            click("#real-start")
            wait("document.querySelector('#generation-dialog').open")
            layout("generation-small-light")
            # A changed preview requires a fresh confirmation, with zero starts.
            session.preferences['max_images'] = 2
            click("#generation-confirm")
            wait("document.querySelector('#generation-error').textContent.includes('mudou')")
            assert window.evaluate_js("window.diagnosticPaidCalls") == 0
            assert window.evaluate_js("document.querySelector('#generation-images').textContent") == 'Até 2'
            window.evaluate_js("document.querySelector('#generation-confirm').click();document.querySelector('#generation-confirm').click()")
            wait("!document.querySelector('#generation-dialog').open")
            assert window.evaluate_js("window.diagnosticPaidCalls") == 1
            assert not session.active and not session.allow_api
            assert hashlib.sha256(queue.read_bytes()).hexdigest() == before
            session.preferences['max_images'] = 10
            window.evaluate_js("api=window.diagnosticOriginalApi;refresh()")
            wait("state.allow_api === false && state.api_key_status === 'missing'")
            report["checks"].append("paid-dialog-cancel-escape-missing-key-stale-plan-and-single-submit-no-api")
            window.resize(1200, 800)
            wait("innerWidth > 1100")
            click("#start")
            wait("state.result.success === 10")
            assert hashlib.sha256(queue.read_bytes()).hexdigest() == before
            assert not Path(str(queue) + ".state.json").exists()
            report["checks"].append("ten-item-studio-limit-overrides-sheet-one-workbook-unchanged")
            layout("simulation-finished")
            window.evaluate_js("document.querySelector('.run-history').scrollIntoView({block:'start'})")
            layout("log-wide-dark")
            window.resize(520, 500)
            wait("innerWidth < 520")
            window.evaluate_js("document.querySelector('.log-table-wrap').scrollIntoView({block:'center'})")
            layout("log-small-dark")
            assert window.evaluate_js("document.querySelector('.log-table-wrap').scrollWidth > document.querySelector('.log-table-wrap').clientWidth")
            report["checks"].append("log-scroll-contained-in-table")
            # Keep the real gate off for the entire native diagnostic.
            assert session.allow_api is False
            try:
                session.start(real=True)
                raise AssertionError('Real gate must reject starts')
            except ValueError:
                pass
            assert window.evaluate_js("[0,59,60,61,119,120,3600,59.5,null].map(formatDuration).join('|')") == '0 s|59 s|1 min|1 min 1 s|1 min 59 s|2 min|1 h|1 min|—'
            assert window.evaluate_js("[59.4,119.5,3920,undefined,NaN,Infinity,-1].map(formatDuration).join('|')") == '59 s|2 min|1 h 5 min 20 s|—|—|—|—'
            report['checks'].append('shared-duration-boundaries-real-gate-blocked')
            window.evaluate_js("q('persistent-history').scrollIntoView({block:'start'})")
            wait("q('history-data').textContent.includes('Simulado') || q('history-data').textContent.includes('Itens planejados')")
            layout('persistent-history-small')
            click('#selection-preview')
            wait("q('selection-preview-data').textContent.includes('10 itens')")
            window.evaluate_js("q('selection-preview-data').querySelector('details').open=true;q('execution-selection').scrollIntoView({block:'start'})")
            layout('selection-preview-small')
            window.resize(1200, 800)
            wait('innerWidth>1100')
            window.evaluate_js("q('persistent-history').scrollIntoView({block:'start'})")
            layout('persistent-history-wide')
            reopened = StudioSession(root / 'reopened-settings.json', allow_api=False, env={})
            reopened.choose_queue(queue)
            assert len(reopened.history()['runs']) == 1
            run_id = session.run_log['run_id']
            window.evaluate_js("[...q('history-data').querySelectorAll('button')].find(b=>b.textContent==='Retomar lote').click()")
            wait("state.selection_mode==='resume'")
            click('#selection-preview')
            wait("q('selection-preview-data').textContent.includes('10 itens')")
            assert session.selection_mode == 'resume'
            assert session.allow_api is False
            assert window.evaluate_js("[...q('execution-selection').options].map(o=>o.textContent).join('|')")=='Gerar pendentes|Repetir erros|Repetir itens em revisão'
            assert window.evaluate_js("q('execution-choice').classList.contains('hidden') && !q('resume-options').classList.contains('hidden')")
            layout('resume-from-history-small')
            window.evaluate_js("[...q('history-data').querySelectorAll('button')].find(b=>b.textContent==='Retomar lote').scrollIntoView({block:'center'});[...q('history-data').querySelectorAll('button')].find(b=>b.textContent==='Retomar lote').focus()")
            wait("!q('action-tooltip').classList.contains('hidden') && q('action-tooltip').textContent.includes('execução original')")
            layout('history-resume-tooltip')
            click('#resume-exit')
            wait("state.selection_mode==='pending' && !q('execution-choice').classList.contains('hidden')")
            window.evaluate_js("[...q('history-data').querySelectorAll('button')].find(b=>b.textContent==='Retomar lote').click()")
            wait("state.selection_mode==='resume'")
            report['checks'].append('three-actions-resume-only-from-history')
            report['checks'].append('history-reopened-original-selection-preview-api-remains-blocked')
            click('#load-reviews')
            wait("q('review-data').textContent.includes('Nenhum item')")
            window.evaluate_js("q('review-section').scrollIntoView({block:'start'})")
            layout('review-empty-wide')
            # Fictional interrupted batch: six completed, one uncertain, three not started.
            from src.execution_state import Journal, execution_identity, row_fingerprint
            from src.excel_reader import load_queue
            from main import make_job
            book = __import__('openpyxl').load_workbook(queue)
            for i in range(2, 8):
                book['Fila_Geracao'][f'F{i}'] = 'CONCLUIDO'
            book['Fila_Geracao']['F8'] = 'REVISAO'
            book.save(queue)
            book.close()
            config, prefs = session.snapshot()
            row = load_queue(queue, reference_mode='direct').iloc[6]
            job = make_job(row, config, True)
            identity, signature = execution_identity(job, row)
            signature_row = dict(row)
            signature_row['Arquivo_Referencia'] = ''
            Journal(queue).put('7', phase='uncertain', outputs=[str(p) for p in job.saidas],
                execution=identity, execution_fingerprint=signature, row_fingerprint=row_fingerprint(signature_row),
                row_fingerprint_version=2, api_attempts=1,
                error=dict(category='connection', exception_type='APIConnectionError', uncertain=True, request_id='req_fictional'))
            click('#selection-preview')
            wait("q('selection-preview-data').textContent.includes('3 itens')")
            click('#load-reviews')
            wait("q('review-data').textContent.includes('Item #7')")
            window.evaluate_js("q('review-section').scrollIntoView({block:'start'})")
            layout('review-uncertain-wide')
            window.resize(520,500)
            wait('innerWidth<520')
            window.evaluate_js("q('review-section').scrollIntoView({block:'start'})")
            layout('review-uncertain-small')
            window.evaluate_js("[...q('review-data').querySelectorAll('button')].find(b=>b.textContent.includes('Liberar')).click()")
            wait("[...document.querySelectorAll('dialog[open]')].some(d=>d.textContent.includes('outra cobrança'))")
            assert window.evaluate_js("q('action-tooltip').textContent.includes('Fecha a confirmação')")
            layout('review-confirmation-small')
            window.evaluate_js("[...document.querySelector('dialog[open]').querySelectorAll('button')].find(b=>b.textContent==='Cancelar').click()")
            assert load_queue(queue, reference_mode='direct').iloc[6]['Status'] == 'REVISAO'
            assert session.allow_api is False
            report['checks'].append('fictional-six-completed-one-review-three-resume-review-consent-cancel')
            window.evaluate_js("[...q('review-data').querySelectorAll('button')].find(b=>b.textContent.includes('Liberar')).click()")
            wait("[...document.querySelectorAll('dialog[open]')].some(d=>d.textContent.includes('outra cobrança'))")
            window.evaluate_js("[...document.querySelector('dialog[open]').querySelectorAll('button')].find(b=>b.textContent==='Confirmar').click()")
            wait("state.selection_mode==='review' && q('review-feedback').textContent.includes('Item #7 liberado') && q('selection-preview-data').textContent.includes('1 item selecionado')")
            wait("q('review-data').textContent.includes('Liberado para nova tentativa')")
            assert load_queue(queue, reference_mode='direct').iloc[6]['Status'] == 'PENDENTE'
            assert session.allow_api is False and not session.active
            assert session.validate_campaign()['selection']['selected_ids'] == ['7']
            window.evaluate_js("q('review-section').scrollIntoView({block:'start'})")
            layout('review-released-feedback-small')
            window.evaluate_js("q('execution-selection').scrollIntoView({block:'start'})")
            layout('review-retry-selection-small')
            window.resize(1200,800)
            wait('innerWidth>1100')
            window.evaluate_js("q('review-section').scrollIntoView({block:'start'})")
            layout('review-released-feedback-wide')
            report['checks'].append('review-release-feedback-auto-select-only-authorized-no-generation')
            # Regression: an already authorized item can still say REVISAO in Excel.
            book = __import__('openpyxl').load_workbook(queue)
            book['Fila_Geracao']['F8'] = 'REVISAO'
            book.save(queue); book.close()
            click('#selection-preview')
            wait("q('selection-preview-data').textContent.includes('1 item selecionado')")
            assert session.validate_campaign()['selection']['selected_ids'] == ['7']
            window.evaluate_js("api=async function(path,body){if(path==='start'&&body?.real)throw Error('Real API forbidden');const result=await window.diagnosticOriginalApi(path,body);if(path==='state'){result.allow_api=true;result.api_key_status='session';}return result;};refresh()")
            wait('state.allow_api===true')
            click('#real-start')
            wait("q('generation-dialog').open && q('generation-items').textContent==='Até 1'")
            assert window.evaluate_js("q('generation-selected-ids').textContent.includes('7') && !q('generation-confirm').disabled")
            layout('authorized-review-modal-exact-id')
            click('#generation-cancel')
            window.evaluate_js('api=window.diagnosticOriginalApi;refresh()')
            wait('state.allow_api===false')
            assert session.allow_api is False and not session.active
            report['checks'].append('authorized-review-sheet-label-does-not-exclude-modal-id-no-api')
            report["passed"] = True
        except Exception as exc:
            report["error"] = f"{type(exc).__name__}: {exc}"
            report['execution_ui'] = window.evaluate_js("({history:q('history-data')?.textContent,historyOptions:q('history-choice')?.innerHTML,runs:state.history?.runs?.length,selection:q('selection-preview-data')?.textContent,error:q('error')?.textContent})")
            report["ui_failure"] = window.evaluate_js("({dialogOpen:document.querySelector('#generation-dialog')?.open,error:document.querySelector('#generation-error')?.textContent,confirmDisabled:document.querySelector('#generation-confirm')?.disabled,keyStatus:state?.api_key_status,paidCalls:window.diagnosticPaidCalls})")
        finally:
            (root / "diagnostics.json").write_text(json.dumps(report, ensure_ascii=True, indent=2), "utf-8")
            window.destroy()

    return session, ready
