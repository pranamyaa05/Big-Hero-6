/* Connection to the ReForm3D backend (the AI design server).
   Backend address, first found wins:
     1. ?api=https://host in the page address (remembered on this browser; ?api=off forgets it)
     2. window.REFORM3D_API set before this script runs, or <meta name="reform3d-api" content="https://host">
   With no address the page stays a demo: the form explains that nothing was sent. */
import './reform3d-client.js';
import { initHistory } from './history.js';
import { t, stepText, initI18n, onLang, applyI18n, aiLanguage } from './i18n.js';
import { initSpeech, attachMic } from './speech.js';

const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const list = (title, items, cls = '') => {
  items = (items || []).filter(Boolean);
  return items.length ? `<div class="rf-sec ${cls}"><h3>${esc(title)}</h3><ul>${items.map(t => `<li>${esc(t)}</li>`).join('')}</ul></div>` : '';
};

export function backendUrl() {
  let api = '';
  try {
    const q = new URLSearchParams(location.search).get('api');
    if (q === 'off') localStorage.removeItem('rf-api');
    else if (q) localStorage.setItem('rf-api', q);
    if (q !== 'off') api = q || localStorage.getItem('rf-api') || '';
  } catch (e) { /* storage blocked: fall through */ }
  if (!api) api = window.REFORM3D_API || ($('meta[name="reform3d-api"]') || {}).content || '';
  return api.replace(/\/$/, '');
}

const STAGES = { asking: 'stage.asking', queued: 'stage.queued', planning: 'stage.planning', designing: 'stage.designing', building: 'stage.building' };

/* The printer in the request panel is its own small page (printer.html, next to this one). It loads when the panel is near the screen, and only
   if the file is there; without it the page keeps the bottle on the stage. */
function initPrinter() {
  const frame = $('#rfPrinter'), repair = $('#repair');
  if (!frame || !repair) return;
  const accent = () => (getComputedStyle(document.documentElement).getPropertyValue('--fil') || '').trim();
  const src = () => 'printer.html?accent=' + encodeURIComponent(accent());
  let ready = false;
  const start = async () => {
    if (ready) return;
    try { const r = await fetch('printer.html', { method: 'HEAD' }); if (!r.ok) return; } catch (e) { return; }
    ready = true; document.documentElement.classList.add('has-printer'); frame.src = src();
  };
  if ('IntersectionObserver' in window) { const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); start(); } }, { rootMargin: '900px 0px' }); io.observe(repair); }
  else start();
  document.addEventListener('rf-accent', () => { if (ready) frame.src = src(); });
}

/* onModel(arrayBuffer, job): put the finished part on the 3D stage. */
export function initBackend({ onModel } = {}) {
  initI18n(); initSpeech();
  initPrinter();
  const api = backendUrl();
  const form = $('#repairForm'), note = $('#formNote'), status = $('#rfStatus'), submit = form.querySelector('button[type=submit]');
  const out = document.createElement('div');
  out.id = 'rfOut'; out.className = 'rf-out'; out.hidden = true; out.setAttribute('aria-live', 'polite');
  form.after(out);                       // outside the form: the panel holds forms of its own

  if (!api) {
    form.addEventListener('submit', e => { e.preventDefault(); note.textContent = t('note.demo'); });
    const demo = () => { status.textContent = t('status.demo'); }; demo(); onLang(demo);
    return { connected: false, makeTemplate: null };
  }

  const rf = new window.ReForm3D(api);
  initHistory(rf, show);
  let aiOn = false, busy = false, current = null, timer = null, t0 = 0, stage = '', seg = 0;
  const repair = $('#repair'), now = $('#rfNow'), nowLine = $('#rfNowLine'), nowTime = $('#rfNowTime'), segs = [...document.querySelectorAll('#rfSteps li')];
  const IDLE = () => t('idle');
  const setNow = (state, line, at, time) => {
    now.dataset.state = state; nowLine.textContent = line; nowTime.textContent = time || '';
    segs.forEach((li, i) => { li.classList.toggle('done', state === 'done' || i < at); li.classList.toggle('on', state === 'busy' && i === at); });
  };

  let statusFn = null;
  const paintStatus = () => { if (statusFn) status.textContent = statusFn(); };
  rf.health().then(h => {
    aiOn = !!h.design;
    statusFn = () => h.design
      ? t('status.ai', { m: h.pool ? h.pool.models.length + ' ' + t('models') : h.provider, t: h.templates })
      : t('status.noai', { t: h.templates });
    paintStatus(); status.classList.add('ok');
  }).catch(() => { statusFn = () => t('status.off'); paintStatus(); status.classList.add('bad'); });
  onLang(() => { paintStatus(); if (now.dataset.state === 'idle') nowLine.textContent = IDLE(); else if (now.dataset.state === 'done') nowLine.textContent = t('done'); else paint(); });

  const setBusy = on => { busy = on; submit.disabled = on; submit.style.opacity = on ? 0.55 : ''; repair.classList.toggle('busy', on); };
  const paint = () => setNow('busy', stage, seg, Math.round((Date.now() - t0) / 1000) + ' s');   // the progress card under the printer replaces the spinner in the form
  const SEG = { asking: 0, queued: 0, planning: 0, designing: 1, building: 3 };
  const progress = (s, job) => {
    const step = job && job.plan && job.plan.step;                       // what the design loop is doing right now (from the server)
    seg = SEG[s] == null ? 0 : SEG[s];
    if (s === 'designing' && step && /Checking|Found a problem|Rendering|approved/.test(step)) seg = 2;
    stage = step ? stepText(step) : t(STAGES[s] || 'stage.working');
    if (!timer) { t0 = Date.now(); timer = setInterval(paint, 1000); out.hidden = true; out.innerHTML = ''; const st = $('#rfStage'); if (st) st.scrollIntoView({ behavior: 'smooth', block: 'center' }); }   // the old panel (questions or result) makes way for the progress card, which scrolls into view
    paint();
  };
  const stop = () => { clearInterval(timer); timer = null; };
  const fail = msg => { stop(); setNow('idle', IDLE(), 0); out.hidden = true; out.innerHTML = ''; note.textContent = msg; note.classList.add('rf-bad'); setBusy(false); };
  const clearNote = () => { note.textContent = ''; note.classList.remove('rf-bad'); };
  const run = p => { setBusy(true); return p.then(show).catch(e => fail(e.message || t('err.generic'))).finally(() => document.dispatchEvent(new Event('rf-job-finished'))); };

  /* ---------- 1. clarifying questions ---------- */
  form.addEventListener('submit', async e => {
    e.preventDefault();
    if (busy) return;
    clearNote();
    if (!($('#what').value || '').trim()) { note.textContent = t('note.empty'); note.classList.add('rf-bad'); return; }
    if (!aiOn) return generate([]);
    setBusy(true); progress('asking');
    let qs = [];
    try { qs = ((await rf.clarify(form)) || {}).questions || []; } catch (err) { qs = []; }
    stop(); setBusy(false);
    if (!qs.length) return generate([]);
    askQuestions(qs);
  });

  function askQuestions(qs) {
    out.hidden = false;
    out.innerHTML = `<div class="rf-head"><h3>${esc(t('q.title'))}</h3><p class="mono">${esc(t('q.sub'))}</p></div>
      <form class="rf-qs" id="rfQs" novalidate>${qs.map((q, i) => {
        const id = 'rfq' + i, val = q.suggestion == null ? '' : q.suggestion;
        const input = q.kind === 'choice' && q.options && q.options.length
          ? `<select id="${id}">${q.options.map(o => `<option${String(o) === String(val) ? ' selected' : ''}>${esc(o)}</option>`).join('')}</select>`
          : `<input id="${id}" type="${q.kind === 'number' ? 'number' : 'text'}" step="any" value="${esc(val)}" placeholder="${esc(q.unit || '')}">`;
        return `<label class="field" for="${id}">${esc(q.question)}${q.unit && q.kind === 'number' ? ` <span class="mono">(${esc(q.unit)})</span>` : ''}${input}${q.why ? `<span class="rf-why">${esc(q.why)}</span>` : ''}</label>`;
      }).join('')}
      <div class="rf-row"><button class="btn btn-fil" type="submit">${esc(t('q.go'))}</button><button class="btn btn-ghost" type="button" id="rfSkip">${esc(t('q.skip'))}</button></div></form>`;
    $('#rfQs').addEventListener('submit', ev => {
      ev.preventDefault();
      generate(qs.map((q, i) => ({ question: q.question, answer: String($('#rfq' + i).value || '').trim() })).filter(a => a.answer));
    });
    $('#rfSkip').addEventListener('click', () => generate([]));
    out.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  /* ---------- 2. design ---------- */
  function generate(answers) {
    clearNote(); progress('queued');
    repair.classList.remove('has-result'); if (onModel) onModel(null);   // a new design: the printer comes back, the old part leaves the stage
    run(rf.generateFromForm(form, { answers, onStatus: progress, timeoutMs: 600000 }));
  }

  /* ---------- 3. result ---------- */
  async function show(job) {
    const secs = t0 ? Math.round((Date.now() - t0) / 1000) : 0; stop(); setBusy(false); current = job;
    setNow('done', t('done'), 4, secs ? secs + ' s' : '');
    const r = job.result, f = job.files || {}, d = r.design || null, est = r.estimate || null;
    const pieces = (r.pieces || []).map(p => `<li><b>${esc(p.name)}</b> <span class="mono">${esc((p.size_mm || []).join(' × '))} mm · ${esc(p.volume_cm3)} cm³ · ${p.ok ? t('res.closed') : t('res.attn')}</span>${(p.warnings || []).length ? `<br><span class="rf-warn">${esc(p.warnings.join(' '))}</span>` : ''}</li>`).join('');
    const estLine = est ? `<p class="rf-est mono">${esc(t(est.source ? 'est.sliced' : 'est.rough', { src: est.source, g: est.filament_g, m: est.material, min: est.print_minutes }))}</p>` : '';
    const origin = d ? (d.cached_from ? t('o.cached') : d.tuned_from ? t('o.tuned') : d.revised_from ? t('o.revised') : '') : '';
    const how = d ? `${t(d.attempts === 1 ? 'how.one' : 'how.many', { n: d.attempts })}${d.reviewed ? t('how.reviewed') : ''}${d.models && d.models.length ? t('how.by', { m: d.models.join(' / ') }) : ''}.` : '';
    out.hidden = false;
    out.innerHTML =
      `<div class="rf-head"><h3>${esc(r.part_name || t('res.part'))}</h3><p class="mono">${esc(d ? t('res.ai') : t('res.tpl'))}</p></div>
      <p class="rf-stage-note mono" id="rfStageNote">${f.glb && innerWidth >= 900 ? t('res.stage') : ''}</p>
      ${f.preview ? `<img class="rf-prev" id="rfPrev" src="${esc(f.preview)}" alt="Preview of the generated part" loading="lazy">` : ''}
      ${d && d.understanding ? `<p class="rf-und">${esc(d.understanding)}</p>` : job.plan && job.plan.rationale && !/chosen directly/.test(job.plan.rationale) ? `<p class="rf-und">${esc(job.plan.rationale)}</p>` : ''}
      ${origin || how ? `<p class="rf-est mono">${esc([origin, how].filter(Boolean).join(' '))}</p>` : ''}
      ${estLine}
      <div class="rf-dl">${f.zip ? `<a class="btn btn-fil" href="${esc(f.zip)}" target="_blank" rel="noopener">${esc(t('res.zip'))}</a>` : ''}${(f.stl || []).map(s => `<a class="btn btn-ghost" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.piece)}.stl</a>`).join('')}${f.fit_test ? `<a class="btn btn-ghost" href="${esc(f.fit_test)}" target="_blank" rel="noopener">${esc(t('res.fit'))}</a>` : ''}${f.readme ? `<a class="btn btn-ghost" href="${esc(f.readme)}" target="_blank" rel="noopener">${esc(t('res.notes'))}</a>` : ''}</div>
      ${pieces ? `<ul class="rf-pieces">${pieces}</ul>` : ''}
      ${list(t('res.warn'), r.warnings, 'warn')}
      ${d ? list(t('res.assumed'), d.assumptions) : ''}
      ${list(t('res.how'), r.print_notes)}${list(t('res.fit2'), r.fit_notes)}
      <div id="rfTools"></div>
      <p class="rf-disc">${esc(aiLanguage() ? t('res.disc') : (r.disclaimer || t('res.disc')))}</p>`;
    tools(job);
    out.scrollIntoView({ behavior: 'smooth', block: 'start' });
    if (f.glb && onModel) {
      try { const buf = await (await fetch(f.glb)).arrayBuffer(); await onModel(buf, job); repair.classList.add('has-result'); }
      catch (err) { const n = $('#rfStageNote'); if (n) n.textContent = ''; }
    }
  }

  /* ---------- 4. change it: sizes without AI, words with AI ---------- */
  async function tools(job) {
    const box = $('#rfTools'), r = job.result, d = r.design;
    let fields = [], rebuild = null;
    if (d && (d.parameters || []).length) {
      fields = d.parameters.map(p => ({ name: p.name, label: p.name.replace(/_/g, ' '), value: p.value ?? p.default, unit: /angle|deg|count|n_|number/.test(p.name) ? '' : 'mm' }));
      rebuild = params => rf.tune(job.id, params, { onStatus: progress });
    } else if (!d && r.part_id) {
      try {
        const spec = await rf.part(r.part_id);
        fields = (spec.params || []).filter(p => p.kind === 'float' || p.kind === 'int').slice(0, 6).map(p => ({ name: p.name, label: p.label, value: (r.params || {})[p.name] ?? p.default, unit: p.unit || '', min: p.min, max: p.max }));
      } catch (e) { fields = []; }
      rebuild = params => rf.build(r.part_id, Object.assign({}, r.params, params), { onStatus: progress });
    }
    box.innerHTML =
      (fields.length ? `<form class="rf-tune" id="rfTune" novalidate><h3>${esc(t('tune.title'))} <span class="mono">${esc(t('tune.sub'))}</span></h3><div class="rf-grid">${fields.map((p, i) =>
        `<label class="field" for="rft${i}">${esc(p.label)}${p.unit ? ` <span class="mono">(${esc(p.unit)})</span>` : ''}<input id="rft${i}" type="number" step="any" data-name="${esc(p.name)}" value="${esc(p.value)}"${p.min != null ? ` min="${p.min}" max="${p.max}"` : ''}></label>`).join('')}</div><button class="btn btn-ghost" type="submit">${esc(t('tune.go'))}</button></form>` : '') +
      (d && aiOn ? `<form class="rf-rev" id="rfRev" novalidate><label class="field" for="rfFb">${esc(t('rev.q'))}<textarea id="rfFb" placeholder="${esc(t('rev.ph'))}"></textarea></label><button class="btn btn-ghost" type="submit">${esc(t('rev.go'))}</button></form>` : '');
    attachMic($('#rfFb'));
    const tune = $('#rfTune');
    if (tune) tune.addEventListener('submit', e => {
      e.preventDefault(); if (busy) return; clearNote();
      const params = {}; tune.querySelectorAll('input').forEach(i => { if (i.value !== '') params[i.dataset.name] = Number(i.value); });
      progress('building'); run(rebuild(params));
    });
    const rev = $('#rfRev');
    if (rev) rev.addEventListener('submit', e => {
      e.preventDefault(); if (busy) return; clearNote();
      const fb = ($('#rfFb').value || '').trim(); if (!fb) return;
      progress('designing'); run(rf.revise(job.id, fb, { onStatus: progress, timeoutMs: 600000 }));
    });
  }

  /* ---------- 5. the example parts: build the real template ---------- */
  function makeTemplate(id) {
    if (busy) return Promise.resolve();
    clearNote(); progress('building');
    return run(rf.build(id, {}, { onStatus: progress }));
  }

  return { connected: true, makeTemplate };
}
