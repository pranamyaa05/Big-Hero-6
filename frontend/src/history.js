import { createImpact } from './impact.js';
import { t, applyI18n, topTools } from './i18n.js';
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function initHistory(rf, show) {
  const button = document.createElement('button');
  button.className = 'rf-history-button btn'; button.type = 'button';
  button.setAttribute('aria-expanded', 'false'); button.setAttribute('aria-controls', 'rfHistory');
  button.innerHTML = '<span aria-hidden="true">◷</span><span class="rf-history-label" data-i18n="hist.btn">History</span> <span id="rfHistoryCount">…</span>';
  button.setAttribute('data-i18n-aria', 'hist.btn'); button.setAttribute('aria-label', 'History'); topTools().append(button);
  const page = document.createElement('dialog'); page.id = 'rfHistory'; page.className = 'rf-history';
  page.setAttribute('aria-labelledby', 'rfHistoryTitle');
  page.innerHTML = `<header><h1 id="rfHistoryTitle" data-i18n="hist.title">History & Statistics</h1><button class="btn btn-ghost" data-close data-i18n="close">Close</button></header>
    <div class="rf-history-tabs" role="tablist" aria-label="History and statistics"><button id="rfHistoryTab" role="tab" aria-controls="rfHistoryContent" data-tab="history" data-i18n="hist.btn">History</button><button id="rfStatsTab" role="tab" aria-controls="rfHistoryContent" data-tab="statistics" data-i18n="tab.stats">Statistics</button></div>
    <p class="rf-history-error" role="status"></p><section id="rfHistoryContent" role="tabpanel"></section>`;
  document.body.append(page); applyI18n(page); applyI18n(button);
  const content = page.querySelector('section'), error = page.querySelector('[role=status]');
  let summaries = {}, impactActive = false, impactTrigger = null, statisticsImpact = null;
  const impact = createImpact({rf, host: content, onBack: () => { impactActive = false; refresh(); render(); content.querySelector(`[data-id="${impactTrigger}"] [data-impact]`)?.focus(); }});
  let tab = 'history', rows = [], stats = null, previousOverflow = '', pending = false, closing = false;
  try { tab = localStorage.getItem('rf-history-tab') === 'statistics' ? 'statistics' : 'history'; } catch (_) {}
  const refresh = async () => {
    try { const [h, s, sums] = await Promise.all([rf.history(), rf.stats(), rf.historySummaries().catch(() => ({}))]); summaries = sums || {}; rows = h.rows; stats = s; document.getElementById('rfHistoryCount').textContent = h.total; error.textContent = ''; if (page.open && !impactActive) render(); }
    catch (_) { if (page.open && !impactActive) { content.innerHTML = ''; error.textContent = t('hist.err'); } }
  };
  const close = () => {
    if (!page.open || closing) return;
    closing = true; impactActive = false; impact.deactivate(); statisticsImpact?.deactivate();
    const finish = () => { page.close(); document.body.style.overflow = previousOverflow; button.setAttribute('aria-expanded', 'false'); button.focus(); closing = false; };
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) finish();
    else page.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 140 }).finished.then(finish, finish);
  };
  const requestClose = () => { if (history.state?.rfHistory) history.back(); else close(); };
  button.onclick = () => {
    if (closing || page.open) return;
    history.pushState({...history.state, rfHistory:true}, ''); previousOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden';
    page.showModal(); button.setAttribute('aria-expanded', 'true');
    content.innerHTML = `<div class="rf-history-skeleton" role="status">${t('hist.loading')}</div>`; refresh();
  };
  page.querySelector('[data-close]').onclick = requestClose;
  page.addEventListener('cancel', e => { e.preventDefault(); requestClose(); });
  window.addEventListener('popstate', close);
  page.querySelectorAll('[data-tab]').forEach(b => {
    b.onclick = () => { impactActive = false; impact.deactivate(); statisticsImpact?.deactivate(); tab = b.dataset.tab; try { localStorage.setItem('rf-history-tab', tab); } catch (_) {} render(); };
    b.onkeydown = e => { if (['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) { e.preventDefault(); const other = page.querySelector(`[data-tab="${b.dataset.tab === 'history' ? 'statistics' : 'history'}"]`); other.click(); other.focus(); } };
  });
  const money = v => '₹' + new Intl.NumberFormat('en-IN', {maximumFractionDigits: v < 100 ? 2 : 0}).format(v);
  const co2 = v => new Intl.NumberFormat('en-IN', {maximumFractionDigits: v < 1 ? 3 : 2}).format(v) + ' kg CO₂e';
  function statStrip(s) {
    if (!s || (!s.cost && !s.carbon)) return '';
    const c = s.cost, k = s.carbon, t = s.time;
    const saving = c && c.saved != null ? (c.saved > 0 ? `<li class="good"><b>${money(c.store)}</b> in a store · you save ${money(c.saved)} (${Math.round(c.percent)}%)</li>` : `<li><b>${money(c.store)}</b> in a store</li>`) : c ? '<li class="ask"><button class="rf-linkbtn" data-impact>Add store price to compare</button></li>' : '';
    return `<ul class="rf-hstats" aria-label="Cost and carbon">${c ? `<li><b>${money(c.print)}</b> to print</li>` : ''}${saving}${k ? `<li><b>${co2(k.print)}</b>${k.percent > 0 ? ` · ${Math.round(k.percent)}% less than bought` : ''}</li>` : ''}${t ? `<li>Ready in <b>${t.print_minutes < 90 ? Math.round(t.print_minutes) + ' min' : (t.print_minutes / 60).toFixed(1) + ' h'}</b></li>` : ''}</ul>`;
  }
  function render() {
    page.querySelectorAll('[data-tab]').forEach(b => { const selected = b.dataset.tab === tab; b.setAttribute('aria-selected', selected); b.tabIndex = selected ? 0 : -1; });
    content.setAttribute('aria-labelledby', tab === 'history' ? 'rfHistoryTab' : 'rfStatsTab');
    if (tab === 'statistics') return renderStats();
    content.innerHTML = `<div class="rf-history-filters"><label>Search<input id="rfHistorySearch" type="search" placeholder="Search requests"></label><label>Status<select id="rfHistoryStatus"><option value="">All statuses</option>${['done','declined','failed'].map(s=>`<option>${s}</option>`).join('')}</select></label><label>Material<select id="rfHistoryMaterial"><option value="">All materials</option>${[...new Set(rows.map(r=>r.material).filter(Boolean))].map(s=>`<option>${escape(s)}</option>`).join('')}</select></label><button class="btn btn-ghost" id="rfHistoryClear" ${rows.length?'':'disabled'}>Clear my history</button></div><div id="rfHistoryCards"></div>`;
    const paint = () => {
      const q = content.querySelector('input').value.toLowerCase(), status = content.querySelector('#rfHistoryStatus').value, material = content.querySelector('#rfHistoryMaterial').value;
      const filtered = rows.filter(r => (!status || r.status === status) && (!material || r.material === material) && `${r.title} ${r.request}`.toLowerCase().includes(q));
      const cards = content.querySelector('#rfHistoryCards');
      cards.innerHTML = !rows.length ? '<p>Make a part to start your history.</p><button class="btn btn-fil" data-make>Make a part</button>' : !filtered.length ? '<p>No matching requests.</p>' : filtered.map(r => {
        const age = Math.max(0, Math.floor((Date.now()-Date.parse(r.created_at))/60000));
        const time = age < 1 ? 'Just now' : age < 60 ? `${age} min ago` : age < 1440 ? `${Math.floor(age/60)} h ago` : `${Math.floor(age/1440)} days ago`;
        const label = r.estimate_source && r.estimate_source !== 'rough estimate' ? 'sliced' : 'estimate';
        return `<article class="rf-history-card ${r.status !== 'done' ? 'muted' : ''}" data-id="${escape(r.job_id)}">
          ${r.files_available && r.preview_url ? `<img src="${escape(rf.abs(r.preview_url))}" alt="Preview of ${escape(r.title)}" loading="lazy">` : '<div class="rf-history-placeholder" aria-hidden="true">◷</div>'}
          <div><h2>${escape(r.title)}</h2><time datetime="${escape(r.created_at)}" title="${escape(r.created_at)}">${time}</time> <span class="rf-history-chip">${escape(r.status)}</span>
          <p>${escape(r.material || 'Material unavailable')} · ${r.source === 'cache' ? 'Cached AI design' : r.source === 'ai' ? 'Designed by AI' : 'Ready-made template'}${r.source === 'fallback' ? ' (fallback)' : ''}</p>
          <p>${r.filament_g == null ? 'Plastic unavailable' : `${escape(r.filament_g)} g (${label})`} · ${r.print_minutes == null ? 'Print time unavailable' : `${escape(r.print_minutes)} min (${label})`}</p>
          ${r.error ? `<p>${escape(r.error)}</p>` : ''}${statStrip(summaries[r.job_id])}
          <div class="rf-history-actions">${r.status === 'done' ? '<button class="btn btn-fil" data-impact>View Impact ↗</button>' : ''}${r.status === 'done' && r.files_available ? '<button class="btn btn-ghost" data-open>Open</button>' : r.status === 'done' ? '<span>Files no longer available</span>' : ''}
          ${r.files_available && r.zip_url ? `<a class="btn btn-ghost" href="${escape(rf.abs(r.zip_url))}" target="_blank" rel="noopener">Download zip</a>` : ''}<button class="btn btn-ghost" data-copy>Copy request text</button></div></div></article>`;
      }).join('');
      cards.querySelector('[data-make]')?.addEventListener('click', () => { requestClose(); document.querySelector('#repair').scrollIntoView(); });
      cards.querySelectorAll('img').forEach(img => img.onerror = () => { img.replaceWith(document.createTextNode('Preview unavailable')); });
    };
    content.querySelectorAll('input,select').forEach(el=>el.addEventListener('input', paint)); paint();
    content.querySelector('#rfHistoryClear').onclick = async () => {
      if (!window.confirm('Clear your saved history? This cannot be undone.')) return;
      try { await rf.clearHistory(); await refresh(); } catch (_) { error.textContent = 'History could not be cleared. Please try again.'; }
    };
  }
  content.addEventListener('click', async e => {
    const card = e.target.closest('[data-id]'); if (!card || pending) return;
    const row = rows.find(r => r.job_id === card.dataset.id);
    if (e.target.closest('[data-impact]')) { impactActive = true; impactTrigger = row.job_id; impact.open(row); return; }
    if (e.target.closest('[data-copy]')) { try { await navigator.clipboard.writeText(row.request || ''); e.target.textContent = 'Copied'; } catch (_) { error.textContent = 'Could not copy the request.'; } }
    if (e.target.closest('[data-open]')) {
      pending = true;
      try { const saved = await rf.historyEntry(row.job_id); if (!saved.files_available) { await refresh(); return; } requestClose(); const input = document.querySelector('#what'); if (input) input.value = saved.request || ''; await show(rf._absolutize(saved.job)); }
      catch (_) { error.textContent = 'This result could not be opened.'; } finally { pending = false; }
    }
  });
  function renderStats() {
    statisticsImpact?.deactivate();
    const completed = rows.filter(row => row.status === 'done');
    if (!completed.length) {
      content.innerHTML = '<div class="rf-statistics-empty"><h2>No completed designs yet</h2><p>Make a part to see its cost, carbon and material comparisons.</p><button class="btn btn-fil" data-stats-make>Make a part</button></div>';
      content.querySelector('[data-stats-make]').onclick = () => { requestClose(); document.querySelector('#repair').scrollIntoView(); };
      return;
    }
    let selected = completed[0].job_id;
    try {
      const remembered = localStorage.getItem('rf-impact-job');
      if (completed.some(row => row.job_id === remembered)) selected = remembered;
    } catch (_) {}
    content.innerHTML = `<div class="rf-statistics-picker"><div><h2>Statistics for your design</h2><p>What one saved part costs and emits, compared with buying it.</p></div><label for="rfStatisticsDesign">Choose a completed design<select id="rfStatisticsDesign">${completed.map(row => `<option value="${escape(row.job_id)}" ${row.job_id === selected ? 'selected' : ''}>${escape(row.title)} · ${escape(row.material || 'Material unavailable')} · ${escape(new Date(row.created_at).toLocaleDateString())}</option>`).join('')}</select></label></div><div id="rfStatisticsImpact"></div><details class="rf-impact-details rf-history-totals"><summary>History totals <span>All saved requests</span></summary><div id="rfHistoryTotals"></div></details>`;
    renderTotals(content.querySelector('#rfHistoryTotals'));
    statisticsImpact = createImpact({rf, host: content.querySelector('#rfStatisticsImpact'), onBack: () => {
      impactActive = false; statisticsImpact?.deactivate(); tab = 'history'; refresh();
      try { localStorage.setItem('rf-history-tab', tab); } catch (_) {}
      render(); page.querySelector('#rfHistoryTab').focus();
    }});
    const select = content.querySelector('#rfStatisticsDesign');
    const load = () => {
      impactActive = true;
      try { localStorage.setItem('rf-impact-job', select.value); } catch (_) {}
      statisticsImpact.open({job_id: select.value});
    };
    select.onchange = load;
    load();
  }
  function renderTotals(target) {
    if (!stats || !stats.total_requests) { target.innerHTML = '<p>No data yet. Make a part to see your statistics.</p>'; return; }
    const metric = (title, value, label, count, excluded = 0) => `<article><h2>${title}</h2><strong>${escape(value ?? 'Unavailable')}</strong><small>${escape(label)} · ${count} rows${excluded ? ` · ${excluded} excluded` : ''}</small></article>`;
    const quantity = (title, data, divisor, unit) => metric(title, data.value == null ? null : `${Number((data.value/divisor).toFixed(2))} ${unit}`, data.label === 'recorded' ? 'recorded' : `${data.label} (${data.sliced} sliced, ${data.estimated} estimated)`, data.rows, data.excluded);
    const sources = stats.sources;
    const chart = (title, entries) => {
      const max = Math.max(1, ...entries.map(e=>e[1]));
      return `<figure><figcaption>${title}</figcaption><div aria-hidden="true">${entries.map(([k,v])=>`<div class="rf-history-bar"><span>${escape(k)}</span><span class="rf-history-track"><i style="width:${v/max*100}%"></i></span><b>${v}</b></div>`).join('')}</div><table class="rf-sr-only"><caption>${title}, recorded request counts</caption><thead><tr><th>Category</th><th>Requests</th></tr></thead><tbody>${entries.map(([k,v])=>`<tr><th>${escape(k)}</th><td>${v}</td></tr>`).join('')}</tbody></table><small>Recorded · ${entries.reduce((n,e)=>n+e[1],0)} rows</small></figure>`;
    };
    target.innerHTML = `<p class="rf-history-context">Parts made counts completed designs. Print usage is projected from saved estimates.</p><div class="rf-history-metrics">${metric('Parts made', stats.statuses.done ?? 0, 'recorded completed requests', stats.statuses.done ?? 0)}${quantity('Plastic used', stats.filament_g, 1, 'g')}${quantity('Print time', stats.print_minutes, 60, 'h')}${metric('AI / template / cache', `${sources.ai || 0} / ${(sources.template || 0)+(sources.fallback || 0)} / ${sources.cache || 0}`, 'recorded; fallback included in templates', stats.total_requests)}${quantity('Average AI design time', stats.average_ai_design_seconds, 1, 's')}${metric('Requests', stats.total_requests, `${stats.statuses.done||0} done · ${stats.statuses.declined||0} declined · ${stats.statuses.failed||0} failed`, stats.total_requests)}</div>
      <div class="rf-history-charts">${Object.keys(stats.materials).length ? chart('Material mix', Object.entries(stats.materials)) : '<p>Material mix: No data yet</p>'}${chart('Design sources', Object.entries(sources))}${chart('Requests per day (UTC, last 14 days)', stats.designs_per_day.map(d=>[d.date,d.count]))}</div>
      <p>Models used: ${escape(Object.entries(stats.models).map(([k,v])=>`${k} (${v} rows)`).join(', ') || 'Unavailable')}.</p><p>Most common recipient: ${escape(stats.most_common_who_for || 'Unavailable')}.</p>`;
  }
  refresh().then(() => {
    if (new URLSearchParams(location.search).get('view') === 'statistics') {
      tab = 'statistics';
      button.click();
    }
  });
  document.addEventListener('rf-job-finished', refresh);
  return { refresh };
}
