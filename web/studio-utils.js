'use strict';

function runCounts(log) {
  if (!log) return {
    planned: 0,
    started: 0,
    completed: 0,
    errors: 0,
    review: 0,
    waiting: 0,
    remaining: 0
  };
  const events = log.events || [],
    result = log.result || {},
    saved = log.counts || {};
  const ends = new Map(events.filter(e => e.type === 'item_end').map(e => [e.id, e]));
  const starts = new Set(events.filter(e => e.type === 'item_start').map(e => e.id));
  for (const id of ends.keys()) starts.add(id);
  const count = status => [...ends.values()].filter(e => status.includes(e.status)).length;
  const planned = saved.planned ?? result.planned ?? log.planned_items ?? 0;
  const started = starts.size || saved.started || result.started || result.processed || 0;
  const completed = ends.size ? count(['CONCLUIDO', 'SIMULADO']) : saved.completed ?? result
    .success ?? 0;
  const errors = ends.size ? count(['ERRO']) : saved.errors ?? result.errors ?? 0;
  const review = ends.size ? count(['REVISAO']) : saved.review ?? result.review ?? 0;
  return {
    planned,
    started,
    completed,
    errors,
    review,
    waiting: Math.max(0, planned - started),
    remaining: Math.max(0, planned - completed - errors - review)
  };
}

function formatDuration(value) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return '—';
  let n = Math.round(value);
  const h = Math.floor(n / 3600);
  n %= 3600;
  const m = Math.floor(n / 60),
    seconds = n % 60;
  return [h ? h + ' h' : '', m ? m + ' min' : '', seconds || (!h && !m) ? seconds + ' s' : '']
    .filter(Boolean).join(' ');
}

function timeoutGuidance(quality, timeout) {
  return quality === 'max' && Number(timeout) > 0 && Number(timeout) <= 120 ?
    'Qualidade máxima com espera de até 120 segundos pode encerrar a chamada antes da conclusão. Qualidade e dimensões podem influenciar a duração. Para o teste inicial, considere 600 segundos de margem em Opções avançadas. É uma sugestão do Studio, não uma exigência da OpenAI, e não garante conclusão.' :
    '';
}
