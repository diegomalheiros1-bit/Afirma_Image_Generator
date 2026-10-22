'use strict';
const token = document.querySelector('meta[name=afirma-token]').content,
  q = id => document.getElementById(id);
let state = null,
  preferenceDirty = false,
  photosKey = '',
  foldersKey = '',
  polling = false,
  renderedRunLog = '',
  renderedQueueSummary = '',
  selectionPreview = null,
  selectionContext = null;
async function api(path, data) {
  const response = await fetch('/api/' + path, {
    method: data === undefined ? 'GET' : 'POST',
    headers: {
      'X-Afirma-Token': token,
      'Content-Type': 'application/json'
    },
    body: data === undefined ? undefined : JSON.stringify(data)
  });
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'Falha na comunicação local.');
  return result;
}

function report(error) {
  q('error').textContent = error.message || String(error);
}
async function action(fn) {
  q('error').textContent = '';
  try {
    await fn();
    await refresh();
  } catch (error) {
    report(error);
  }
}

function renderAbout() {
  if (!state) return;
  const info = state.app_info;
  q('about-name').textContent = info?.name || 'Afirma Image Studio';
  q('about-version').textContent = 'Versão ' + (info?.version || '—');
  q('about-developer').textContent = info?.developer || 'Diego Stanisci Malheiros';
  q('about-platform').textContent = state.app_mode === 'desktop' ? 'Aplicativo desktop' :
    'Interface local';
  q('about-model').textContent = q('model').value || state.preferences.image.model;
  if (!q('about-logo').hasAttribute('src')) q('about-logo').src = document.querySelector(
    '.company-logo').src;
}

function selectSettingsTab(name) {
  if (name !== 'generation') {
    resetCredentialDraft();
    if (state) renderCredentialStatus(state.api_key_status, state.active);
  }
  for (const section of ['generation', 'about']) {
    const selected = section === name;
    const tab = q('settings-tab-' + section);
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    q('settings-' + section).classList.toggle('hidden', !selected);
  }
  if (name === 'about') renderAbout();
}
for (const [index, tab] of [...document.querySelectorAll('.settings-tab')].entries()) {
  const names = ['generation', 'about'];
  tab.addEventListener('click', () => selectSettingsTab(names[index]));
  tab.addEventListener('keydown', event => {
    let next;
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') next = 1 - index;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = 1;
    else return;
    event.preventDefault();
    selectSettingsTab(names[next]);
    q('settings-tab-' + names[next]).focus();
  });
}
q('about-back').onclick = () => showSettings(false);

function showSettings(show) {
  if (!show) {
    resetCredentialDraft();
    if (state) renderCredentialStatus(state.api_key_status, state.active);
  }
  for (const id of ['persistent-history', 'review-section']) q(id).classList.toggle('hidden', show);
  q('home').classList.toggle('hidden', show);
  q('settings').classList.toggle('hidden', !show);
  q('settings-button').classList.toggle('hidden', show);
  q('settings-button').setAttribute('aria-expanded', String(show));
  q('toolbar-back').classList.toggle('hidden', !show);
  document.querySelector(show ? '#settings h1' : '#home h1').focus();
}

function fillPreferences(p) {
  q('model').value = p.image.model;
  q('format').value = p.image.output_format;
  q('background').value = p.image.background;
  q('quality').value = p.image.quality;
  const standard = ['auto', '1024x1024', '1536x1024', '1024x1536'];
  q('size').value = standard.includes(p.image.size) ? p.image.size : 'custom';
  if (q('size').value === 'custom') {
    [q('width').value, q('height').value] = p.image.size.split('x');
  }
  q('use-compression').checked = p.image.compression !== null;
  q('compression').value = p.image.compression ?? 50;
  q('timeout').value = p.timeout;
  q('retries').value = p.retries;
  q('max-jobs').value = p.max_jobs;
  q('max-images').value = p.max_images;
  q('safe-mode').checked = p.safe_mode;
  preferencesChanged();
  preferenceDirty = false;
}

function preferencesChanged() {
  q('timeout-equivalence').textContent = q('timeout').value + ' segundos — ' + formatDuration(
    Number(q('timeout').value));
  showTimeoutGuidance('timeout-guidance', q('quality').value, q('timeout').value);
  const jpeg = q('format').value === 'jpeg',
    png = q('format').value === 'png';
  q('background').querySelector('[value=transparent]').disabled = jpeg;
  q('compression-field').classList.toggle('hidden', png && !q('use-compression').checked);
  q('custom-size').classList.toggle('hidden', q('size').value !== 'custom');
  q('compression-value').textContent = q('compression').value;
  const experimental = q('size').value === 'custom' && Number(q('width').value) * Number(q('height')
    .value) > 2560 * 1440;
  q('experimental').textContent = experimental ?
    'Resolução experimental: avalie o resultado antes de ampliar o lote.' : '';
  q('image-error').textContent = jpeg && q('background').value === 'transparent' ?
    'JPEG não suporta transparência. Corrija o formato ou o fundo.' : png && q('use-compression')
    .checked ? 'PNG não aceita compressão configurável. Desmarque a compressão antes de aplicar.' :
    '';
  preferenceDirty = true;
}

function showTimeoutGuidance(id, quality, timeout) {
  const node = q(id),
    text = timeoutGuidance(quality, timeout);
  node.textContent = text;
  node.classList.toggle('hidden', !text);
}

function readPreferences() {
  if (q('image-error').textContent) throw Error(q('image-error').textContent);
  return {
    image: {
      model: q('model').value,
      quality: q('quality').value,
      output_format: q('format').value,
      background: q('background').value,
      size: q('size').value === 'custom' ? q('width').value + 'x' + q('height').value : q('size')
        .value,
      compression: q('use-compression').checked ? Number(q('compression').value) : null
    },
    output_dir: state.preferences.output_dir,
    timeout: Number(q('timeout').value),
    retries: Number(q('retries').value),
    max_jobs: Number(q('max-jobs').value),
    max_images: Number(q('max-images').value),
    safe_mode: q('safe-mode').checked
  };
}
async function applyPreferences(persist = false) {
  await api('preferences', {
    preferences: readPreferences(),
    persist
  });
  preferenceDirty = false;
  q('settings-notice').textContent = persist ? 'Preferências salvas neste computador.' :
    'Preferências aplicadas somente nesta sessão.';
}

function button(text, fn) {
  const b = document.createElement('button');
  b.className = 'secondary campaign-control';
  b.textContent = text;
  b.onclick = () => action(fn);
  return b;
}
async function drawPhotos() {
  const key = JSON.stringify(state.photos);
  if (key === photosKey) return;
  photosKey = key;
  q('photos').replaceChildren();
  for (const [index, p] of state.photos.entries()) {
    const card = document.createElement('div');
    card.className = 'photo';
    const image = document.createElement('img');
    image.alt = p.name;
    const name = document.createElement('div');
    name.className = 'tip';
    name.textContent = p.name;
    name.title = p.path;
    const path = document.createElement('div');
    path.className = 'tip';
    path.textContent = p.path;
    card.append(image, name, path, button('Remover', () => api('photos/remove', {
      index
    })));
    q('photos').append(card);
    try {
      image.src = (await api('thumbnail', {
        index
      })).url;
    } catch (error) {
      path.textContent = 'Arquivo movido, excluído ou inválido: ' + p.path;
      report(error);
    }
  }
}

function drawFolders() {
  const key = JSON.stringify([state.folders, state.default_folder]);
  if (key === foldersKey) return;
  foldersKey = key;
  q('folders').replaceChildren();
  for (const [index, folder] of state.folders.entries()) {
    const card = document.createElement('div');
    card.className = 'reference-card';
    const title = document.createElement('strong');
    title.textContent = folder.alias + (folder.alias === state.default_folder ? ' · padrão' : '');
    const path = document.createElement('p');
    path.className = 'tip';
    path.textContent = folder.path;
    const actions = document.createElement('div');
    actions.className = 'actions';
    actions.append(button('Editar', async () => {
      const alias = prompt('Nome curto da pasta:', folder.alias);
      if (alias === null) return;
      const selection = await api('select', {
        kind: 'folder'
      });
      if (!selection.paths.length) return;
      const folders = structuredClone(state.folders);
      folders[index] = {
        alias,
        path: selection.paths[0]
      };
      await api('folders', {
        folders,
        default: state.default_folder === folder.alias ? alias : state.default_folder
      });
    }), button('Usar como padrão', () => api('folders', {
      folders: state.folders,
      default: folder.alias
    })), button('Remover', async () => {
      const usage = await api('folders/usage', {
        alias: folder.alias
      });
      const message = usage.ids.length ? 'Esta pasta é usada nos itens ' + usage.ids.join(
          ', ') +
        '. As referências ficarão inválidas até você corrigi-las. Remover o cadastro desta sessão?' :
        'Remover o cadastro desta sessão?';
      if (!confirm(message)) return;
      await api('folders', {
        folders: state.folders.filter((_, i) => i !== index),
        default: state.default_folder === folder.alias ? '' : state.default_folder
      });
    }));
    card.append(title, path, actions);
    q('folders').append(card);
  }
  q('legacy-folder').textContent = state.folders.length ?
    'Arquivos com o mesmo nome em pastas diferentes precisam do prefixo, como Produtos::foto.jpg.' :
    'Adicione as pastas que contêm suas referências.';
}

function renderQueueSummary(summary) {
  const signature = JSON.stringify([state.queue, summary, state.selection_mode, selectionPreview]);
  if (signature === renderedQueueSummary) return;
  renderedQueueSummary = signature;
  const box = q('queue-summary');
  box.replaceChildren();
  const heading = textNode('strong', summary ? 'Resumo da planilha' : 'Selecione sua planilha');
  heading.className = 'summary-title';
  box.append(heading);
  if (!summary) {
    box.append(textNode('p', 'Os itens e limites aparecerão aqui.'));
    return;
  }
  const metrics = document.createElement('div');
  metrics.className = 'summary-metrics';
  for (const [value, label] of [
      [summary.pending_items, 'Itens pendentes'],
      [summary.completed_items, 'Concluídos'],
      [summary.review_items, 'Erros / revisão']
    ]) {
    const cell = document.createElement('div');
    cell.className = 'summary-cell';
    cell.append(textNode('strong', String(value)), textNode('span', label));
    metrics.append(cell);
  }
  const current = document.createElement('div');
  current.className = 'summary-cell summary-current';
  const preview = selectionPreview;
  const pending = state.selection_mode === 'pending';
  const count = preview ? preview.selected_ids.length : pending ? summary.execution_items : null;
  const images = preview ? preview.images : summary.execution_images;
  current.append(textNode('strong', count === null ? 'Confira a seleção' : count + ' ' + (count ===
      1 ? 'item' : 'itens') + ' nesta execução'),
    textNode('span', count === null ? 'Veja abaixo quais itens estão aptos.' : images + ' ' + (
      images === 1 ? 'imagem' : 'imagens') + (preview ? (images === 1 ? ' selecionada' : ' selecionadas') :
      (images === 1 ? ' prevista entre os pendentes' : ' previstas entre os pendentes'))));
  metrics.append(current);
  box.append(metrics);
  const note = textNode('p', 'Limite: ' + summary.item_limit + ' itens e ' + summary.image_limit +
    ' imagens por execução.');
  note.className = 'summary-note';
  box.append(note);
  const limits = textNode('button', 'Ajustar limites');
  limits.className = 'secondary campaign-control summary-limits';
  limits.onclick = () => {
    showSettings(true);
    selectSettingsTab('generation');
    q('max-jobs').scrollIntoView({
      block: 'center'
    });
    q('max-jobs').focus();
  };
  box.append(limits);
  if (summary.invalid_quantities) {
    const warning = textNode('p', summary.invalid_quantities +
      ' quantidade(s) inválida(s). Corrija a planilha.');
    warning.className = 'summary-warning';
    box.append(warning);
  }
}

function selectionSignature() {
  return JSON.stringify([campaignContext(), state.queue_summary]);
}

function diagnosticLabel(key) {
  return ({
    category: 'Categoria',
    exception_type: 'Tipo da falha',
    uncertain: 'Resultado incerto',
    request_id: 'Requisição',
    http_status: 'HTTP',
    api_code: 'Código API',
    elapsed_seconds: 'Duração (segundos)',
    timeout_seconds: 'Timeout (segundos)',
    api_attempts: 'Chamadas'
  })[key] || key;
}

function textNode(tag, text) {
  const node = document.createElement(tag);
  if (tag === 'button') {
    node.type = 'button';
    node.className = 'secondary';
  }
  node.textContent = text;
  return node;
}

function renderSelection(data) {
  selectionPreview = data;
  selectionContext = selectionSignature();
  const box = q('selection-preview-data');
  box.replaceChildren(textNode('p', (data.selected_ids.length === 1 ? '1 item selecionado' : data
    .selected_ids.length + ' itens selecionados') + ' · ' + data.images + (data.images === 1 ?
    ' imagem' : ' imagens') + (data.selected_ids.length ? ' · IDs: ' + data.selected_ids.join(
    ', ') : ' · Nenhum item apto; confira os motivos')));
  const table = document.createElement('table');
  for (const item of data.decisions) {
    const row = document.createElement('tr');
    row.append(textNode('td', '#' + item.id), textNode('td', item.reason));
    table.append(row);
  }
  const details = document.createElement('details');
  details.append(textNode('summary', 'Selecionados e excluídos, com motivos'), table);
  box.append(details);
}
async function applySelection() {
  const mode = state?.selection_mode === 'resume' && q('execution-choice').classList.contains(
    'hidden') ? 'resume' : q('execution-selection').value;
  await api('selection', {
    mode,
    run_id: mode === 'resume' ? q('resume-history').value || null : null,
    ids: mode === 'resume' ? q('explicit-batch').value.split(',').map(s => s.trim()).filter(Boolean) : []
  });
}
q('execution-selection').onchange = () => action(async () => {
  q('review-selection-help').classList.toggle('hidden', q('execution-selection').value !==
    'review');
  q('resume-options').classList.toggle('hidden', q('execution-selection').value !== 'resume');
  await applySelection();
});
q('review-view-selection').onclick = () => q('execution-selection').scrollIntoView({
  block: 'start'
});
q('resume-exit').onclick = () => action(async () => {
  await api('selection', {
    mode: 'pending'
  });
  q('selection-preview-data').replaceChildren();
});
q('review-open').onclick = () => {
  q('load-reviews').click();
  q('review-section').scrollIntoView({
    block: 'start'
  });
};
q('resume-history').onchange = () => action(applySelection);
q('explicit-batch').onchange = () => action(applySelection);
q('selection-preview').onclick = () => action(async () => {
  await applySelection();
  state = await api('state');
  const plan = await api('validate', {});
  renderSelection(plan.selection);
});
let historySignature = '';
let historyQueue, historyDetailSignature, historyDetailRun;

function renderPersistentHistory() {
  if (historyQueue !== state.queue) {
    historyQueue = state.queue;
    q('persistent-history').open = false;
    historySignature = null;
    historyDetailSignature = null;
    historyDetailRun = null;
  }
  const data = state.history || {
    runs: [],
    warnings: []
  };
  const signature = JSON.stringify(data);
  if (signature === historySignature) {
    drawHistory();
    return;
  }
  historySignature = signature;
  const choice = q('history-choice'),
    resume = q('resume-history'),
    old = choice.value,
    oldResume = resume.value;
  choice.replaceChildren();
  resume.replaceChildren();
  for (const run of data.runs) {
    const label = (run.started_at ? new Date(run.started_at).toLocaleString('pt-BR') :
      'Data não registrada') + ' · ' + (run.mode === 'real' ? 'Real' : run.mode === 'simulation' ?
      'Simulado' : 'Modo não registrado') + ' · ' + (run.status || 'Estado não registrado');
    for (const select of [choice, resume]) {
      const option = textNode('option', label);
      option.value = run.run_id || '';
      select.append(option);
    }
  }
  if ([...choice.options].some(o => o.value === old)) choice.value = old;
  if ([...resume.options].some(o => o.value === oldResume)) resume.value = oldResume;
  drawHistory();
}

function drawHistory() {
  const box = q('history-data'),
    data = state.history || {
      runs: [],
      warnings: []
    },
    run = data.runs.find(r => (r.run_id || '') === q('history-choice').value),
    signature = JSON.stringify([run, data.warnings]);
  if (signature === historyDetailSignature) {
    const button = box.querySelector('button');
    if (button) button.disabled = state.active;
    return;
  }
  const keepDetails = historyDetailRun === run?.run_id && Boolean(box.querySelector('details')
    ?.open);
  historyDetailSignature = signature;
  historyDetailRun = run?.run_id;
  box.replaceChildren();
  for (const warning of data.warnings) box.append(textNode('p', warning));
  if (!run) {
    box.append(textNode('p', 'Nenhuma execução registrada nesta planilha.'));
    return;
  }
  const c = runCounts(run),
    image = run.settings?.image || {};
  const header = textNode('p', run.status || 'Situação não registrada');
  header.className = 'log-mode';
  box.append(header);
  const cards = document.createElement('div');
  cards.className = 'log-stat-grid';
  for (const [label, value] of [
      ['Itens planejados', run.planned_items ?? '—'],
      ['Imagens planejadas', run.planned_images ?? '—'],
      ['Iniciados', c.started ?? '—'],
      ['Concluídos / simulados', c.completed ?? '—'],
      ['Erros confirmados', c.errors],
      ['Em revisão', c.review ?? '—'],
      ['Não iniciados', c.waiting ?? '—'],
      ['Duração total', formatDuration(run.elapsed_seconds)],
      ['Média dos concluídos', formatDuration(run.mean_completed_seconds)]
    ]) {
    const card = document.createElement('div');
    card.className = 'log-stat';
    card.append(textNode('span', label), textNode('strong', String(value)));
    cards.append(card);
  }
  box.append(cards, textNode('p', 'Modelo: ' + (image.model || '—') + ' · Qualidade: ' + (image
      .quality || '—') + ' · Dimensões: ' + (image.size || '—') + ' · Timeout: ' +
    formatDuration(run.settings?.timeout)));
  if (run.parent_run_id) box.append(textNode('p', 'Retomada da execução: ' + run.parent_run_id));
  if (!run.selected_ids) box.append(textNode('p',
    'Histórico antigo sem seleção original. Informe os IDs explicitamente para concluir este lote.'
  ));
  const details = document.createElement('details');
  details.open = keepDetails;
  details.append(textNode('summary', 'Detalhes dos itens e saídas'));
  for (const e of run.events || []) {
    details.append(textNode('p', '#' + e.id + ' · ' + (e.status || 'Iniciado') + ' · ' +
      formatDuration(e.elapsed_seconds) + ' · ' + (e.message || '')));
    if (e.api_attempts != null || e.request_id || e.diagnostic) details.append(textNode('p',
      'Chamadas: ' + (e.api_attempts ?? '—') + ' · Requisição: ' + (e.request_id || '—') +
      ' · ' + Object.entries(e.diagnostic || {}).map(([k, v]) => k + ': ' + v).join(' · ')));
    for (const path of e.outputs || []) details.append(textNode('p', path));
  }
  box.append(details);
  const button = textNode('button', 'Retomar lote');
  button.className = 'action-generate';
  button.innerHTML =
    '<svg class="button-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 5 10 7-10 7zM19 5v14"/></svg>Retomar lote';
  button.dataset.help =
    'Prepara somente os itens ainda elegíveis desta execução original, respeitando os limites. Não inicia geração. Itens concluídos e revisões sem liberação ficam preservados.';
  button.disabled = state.active;
  button.onclick = () => action(async () => {
    q('resume-history').value = run.run_id || '';
    await api('selection', {
      mode: 'resume',
      run_id: run.run_id || null,
      ids: []
    });
    await refresh();
    q('selection-preview-data').replaceChildren();
    if (run.original_selected_ids || run.selected_ids) {
      const plan = await api('validate', {});
      renderSelection(plan.selection);
    }
    q('resume-options').scrollIntoView({
      block: 'center'
    });
  });
  const selection = run.selection_counts;
  if (selection) box.append(textNode('p', 'Fora da seleção: ' + selection.outside +
    ' · Aguardando limite: ' + selection.limit + ' · Concluídos preservados: ' + selection
    .completed + ' · Erros excluídos: ' + selection.error + ' · Revisão excluída: ' + selection
    .review));
  box.append(button);
}
q('history-choice').onchange = drawHistory;
q('load-reviews').onclick = () => action(async () => {
  const result = await api('reviews', {});
  const box = q('review-data');
  box.replaceChildren();
  if (!result.items.length) box.append(textNode('p', 'Nenhum item em revisão.'));
  for (const item of result.items) {
    const card = document.createElement('div');
    card.className = 'review-card';
    const released = item.released && item.evidence.releasable;
    const badge = textNode('p', released ? 'Liberado para nova tentativa' : item.released ?
      'Liberação exige nova conferência' : 'Aguardando revisão');
    badge.className = 'log-status ' + (released ? 'is-success' : 'is-error');
    card.append(badge);
    card.append(textNode('h3', 'Item #' + item.id), textNode('p', item.evidence.reason),
      textNode('p', 'Data: ' + (item.at ? new Date(item.at).toLocaleString('pt-BR') : '—') +
        ' · Duração: ' + formatDuration(item.elapsed_seconds) + ' · Chamadas: ' + (item
          .calls ?? '—')), textNode('p', Object.entries(item.diagnostic).map(([k, v]) =>
        diagnosticLabel(k) + ': ' + v).join(' · ')));
    for (const output of item.evidence.outputs) card.append(textNode('p', output.path +
      ' · ' + (output.exists ? 'Existe' : 'Ausente')));
    for (const [actionName, label, allowed] of [
        ['recover', 'Recuperar saída comprovada', item.evidence.recoverable],
        ['release', 'Liberar nova tentativa', item.evidence.releasable]
      ]) {
      const button = textNode('button', actionName === 'release' && released ?
        'Já liberado para nova tentativa' : label);
      button.dataset.help = actionName === 'release' ?
        'Abre uma confirmação para autorizar nova tentativa deste item. O reenvio pode gerar outra cobrança. Não inicia a geração; depois use Repetir itens em revisão.' :
        'Recupera somente saídas com hashes e correspondência comprovados. Pede confirmação e não chama a API.';
      button.title = item.released ?
        'Item liberado. Use Repetir itens em revisão e confira a seleção.' : item.evidence
        .reason;
      button.disabled = !allowed || state.active || item.released;
      button.onclick = () => action(async () => {
        const accepted = await reviewConfirmation(actionName, item.id);
        if (!accepted) return;
        await api('review/action', {
          id: item.id,
          action: actionName,
          consent: true
        });
        const feedback = q('review-feedback');
        feedback.textContent = actionName === 'release' ? 'Item #' + item.id +
          ' liberado para nova tentativa. A geração ainda não foi iniciada. A prévia foi atualizada em O que deseja executar.' :
          'Item #' + item.id +
          ' recuperado com saídas comprovadas. Nenhuma chamada à API.';
        feedback.classList.remove('hidden');
        q('review-view-selection').classList.toggle('hidden', actionName !== 'release');
        if (actionName === 'release') {
          q('execution-selection').value = 'review';
          q('resume-options').classList.add('hidden');
          q('review-selection-help').classList.remove('hidden');
          await api('selection', {
            mode: 'review'
          });
          await refresh();
          const plan = await api('validate', {});
          renderSelection(plan.selection);
        }
        await refresh();
        q('load-reviews').click();
      });
      card.append(button);
    }
    box.append(card);
  }
});

function reviewConfirmation(actionName, id) {
  return new Promise(resolve => {
    const dialog = document.createElement('dialog');
    dialog.className = 'generation-dialog';
    dialog.append(textNode('h2', actionName === 'release' ? 'Liberar nova tentativa do item #' +
      id : 'Recuperar item #' + id), textNode('p', actionName === 'release' ?
      'O processamento remoto anterior é incerto. Uma nova tentativa pode gerar outra cobrança. A liberação não inicia a geração; será necessária a confirmação do lote.' :
      'As saídas serão recuperadas somente após conferir novamente hashes, linha e configuração. Nenhuma chamada será feita.'
    ));
    const cancel = textNode('button', 'Cancelar'),
      ok = textNode('button', 'Confirmar');
    let finished = false;
    const done = value => {
      if (finished) return;
      finished = true;
      hideActionHelp();
      dialog.close();
      dialog.remove();
      resolve(value);
    };
    cancel.dataset.help = 'Fecha a confirmação sem liberar nova tentativa ou alterar o item.';
    ok.dataset.help = actionName === 'release' ?
      'Autoriza nova tentativa deste item e registra sua confirmação do risco de cobrança adicional. Não inicia a geração.' :
      'Recupera as saídas locais somente após validar novamente hashes e correspondência. Não chama a API.';
    cancel.onclick = () => done(false);
    ok.onclick = () => done(true);
    dialog.oncancel = e => {
      e.preventDefault();
      done(false);
    };
    dialog.append(cancel, ok);
    document.body.append(dialog);
    dialog.showModal();
    cancel.focus();
  });
}

function renderRunLog(log) {
  const key = JSON.stringify(log);
  if (key === renderedRunLog) return;
  renderedRunLog = key;
  const box = q('run-history');
  box.replaceChildren();
  if (!log) {
    box.textContent = 'Nenhum log detalhado registrado para esta planilha.';
    return;
  }
  const localTime = value => {
    if (!value) return '-';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString('pt-BR', {
      timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
    });
  };
  const header = document.createElement('div');
  header.className = 'log-header';
  const mode = document.createElement('span');
  mode.className = 'log-mode' + (log.mode === 'real' ? ' is-real' : '');
  mode.textContent = log.mode === 'real' ? 'Execu\u00e7\u00e3o real' : 'Simula\u00e7\u00e3o';
  const period = document.createElement('span');
  period.className = 'log-period';
  period.textContent = localTime(log.started_at) + ' | ' + localTime(log.finished_at) +
    ' (fuso local)';
  header.append(mode, period);
  box.append(header);
  const stats = document.createElement('div');
  stats.className = 'log-stat-grid';
  const stat = (label, value, sub) => {
    const card = document.createElement('div');
    card.className = 'log-stat';
    const caption = document.createElement('span');
    caption.textContent = label;
    const number = document.createElement('strong');
    number.textContent = value;
    card.append(caption, number);
    if (sub) {
      const hint = document.createElement('small');
      hint.textContent = sub;
      card.append(hint);
    }
    stats.append(card);
  };
  stat('Dura\u00e7\u00e3o', log.elapsed_seconds == null ? (log.finished_at === null ?
    'Em andamento' : 'N\u00e3o registrada') : formatDuration(log.elapsed_seconds), log.status);
  const counts = runCounts(log);
  stat('Média dos concluídos', formatDuration(log.mean_completed_seconds));
  stat('Erros confirmados', String(counts.errors));
  stat('Planejados', String(counts.planned ?? '—'));
  stat('Iniciados', String(counts.started ?? '—'));
  stat('Concluídos / simulados', String(counts.completed ?? '—'));
  stat('Em revisão', String(counts.review));
  stat('Aguardando início', String(counts.waiting ?? '—'));
  if (log.estimated_cost_usd !== undefined) stat('Custo estimado', 'US$ ' + Number(log
    .estimated_cost_usd).toFixed(6), 'Faturamento n\u00e3o confirmado');
  box.append(stats);
  if (log.usage_totals) {
    const usage = document.createElement('p');
    usage.className = 'log-usage';
    usage.textContent = 'Tokens | Imagem de entrada: ' + log.usage_totals.image_input +
      ' | Texto de entrada: ' + log.usage_totals.text_input + ' | Imagem de sa\u00edda: ' + log
      .usage_totals.image_output;
    box.append(usage);
  }
  if (log.log_error) {
    const warning = document.createElement('p');
    warning.className = 'error';
    warning.textContent = log.log_error;
    box.append(warning);
  }
  const heading = document.createElement('h3');
  heading.className = 'log-events-title';
  heading.textContent = 'Linha do tempo';
  box.append(heading);
  const wrap = document.createElement('div');
  wrap.className = 'log-table-wrap';
  wrap.tabIndex = 0;
  wrap.setAttribute('role', 'region');
  wrap.setAttribute('aria-label', 'Linha do tempo da execução, com rolagem');
  const table = document.createElement('table');
  table.className = 'log-table';
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const title of ['Hor\u00e1rio', 'Item', 'Evento', 'Tempo', 'Detalhes']) {
    const th = document.createElement('th');
    th.scope = 'col';
    th.textContent = title;
    headRow.append(th);
  }
  head.append(headRow);
  table.append(head);
  const body = document.createElement('tbody');
  for (const event of log.events || []) {
    const row = document.createElement('tr');
    const time = document.createElement('td');
    time.className = 'log-time';
    time.textContent = localTime(event.at);
    time.title = event.at || '';
    const id = document.createElement('td');
    const idTag = document.createElement('span');
    idTag.className = 'log-item';
    idTag.textContent = '#' + event.id;
    id.append(idTag);
    const status = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = 'log-status ' + (event.type === 'item_start' ? 'is-start' : event.status ===
      'CONCLUIDO' || event.status === 'SIMULADO' ? 'is-success' : 'is-error');
    badge.textContent = event.type === 'item_start' ? 'Iniciado' : event.status || event.type;
    status.append(badge);
    const duration = document.createElement('td');
    duration.className = 'log-duration';
    duration.textContent = event.elapsed_seconds == null ? '-' : formatDuration(event
      .elapsed_seconds);
    const details = document.createElement('td');
    details.className = 'log-details';
    if (event.message) {
      const message = document.createElement('div');
      message.className = 'log-message';
      message.textContent = event.message;
      details.append(message);
    }
    const files = event.output ? [event.output] : event.outputs || [];
    const meta = [...files.map(path => 'Arquivo: ' + path), event.request_id ? 'Req: ' + event
      .request_id : null, event.api_attempts != null ? 'Chamadas API: ' + event.api_attempts :
      null, ...Object.entries(event.diagnostic || {}).filter(([key]) => ['category',
        'exception_type', 'http_status', 'api_code', 'timeout_seconds'
      ].includes(key)).map(([key, value]) => ({
        category: 'Categoria',
        exception_type: 'Tipo',
        http_status: 'HTTP',
        api_code: 'Código API',
        timeout_seconds: 'Timeout (s)'
      } [key]) + ': ' + value), event.usage ? 'Tokens: ' + [event.usage.image_input, event.usage
        .text_input, event.usage.image_output
      ].join(' / ') : null
    ].filter(Boolean);
    if (meta.length) {
      const metaBox = document.createElement('div');
      metaBox.className = 'log-meta';
      for (const value of meta) {
        const chip = document.createElement('span');
        chip.textContent = value;
        metaBox.append(chip);
      }
      details.append(metaBox);
    }
    row.append(time, id, status, duration, details);
    body.append(row);
  }
  table.append(body);
  wrap.append(table);
  box.append(wrap);
}
let renderedCredentialConnection = '',
  credentialBusy = false,
  credentialEditing = false;

function resetCredentialDraft() {
  q('api-key').value = '';
  q('api-key').type = 'password';
  q('api-key-toggle').textContent = 'Mostrar';
  q('api-key-toggle').setAttribute('aria-label', 'Mostrar texto digitado');
  q('api-key-toggle').setAttribute('aria-pressed', 'false');
  credentialEditing = false;
  q('api-key-error').textContent = '';
}

function renderCredentialStatus(status, active) {
  const configured = status !== 'missing',
    editing = credentialEditing || !configured;
  const messages = {
    saved: 'Origem: salva neste computador.',
    session: 'Origem: somente nesta sessão.',
    external: 'Origem: configuração externa (.env ou ambiente). Gerenciada fora do Studio.',
    missing: 'Insira uma chave para configurar as gerações reais.'
  };
  const connection = state.api_connection || {
    status: 'unverified',
    message: 'Verifique a conexão quando desejar.'
  };
  const blocked = active || credentialBusy || connection.status === 'checking';
  q('credential-title').textContent = configured ? 'Chave configurada' :
    'Nenhuma chave configurada';
  q('api-key-status').textContent = messages[status] || messages.missing;
  q('credential-form').classList.toggle('hidden', !editing);
  q('credential-manage').classList.toggle('hidden', !configured || editing);
  q('credential-replacement').classList.toggle('hidden', !configured);
  q('api-key-cancel').classList.toggle('hidden', !configured);
  q('credential-verification').classList.toggle('hidden', !configured);
  q('api-key-clear').classList.toggle('hidden', !['saved', 'session'].includes(status));
  q('api-key-clear').textContent = status === 'session' ? 'Descartar chave desta sessão' :
    'Remover chave salva';
  for (const id of ['api-key-clear', 'api-key-change', 'api-key', 'api-key-toggle']) q(id)
    .disabled = blocked;
  q('api-key-cancel').disabled = credentialBusy;
  const draft = Boolean(q('api-key').value.trim());
  const renderKey = JSON.stringify(connection);
  if (renderKey !== renderedCredentialConnection) {
    renderedCredentialConnection = renderKey;
    const titles = {
      connected: 'Autenticação verificada',
      disconnected: 'Falha na verificação',
      checking: 'Verificando conexão…',
      unverified: 'Não verificada'
    };
    const icons = {
      connected: '<path d="m5 12 4 4L19 6"/>',
      disconnected: '<path d="m7 7 10 10M17 7 7 17"/>',
      checking: '<path d="M20 12a8 8 0 1 1-8-8"/>',
      unverified: '<circle cx="12" cy="12" r="8"/><path d="M12 8v4m0 4h.01"/>'
    };
    q('api-connection').dataset.status = connection.status;
    q('api-connection-icon').innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + (icons[
      connection.status] || icons.unverified) + '</svg>';
    q('api-connection-title').textContent = titles[connection.status] || titles.unverified;
    q('api-connection-message').textContent = connection.message;
    q('api-connection-time').textContent = connection.checked_at ? 'Última verificação: ' +
      new Date(connection.checked_at).toLocaleString('pt-BR') : '';
  }
  q('api-key-check').disabled = blocked || editing || !configured;
  q('api-key-session').disabled = blocked || !draft;
  q('api-key-save').disabled = blocked || !draft;
  q('api-key-check').textContent = connection.status === 'checking' ? 'Verificando…' :
    'Verificar conexão';
}

function syncFollowHeight() {
  const left = q('campaign-setup'),
    right = q('campaign-follow'),
    table = q('run-history').querySelector('.log-table-wrap');
  if (matchMedia('(min-width:1101px)').matches) {
    const height = left.getBoundingClientRect().height;
    if (!height) return;
    right.style.setProperty('--follow-height', height + 'px');
    if (table) {
      const offset = table.getBoundingClientRect().top - right.getBoundingClientRect().top + right
        .scrollTop;
      const bottom = parseFloat(getComputedStyle(right).paddingBottom) || 0;
      right.style.setProperty('--timeline-height', Math.max(140, Math.min(640, height - offset -
        bottom - 3)) + 'px');
    }
  } else {
    right.style.removeProperty('--follow-height');
    right.style.removeProperty('--timeline-height');
  }
}
const campaignResizeObserver = new ResizeObserver(syncFollowHeight);
campaignResizeObserver.observe(q('campaign-setup'), {
  box: 'border-box'
});
const timelineMutationObserver = new MutationObserver(syncFollowHeight);
timelineMutationObserver.observe(q('run-history'), {
  childList: true,
  subtree: true
});
addEventListener('resize', syncFollowHeight);
syncFollowHeight();
let renderedReviewQueue = '';
let launchBusy = false,
  controlBusy = false;
const actionIcons = {
  play: '<path d="m8 5 11 7-11 7z"/>',
  resume: '<path d="m5 5 10 7-10 7zM19 5v14"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="1"/>'
};

function actionLabel(id, text, icon) {
  const node = q(id);
  if (node.dataset.label === text && node.dataset.icon === icon) return;
  node.dataset.label = text;
  node.dataset.icon = icon;
  node.replaceChildren();
  if (icon) {
    const span = document.createElement('span');
    span.innerHTML = '<svg class="button-icon" viewBox="0 0 24 24" aria-hidden="true">' +
      actionIcons[icon] + '</svg>';
    node.append(span);
  }
  node.append(document.createTextNode(text));
}

function renderHomeConnection() {
  const connection = state.api_connection || {},
    status = state.api_key_status === 'missing' ? 'disconnected' : connection.status ||
    'unverified';
  const label = {
    connected: 'API conectada',
    disconnected: 'API desconectada',
    checking: 'Verificando API…',
    unverified: 'API não verificada'
  } [status] || 'API não verificada';
  const descriptions = {
    connected: 'A conexão foi confirmada por uma verificação ou geração nesta sessão. Não garante disponibilidade contínua, saldo ou acesso a outros modelos.',
    disconnected: state.api_key_status === 'missing' ?
      'Nenhuma chave configurada. Configure uma chave em Opções avançadas.' : connection.message +
      ' Abra as configurações para verificar novamente.',
    checking: connection.message || 'Confirmando a conexão com a OpenAI…',
    unverified: connection.category ? connection.message :
      'Existe uma chave configurada, mas ainda não há verificação válida nesta sessão.'
  };
  const node = q('home-api-status');
  node.dataset.status = status;
  q('home-api-label').textContent = label;
  node.dataset.help = descriptions[status] + (connection.checked_at ? ' Última verificação: ' +
      new Date(connection.checked_at).toLocaleString('pt-BR') + '.' : '') +
    ' Abrir configurações de conexão.';
  node.setAttribute('aria-label', label + '. ' + node.dataset.help);
}

function renderInteraction() {
  const busy = state.active || launchBusy || generationBusy;
  for (const control of document.querySelectorAll('.campaign-control')) control.disabled = busy;
  for (const id of ['start', 'real-start']) q(id).disabled = busy || !state.queue;
  q('execution-lock-notice').classList.toggle('hidden', !state.active);
  q('settings-button').disabled = false;
  for (const id of ['real-start', 'resume', 'generation-confirm']) {
    q(id).classList.remove('primary', 'secondary');
    q(id).classList.add('action-generate');
  }
  q('start').classList.remove('primary');
  q('start').classList.add('action-simulate');
  q('pause').classList.remove('secondary');
  q('pause').classList.add('action-pause');
  q('stop').classList.remove('secondary');
  q('stop').classList.add('action-stop');
  actionLabel('real-start', state.active && state.run_log?.mode === 'real' ? 'Gerando imagens…' :
    'Gerar imagens — API paga', 'play');
  actionLabel('start', state.active && state.run_log?.mode === 'simulation' ?
    'Simulando campanha…' : launchBusy ? 'Iniciando simulação…' : 'Simular campanha', '');
  actionLabel('pause', state.pause_requested && !state.paused ? 'Aguardando pausa…' : 'Pausar',
    'pause');
  actionLabel('resume', 'Retomar', 'resume');
  actionLabel('stop', state.stopping ? 'Interrompendo…' : 'Interromper lote', 'stop');
  const focusedToggle = document.activeElement.id;
  q('pause').classList.toggle('hidden', Boolean(state.paused));
  q('resume').classList.toggle('hidden', !state.paused);
  q('pause').disabled = !state.active || state.pause_requested || state.stopping || controlBusy;
  q('resume').disabled = !state.active || !state.paused || state.stopping || controlBusy;
  q('stop').disabled = !state.active || state.stopping || controlBusy;
  if (!controlBusy && state.active && !state.stopping) {
    if (state.paused && focusedToggle === 'pause') q('resume').focus();
    else if (!state.paused && focusedToggle === 'resume') q('pause').focus();
  }
  q('stop-confirm').disabled = controlBusy || !state.active || state.stopping;
  q('stop-cancel').disabled = controlBusy;
  q('open-output').disabled = !state.preferences.output_dir;
  renderCredentialStatus(state.api_key_status, busy);
  renderHomeConnection();
}
async function sendControl(command) {
  if (controlBusy || !state.active || state.stopping) return;
  controlBusy = true;
  renderInteraction();
  try {
    await api('control', {
      action: command
    });
    if (command === 'stop') q('stop-dialog').close();
    await refresh();
  } catch (error) {
    if (command === 'stop') q('stop-error').textContent = error.message;
    else report(error);
  } finally {
    controlBusy = false;
    renderInteraction();
    if (command === 'pause' && state.paused) q('resume').focus();
    if (command === 'resume') q('pause').focus();
  }
}

function renderState() {
  if (selectionContext && selectionContext !== selectionSignature()) {
    selectionPreview = null;
    selectionContext = null;
    q('selection-preview-data').replaceChildren();
  }
  const resuming = state.selection_mode === 'resume';
  q('execution-choice').classList.toggle('hidden', resuming);
  q('execution-selection').value = resuming ? 'pending' : state.selection_mode || 'pending';
  q('selection-guidance').textContent = ({
    pending: 'Usa os itens PENDENTE. Se já foram gerados, cria novas imagens e preserva as anteriores.',
    errors: 'Tenta novamente os erros aptos. Itens concluídos e resultados incertos ficam preservados.',
    review: 'Repete somente itens em revisão que você liberou explicitamente. A liberação não inicia a geração.',
    resume: 'Apenas os itens elegíveis do lote escolhido no histórico serão incluídos. Nenhum item externo será adicionado.'
  })[state.selection_mode] || '';
  if (resuming) {
    const run = state.history?.runs?.find(r => r.run_id === state.resume_run_id);
    q('resume-origin').textContent = run?.started_at ? 'Lote de ' + new Date(run.started_at)
      .toLocaleString('pt-BR') : 'Lote selecionado no histórico';
    q('legacy-batch-fields').classList.toggle('hidden', Boolean(run?.original_selected_ids || run
      ?.selected_ids));
  }
  q('review-selection-help').classList.toggle('hidden', state.selection_mode !== 'review');
  q('resume-options').classList.toggle('hidden', state.selection_mode !== 'resume');
  if (renderedReviewQueue !== state.queue) {
    renderedReviewQueue = state.queue;
    q('review-feedback').classList.add('hidden');
    q('review-view-selection').classList.add('hidden');
    q('review-data').textContent =
      'Clique em Conferir evidências para revisar os itens desta planilha.';
  }
  renderPersistentHistory();
  renderAbout();
  q('footer-status').textContent = 'Afirma Image Studio · ' + (state.app_mode === 'desktop' ?
    'Aplicativo desktop' : 'Processamento local') + ' · ' + (state.allow_api ?
    'Geração paga exige confirmação' : 'API real bloqueada');
  q('progress-empty').classList.toggle('hidden', state.active || state.items.length > 0);
  q('progress-empty').textContent = state.queue_summary && state.queue_summary.completed_items ?
    'Nenhuma execu\u00e7\u00e3o ativa nesta sess\u00e3o. Esta planilha tem ' + state.queue_summary
    .completed_items + (state.queue_summary.completed_items === 1 ? ' item conclu\u00eddo.' :
      ' itens conclu\u00eddos.') + ' Veja o hist\u00f3rico abaixo.' :
    'O acompanhamento aparece aqui quando voc\u00ea iniciar uma campanha.';
  const img = state.preferences.image;
  const qualityNames = {
    auto: 'automática',
    low: 'baixa',
    medium: 'média',
    high: 'alta',
    xhigh: 'muito alta',
    max: 'máxima'
  };
  q('config-summary').textContent = img.output_format.toUpperCase() + ' · Qualidade ' +
    qualityNames[img.quality] + ' · ' + (img.size === 'auto' ? 'Resolução automática' : img.size
      .replace('x', ' × ') + ' px');
  q('choose-queue').textContent = state.queue || 'Selecionar planilha Excel';
  renderQueueSummary(state.queue_summary);
  renderRunLog(state.run_log);
  renderCredentialStatus(state.api_key_status, state.active);
  q('reference-mode').value = state.mode;
  q('spreadsheet-references').classList.toggle('hidden', state.mode !== 'spreadsheet');
  q('direct-references').classList.toggle('hidden', state.mode !== 'direct');
  q('photo-count').textContent = state.photos.length + ' de 16 fotos';
  q('choose-output').textContent = state.preferences.output_dir || 'Selecionar pasta de saída';
  q('run-status').textContent = state.status;
  q('run-error').textContent = state.error;
  const counts = runCounts(state.run_log);
  q('success').textContent = counts.completed;
  q('errors').textContent = counts.errors;
  q('success-label').textContent = state.run_log?.mode === 'simulation' ? 'Simulados' :
    'Concluídos';
  q('remaining-count').textContent = counts.remaining;
  q('planned-count').textContent = counts.planned;
  q('started-count').textContent = counts.started;
  q('waiting-count').textContent = counts.waiting;
  q('review-count').textContent = counts.review;
  q('review-notice').classList.toggle('hidden', !counts.review);
  q('review-notice').textContent = counts.review + ' ' + (counts.review === 1 ? 'item em revisão.' :
    'itens em revisão.') + ' Confira as evidências antes de tentar novamente.';
  const processed = counts.completed + counts.errors + counts.review;
  q('progress-count').textContent = processed + ' / ' + counts.planned;
  const percent = counts.planned ? Math.min(100, 100 * processed / counts.planned) : 0;
  q('bar').style.width = percent + '%';
  q('bar').parentElement.setAttribute('aria-valuenow', String(Math.round(percent)));
  q('items').replaceChildren();
  for (const item of state.items) {
    const row = document.createElement('tr');
    for (const text of [item.id, item.status, item.message]) {
      const cell = document.createElement('td');
      cell.textContent = text;
      row.append(cell);
    }
    q('items').append(row);
  }
  q('pause').disabled = !state.active || state.paused || state.stopping;
  q('resume').disabled = !state.active || !state.paused || state.stopping;
  q('stop').disabled = !state.active || state.stopping;
  q('real-start').classList.toggle('hidden', !state.allow_api);
  drawFolders();
  for (const control of document.querySelectorAll('.campaign-control')) control.disabled = state
    .active;
  q('settings-button').disabled = false;
  q('start').disabled = state.active || !state.queue;
  q('real-start').disabled = state.active || !state.queue;
  renderInteraction();
}
async function refresh() {
  if (polling) return;
  polling = true;
  try {
    state = await api('state');
    if (!preferenceDirty) fillPreferences(state.preferences);
    renderState();
    if (state.current_item_seconds !== null) q('run-status').textContent = state.status + (state
        .run_log?.mode === 'real' ? ' · Chamada em andamento: ' : ' · Item em andamento: ') +
      formatDuration(state.current_item_seconds);
    await drawPhotos();
    for (const control of document.querySelectorAll('.campaign-control')) control.disabled = state
      .active;
    renderInteraction();
  } finally {
    polling = false;
  }
}
q('toolbar-back').onclick = () => showSettings(false);
q('settings-button').onclick = () => showSettings(true);
q('back').onclick = () => showSettings(false);
for (const el of q('settings').querySelectorAll('input:not(#api-key),select')) el.addEventListener(
  'input', preferencesChanged);
q('apply').onclick = () => action(() => applyPreferences(false));
q('save-settings').onclick = () => action(() => applyPreferences(true));
async function saveApiKey(persist) {
  const field = q('api-key');
  try {
    await api('credential', {
      key: field.value,
      persist
    });
  } finally {
    field.value = '';
    field.type = 'password';
    q('api-key-toggle').textContent = 'Mostrar';
    q('api-key-toggle').setAttribute('aria-label', 'Mostrar texto digitado');
    q('api-key-toggle').setAttribute('aria-pressed', 'false');
  }
  resetCredentialDraft();
  q('credential-notice').textContent = persist ?
    'Chave protegida salva. Verifique a conexão quando desejar.' :
    'Chave configurada nesta sessão. Verifique a conexão quando desejar.';
}
async function credentialAction(fn) {
  if (credentialBusy) return;
  credentialBusy = true;
  q('api-key-error').textContent = '';
  renderCredentialStatus(state.api_key_status, state.active);
  try {
    await fn();
    await refresh();
    if (!credentialEditing && state.api_key_status !== 'missing' && state.api_connection
      .status !== 'checking') q('api-key-change').focus();
  } catch (error) {
    q('api-key-error').textContent = error.message || 'Não foi possível concluir a operação.';
  } finally {
    credentialBusy = false;
    renderCredentialStatus(state.api_key_status, state.active);
  }
}
q('api-key-change').onclick = () => {
  resetCredentialDraft();
  credentialEditing = true;
  q('credential-notice').textContent = '';
  renderCredentialStatus(state.api_key_status, state.active);
  q('api-key').focus();
};
q('api-key-cancel').onclick = () => {
  resetCredentialDraft();
  renderCredentialStatus(state.api_key_status, state.active);
  q('api-key-change').focus();
};
q('api-key-check').onclick = () => credentialAction(() => api('credential/check', {}));
q('api-key').addEventListener('input', () => {
  q('api-key-error').textContent = '';
  if (state) renderCredentialStatus(state.api_key_status, state.active);
});
q('api-key-session').onclick = () => credentialAction(() => saveApiKey(false));
q('api-key-save').onclick = () => credentialAction(() => saveApiKey(true));
q('api-key-clear').onclick = () => credentialAction(async () => {
  const source = state.api_key_status;
  const description = source === 'session' ? 'Descartar apenas a chave desta sessão?' :
    'Remover apenas a chave protegida salva pelo aplicativo?';
  if (!confirm(description + ' Uma chave de outra origem poderá passar a ser usada.')) return;
  await api('credential/clear', {
    source
  });
  resetCredentialDraft();
  await refresh();
  const origins = {
    saved: 'a chave salva neste computador',
    session: 'a chave desta sessão',
    external: 'a configuração externa'
  };
  q('credential-notice').textContent = state.api_key_status === 'missing' ?
    'Chave removida. Nenhuma chave configurada.' : 'Chave removida. Agora está em uso ' +
    origins[state.api_key_status] + '.';
});
q('api-key-toggle').onclick = () => {
  const field = q('api-key');
  const show = field.type === 'password';
  field.type = show ? 'text' : 'password';
  q('api-key-toggle').textContent = show ? 'Ocultar' : 'Mostrar';
  q('api-key-toggle').setAttribute('aria-label', show ? 'Ocultar texto digitado' :
    'Mostrar texto digitado');
  q('api-key-toggle').setAttribute('aria-pressed', String(show));
};
document.querySelector('#settings-generation details').addEventListener('toggle', event => {
  if (!event.target.open) {
    resetCredentialDraft();
    if (state) renderCredentialStatus(state.api_key_status, state.active);
  }
});
window.addEventListener('pagehide', resetCredentialDraft);
q('choose-queue').onclick = () => action(() => api('select', {
  kind: 'queue'
}));
q('reference-mode').onchange = () => action(() => api('mode', {
  mode: q('reference-mode').value
}));
q('add-photos').onclick = () => action(() => api('select', {
  kind: 'photos'
}));
q('add-folder').onclick = () => action(async () => {
  const selected = await api('select', {
    kind: 'folder'
  });
  if (!selected.paths.length) return;
  const alias = prompt('Nome curto da pasta (ex.: Produtos):');
  if (alias === null) return;
  await api('folders', {
    folders: [...state.folders, {
      alias,
      path: selected.paths[0]
    }],
    default: state.default_folder
  });
});
q('save-folders').onclick = () => action(async () => {
  if (confirm(
      'Salvar Pastas_Referencias e a pasta padrão na planilha selecionada? Esta é uma gravação explícita no Excel.'
    )) {
    await api('folders/save', {});
    q('error').textContent = 'Pastas salvas na planilha.';
  }
});
q('choose-output').onclick = () => action(async () => {
  const selected = await api('select', {
    kind: 'folder'
  });
  if (selected.paths.length) {
    const preferences = readPreferences();
    preferences.output_dir = selected.paths[0];
    await api('preferences', {
      preferences
    });
    preferenceDirty = false;
  }
});
q('start').onclick = async () => {
  if (launchBusy || state.active) return;
  launchBusy = true;
  renderInteraction();
  try {
    await action(async () => {
      if (preferenceDirty) await applyPreferences();
      await api('start', {
        real: false
      });
    });
  } finally {
    launchBusy = false;
    renderInteraction();
  }
};
q('real-start').onclick = () => {
  if (!launchBusy && !state.active) action(openGenerationDialog);
};
q('pause').onclick = () => sendControl('pause');
q('resume').onclick = () => sendControl('resume');
q('stop').onclick = () => {
  if (!state.active || state.stopping || controlBusy) return;
  q('stop-error').textContent = '';
  q('stop-dialog').showModal();
  q('stop-cancel').focus();
};
q('stop-cancel').onclick = () => {
  q('stop-dialog').close();
  q('stop').focus();
};
q('stop-confirm').onclick = () => sendControl('stop');
q('stop-dialog').addEventListener('cancel', event => {
  if (controlBusy) event.preventDefault();
});
q('open-output').onclick = () => action(() => api('output/open', {}));
q('home-api-status').onclick = () => {
  selectSettingsTab('generation');
  showSettings(true);
  document.querySelector('#settings-generation details').open = true;
  const target = state.api_key_status === 'missing' ? q('api-key') : q('credential-verification');
  target.tabIndex = target.id === 'api-key' ? 0 : -1;
  target.focus();
  target.scrollIntoView({
    block: 'center',
    behavior: 'auto'
  });
};

function themeLabel() {
  const dark = document.documentElement.dataset.theme === 'dark';
  q('theme-toggle').textContent = dark ? '☀ Tema claro' : '☾ Tema escuro';
  q('theme-toggle').setAttribute('aria-pressed', String(dark));
  q('theme-toggle').setAttribute('aria-label', dark ? 'Ativar tema claro' : 'Ativar tema escuro');
}
q('theme-toggle').onclick = () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem('afirma-theme', theme);
  } catch (e) {}
  themeLabel();
};
themeLabel();

const actionHelp = {
  'open-output': 'Abre a pasta de resultados configurada no gerenciador de arquivos. Não altera o destino nem interrompe a campanha.',
  'stop-confirm': 'Impede novos itens e aguarda o item atual e o salvamento. Não confirma cancelamento remoto.',
  'stop-cancel': 'Fecha a confirmação e mantém o lote em execução.',
  'api-key-change': 'Abre um campo vazio para substituir a chave. A chave atual continua em uso até a confirmação.',
  'api-key-session': 'Usa o novo valor apenas nesta sessão. Não salva no computador nem verifica a conexão.',
  'api-key-save': 'Protege a nova chave com o usuário do sistema. Não inicia verificação nem geração.',
  'api-key-cancel': 'Descarta o texto digitado e mantém a chave atual.',
  'api-key-check': 'Verifica a autenticação da chave configurada. Não consulta saldo nem gera imagens.',
  'api-key-clear': 'Remove somente a origem indicada no botão. Outra chave configurada pode passar a ser usada.',
  start: 'Simula somente os IDs da seleção escolhida. Mostra o andamento, sem chamar a API, criar imagens finais ou alterar os estados da planilha.',
  'real-start': 'Mostra os IDs e configurações para sua confirmação. Só depois de Confirmar e gerar imagens inicia a API paga. Pode consumir créditos.',
  'selection-preview': 'Mostra os IDs que entrarão nesta execução e os motivos de exclusão, já respeitando os limites. Não gera imagens nem altera a planilha.',
  'review-open': 'Abre as evidências dos itens em revisão para recuperar saídas comprovadas ou autorizar uma nova tentativa. Não gera imagens.',
  'load-reviews': 'Confere assinaturas, referências e saídas locais. Não consulta a API nem consome créditos.',
  'review-view-selection': 'Volta à prévia dos IDs liberados para nova tentativa. Confira-os antes de confirmar a geração paga.',
  'resume-exit': 'Sai da retomada deste lote e volta à escolha entre pendentes, erros e revisões. Não inicia geração.',
  'pause': 'Solicita pausa após o item atual. A chamada já iniciada pode continuar e consumir créditos.',
  'resume': 'Continua a execução pausada a partir do próximo item. Na geração real, novas chamadas podem consumir créditos.',
  'stop': 'Impede novos itens e aguarda a chamada atual terminar ou atingir o timeout, salvando o resultado. Não confirma cancelamento remoto.',
  'generation-configure': 'Abre a configuração ou a revisão necessária para resolver o impedimento mostrado. Não inicia geração.',
  'generation-cancel': 'Fecha esta confirmação sem iniciar a geração.',
  'generation-confirm': 'Inicia os IDs exibidos neste resumo usando sua chave OpenAI. Esta ação pode consumir créditos ou gerar cobrança.'
};
let activeActionHelp = null;

function hideActionHelp() {
  activeActionHelp = null;
  const tooltip = q('action-tooltip');
  if (tooltip) {
    tooltip.classList.add('hidden');
    document.body.append(tooltip);
  }
}

function positionActionHelp() {
  if (!activeActionHelp) return;
  const tooltip = q('action-tooltip'),
    rect = activeActionHelp.getBoundingClientRect(),
    box = tooltip.getBoundingClientRect();
  if (rect.bottom < 0 || rect.top > innerHeight) {
    hideActionHelp();
    return;
  }
  tooltip.style.left = Math.max(12, Math.min(rect.left, innerWidth - box.width - 12)) + 'px';
  tooltip.style.top = Math.max(12, rect.bottom + box.height + 20 <= innerHeight ? rect.bottom + 8 :
    rect.top - box.height - 8) + 'px';
}

function showButtonHelp(button) {
  const message = button?.dataset.help || actionHelp[button?.id];
  if (!message || button.disabled) return;
  activeActionHelp = button;
  button.setAttribute('aria-describedby', 'action-tooltip');
  const tooltip = q('action-tooltip');
  const dialog = button.closest('dialog[open]');
  (dialog || document.body).append(tooltip);
  tooltip.textContent = message;
  tooltip.classList.remove('hidden');
  positionActionHelp();
}
document.addEventListener('mouseover', event => {
  const button = event.target.closest('button');
  if (button && !button.contains(event.relatedTarget)) showButtonHelp(button);
});
document.addEventListener('focusin', event => showButtonHelp(event.target.closest('button')));
document.addEventListener('mouseout', event => {
  if (activeActionHelp && !activeActionHelp.contains(event.relatedTarget) && document
    .activeElement !== activeActionHelp) hideActionHelp();
});
document.addEventListener('focusout', hideActionHelp);
document.addEventListener('click', hideActionHelp);
addEventListener('resize', positionActionHelp);
addEventListener('scroll', () => {
  if (activeActionHelp && document.activeElement === activeActionHelp) positionActionHelp();
  else hideActionHelp();
}, true);
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') hideActionHelp();
});
let generationPlan = null,
  generationContext = '',
  generationOpening = false,
  generationBusy = false;

function campaignContext() {
  return JSON.stringify({
    queue: state.queue,
    preferences: state.preferences,
    mode: state.mode,
    photos: state.photos,
    folders: state.folders,
    default_folder: state.default_folder,
    selection_mode: state.selection_mode,
    resume_run_id: state.resume_run_id
  });
}

function renderGenerationDialog(plan) {
  actionLabel('generation-confirm', 'Confirmar e gerar imagens', 'play');
  showTimeoutGuidance('generation-timeout-guidance', plan.settings.quality, state.preferences
    .timeout);
  const preview = plan.execution_preview,
    img = plan.settings,
    qualityNames = {
      auto: 'automática',
      low: 'baixa',
      medium: 'média',
      high: 'alta',
      xhigh: 'muito alta',
      max: 'máxima'
    };
  q('generation-items').textContent = 'Até ' + preview.items;
  q('generation-images').textContent = 'Até ' + preview.images;
  q('generation-queue').textContent = state.queue.split(/[\\/]/).pop();
  q('generation-model').textContent = img.model;
  q('generation-settings').textContent = img.output_format.toUpperCase() + ' · Qualidade ' +
    qualityNames[img.quality] + ' · ' + (img.size === 'auto' ? 'Resolução automática' : img.size
      .replace('x', ' × ') + ' px');
  q('generation-output').textContent = preview.output_dir;
  q('generation-selected-ids').textContent = 'IDs selecionados: ' + (plan.selection?.selected_ids
    ?.join(', ') || 'Nenhum');
  const regenerated = (plan.selection?.decisions || []).filter(d => d.category === 'selected' && d
    .regeneration).map(d => d.id);
  q('generation-regeneration').classList.toggle('hidden', !regenerated.length);
  q('generation-regeneration').textContent = regenerated.length ? 'Gerar novamente os IDs ' +
    regenerated.join(', ') +
    ': estão PENDENTE na planilha. As imagens anteriores serão preservadas. Esta é uma nova geração paga.' :
    '';
  const hasDeferred = plan.selection?.decisions?.some(d => d.category === 'limit');
  const emptyReason = hasDeferred ?
    'Os itens elegíveis excedem os limites desta execução. Confira os limites.' : state
    .selection_mode === 'review' ?
    'Nenhuma revisão liberada está apta nesta configuração. Confira as evidências, as referências e as saídas em Itens em revisão.' :
    'Nenhum item elegível para a seleção escolhida. Confira os motivos em Conferir seleção.';
  const problem = state.api_key_status === 'missing' ?
    'Configure sua chave OpenAI em Configurações → Geração → Opções avançadas antes de gerar.' : !
    preview.safe_mode_compatible ?
    'O modo seguro exige limites de até 1 item e 1 imagem, nas configurações. Ajuste os limites ou desative o modo seguro.' :
    !preview.items ? emptyReason : '';
  q('generation-error').textContent = problem;
  q('generation-confirm').disabled = Boolean(problem);
  q('generation-configure').classList.toggle('hidden', !problem);
  q('generation-configure').textContent = problem && state.api_key_status !== 'missing' && preview
    .safe_mode_compatible && !hasDeferred && !preview.items ? 'Revisar seleção' :
    'Configurar chave ou limites';
}
async function openGenerationDialog() {
  if (generationOpening || generationBusy || q('generation-dialog').open) return;
  generationOpening = true;
  try {
    if (preferenceDirty) await applyPreferences();
    const plan = await api('validate', {});
    state = await api('state');
    if (!state.allow_api || state.active) throw Error(
      'A geração real não está disponível nesta sessão.');
    generationPlan = plan;
    generationContext = campaignContext();
    renderGenerationDialog(plan);
    hideActionHelp();
    q('generation-dialog').showModal();
    q('generation-title').focus();
    q('generation-dialog').scrollTop = 0;
  } finally {
    generationOpening = false;
  }
}

function closeGenerationDialog() {
  if (generationBusy) return;
  q('generation-dialog').close();
  generationPlan = null;
  q('real-start').focus();
}
q('generation-cancel').onclick = closeGenerationDialog;
q('generation-dialog').addEventListener('cancel', event => {
  event.preventDefault();
  closeGenerationDialog();
});
q('generation-configure').onclick = () => {
  const review = q('generation-configure').textContent === 'Revisar seleção';
  closeGenerationDialog();
  if (review) {
    showSettings(false);
    q('review-open').click();
    return;
  }
  selectSettingsTab('generation');
  showSettings(true);
  document.querySelector('#settings-generation details').open = true;
  (state.api_key_status === 'missing' ? q('api-key') : q('api-key-change')).focus();
};
q('generation-confirm').onclick = async () => {
  if (generationBusy || !generationPlan || !q('generation-dialog').open || q(
      'generation-confirm').disabled) return;
  generationBusy = true;
  q('generation-confirm').disabled = true;
  q('generation-cancel').disabled = true;
  q('generation-configure').disabled = true;
  actionLabel('generation-confirm', 'Iniciando…', 'play');
  q('generation-error').textContent = '';
  try {
    const currentState = await api('state');
    state = currentState;
    const currentPlan = await api('validate', {});
    if (campaignContext() !== generationContext || JSON.stringify(currentPlan) !== JSON
      .stringify(generationPlan)) {
      generationPlan = currentPlan;
      generationContext = campaignContext();
      renderGenerationDialog(currentPlan);
      throw Error(
        'A campanha mudou desde a conferência. Revise o resumo atualizado e confirme novamente.'
      );
    }
    if (!state.allow_api || state.active || state.api_key_status === 'missing') throw Error(
      'Confira a chave e se já existe uma campanha em andamento antes de gerar.');
    await api('start', {
      real: true
    });
    q('generation-dialog').close();
    generationPlan = null;
    await refresh();
  } catch (error) {
    q('generation-error').textContent = error.message || 'Não foi possível iniciar a geração.';
  } finally {
    generationBusy = false;
    actionLabel('generation-confirm', 'Confirmar e gerar imagens', 'play');
    q('generation-cancel').disabled = false;
    q('generation-configure').disabled = false;
    if (generationPlan) q('generation-confirm').disabled = state.active || state
      .api_key_status === 'missing' || !generationPlan.execution_preview.items || !
      generationPlan.execution_preview.safe_mode_compatible;
  }
};

const fieldHelp = {
  'choose-queue': 'Selecione a planilha Excel da campanha. O resumo mostra os itens e imagens dessa planilha sem iniciar a gera\u00e7\u00e3o.',
  'reference-mode': 'Pela planilha, cada item usa suas pr\u00f3prias fotos. No software, as fotos escolhidas valem para todos os itens.',
  'choose-output': 'Escolha onde salvar as novas imagens. Selecione uma pasta antes de conferir ou gerar.',
  'model': 'Escolhe o modelo de gera\u00e7\u00e3o. Modelo e configura\u00e7\u00f5es influenciam resultado, tempo e custo.',
  'format': 'Define o tipo de arquivo gerado: PNG, JPEG ou WebP. A extensão é completada ou ajustada automaticamente; não é necessário digitá-la em Nome_Saida na planilha.',
  'background': 'Fundo opaco, transparente quando suportado, ou escolha autom\u00e1tica do modelo.',
  'quality': 'Qualidade maior pode exigir mais tempo e aumentar o custo da API.',
  'size': 'Escolha uma resolu\u00e7\u00e3o pronta ou informe largura e altura personalizadas.',
  'width': 'Largura em pixels. Use m\u00faltiplos de 16 dentro dos limites indicados.',
  'height': 'Altura em pixels. Use m\u00faltiplos de 16 dentro dos limites indicados.',
  'max-jobs': 'Limite de linhas processadas por execu\u00e7\u00e3o. No Studio, prevalece sobre Limite_Por_Execucao do Excel, sem editar a planilha.',
  'max-images': 'Limite total de imagens na pr\u00f3xima execu\u00e7\u00e3o; pode ser diferente do n\u00famero de itens.',
  'timeout': 'Tempo m\u00e1ximo de espera por chamada de gera\u00e7\u00e3o, em segundos.',
  'retries': 'N\u00famero de novas tentativas autom\u00e1ticas para falhas transit\u00f3rias.',
  'compression': 'Ajusta o tamanho do arquivo JPEG ou WebP; n\u00e3o muda a qualidade usada para gerar a imagem.',
  'api-key': 'Cole sua chave OpenAI. Use somente nesta sess\u00e3o ou salve protegida para este usu\u00e1rio do sistema.'
};

function installFieldHelp() {
  for (const [id, message] of Object.entries(fieldHelp)) {
    const label = document.querySelector('label[for="' + id + '"]');
    if (!label) continue;
    const row = document.createElement('span');
    row.className = 'field-label-row';
    label.before(row);
    row.append(label);
    const wrap = document.createElement('span');
    wrap.className = 'field-help';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'field-help-button';
    button.textContent = '?';
    button.setAttribute('aria-label', 'Ajuda sobre ' + label.textContent);
    button.setAttribute('aria-expanded', 'false');
    const tooltip = document.createElement('span');
    tooltip.className = 'field-help-popover';
    tooltip.id = 'help-' + id;
    tooltip.setAttribute('role', 'tooltip');
    tooltip.textContent = message;
    button.setAttribute('aria-describedby', tooltip.id);
    button.onclick = () => {
      const open = !wrap.classList.contains('help-open');
      for (const other of document.querySelectorAll('.field-help.help-open')) {
        other.classList.remove('help-open');
        other.querySelector('button').setAttribute('aria-expanded', 'false');
      }
      wrap.classList.toggle('help-open', open);
      button.setAttribute('aria-expanded', String(open));
    };
    wrap.append(button, tooltip);
    row.append(wrap);
  }
  document.addEventListener('click', event => {
    if (event.target.closest('.field-help')) return;
    for (const wrap of document.querySelectorAll('.field-help.help-open')) {
      wrap.classList.remove('help-open');
      wrap.querySelector('button').setAttribute('aria-expanded', 'false');
    }
  });
}
installFieldHelp();
refresh().catch(report);
setInterval(() => refresh().catch(report), 700);
