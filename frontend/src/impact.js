const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const inr = v => '₹' + new Intl.NumberFormat('en-IN', {maximumFractionDigits: v < 100 ? 2 : 0}).format(v);
const kg = v => new Intl.NumberFormat('en-IN', {maximumFractionDigits: v < 1 ? 3 : 2}).format(v) + ' kg CO₂e';
const pct = v => Math.round(Math.abs(v)) + '%';
const mins = v => v < 90 ? Math.round(v) + ' min' : (v / 60).toFixed(1).replace(/\.0$/, '') + ' h';
const sizeText = s => {
  if (!Array.isArray(s) || !s.length) return '';
  if (Array.isArray(s[0])) return s.length === 1 ? sizeText(s[0]) : `${s.length} pieces`;
  return s.map(n => Math.round(n)).join(' × ') + ' mm';
};

// One horizontal bar. `parts` stack inside the bar (e.g. material + printing); width is relative to `max`.
const bar = (label, total, max, parts, cls) => `<div class="rf-sbar ${cls}"><div class="rf-sbar-head"><span>${label}</span><b>${total}</b></div><div class="rf-sbar-rail">${parts.map(([v, c, name]) => v > 0 ? `<i class="${c}" style="--w:${v / max * 100}%" title="${esc(name)}"></i>` : '').join('')}</div></div>`;

export function createImpact({rf, host, onBack}) {
  let payload = null, active = false, request = 0, jobId = null;
  const close = () => { active = false; request++; onBack(); };

  async function open(row) {
    active = true; jobId = row.job_id;
    const token = ++request;
    host.innerHTML = '<div class="rf-impact-loading" role="status"><span></span><p>Working out the numbers…</p></div>';
    try {
      const data = await rf.impact(row.job_id);
      if (!active || token !== request) return;
      payload = data; render(); host.querySelector('[data-impact-back]').focus();
    } catch (_) {
      if (!active || token !== request) return;
      host.innerHTML = '<button class="btn btn-ghost" data-impact-back>← Back to history</button><p role="alert">The numbers could not be loaded. Your saved design is unchanged.</p>';
      host.querySelector('button').onclick = close;
    }
  }
  const deactivate = () => { active = false; request++; };

  function costCard(c) {
    if (!c) return '<section class="rf-scard"><h3>Cost</h3><p class="rf-sempty">Not enough information to work out the cost of this design.</p></section>';
    const hasStore = c.store != null, max = Math.max(c.store || 0, c.print, 0.01);
    const cheaper = hasStore && c.saved > 0;
    const source = !hasStore ? '' : c.store_source?.kind === 'you' ? 'Store price you entered' : c.store_source?.url ? `Store price: <a href="${esc(c.store_source.url)}" target="_blank" rel="noopener noreferrer">${esc(c.store_source.title)} ↗</a>` : 'Store price';
    return `<section class="rf-scard" aria-labelledby="rfsCost"><h3 id="rfsCost">Cost</h3>
      <div class="rf-sbars">${hasStore ? bar('Buy from a store', inr(c.store), max, [[c.store, 'store', 'Store price']], 'is-store') : ''}
        ${bar('3D print with ReForm3D', inr(c.print), max, [[c.filament || 0, 'a', 'Filament'], [c.electricity || 0, 'b', 'Electricity'], [c.other, 'c', 'Labour, machine time and failed prints']], 'is-print')}</div>
      <p class="rf-sresult ${hasStore ? (cheaper ? 'good' : 'neutral') : 'neutral'}">${!hasStore ? 'Add a store price to compare.' : cheaper ? `You save <b>${inr(c.saved)}</b> <span>(${pct(c.percent)} less)</span>` : c.saved === 0 ? 'Same price as the store.' : `<b>${inr(-c.saved)} more</b> than the store <span>— but made to fit you</span>`}</p>
      <ul class="rf-skey"><li><i class="a"></i>Filament ${inr(c.filament || 0)}</li><li><i class="b"></i>Electricity ${inr(c.electricity || 0)}</li><li><i class="c"></i>Labour, machine & failed prints ${inr(c.other)}</li></ul>
      <form class="rf-sprice" data-store-price><label>${hasStore ? 'Store price differs?' : 'Store price'}<span><b>₹</b><input name="price" type="number" inputmode="decimal" min="0" step="any" placeholder="${hasStore ? esc(Math.round(c.store)) : 'e.g. 450'}" aria-label="Store price in rupees"></span></label><button class="btn btn-ghost" type="submit">${hasStore ? 'Update' : 'Compare'}</button>${c.store_source?.kind === 'you' ? '<button class="btn btn-ghost" type="button" data-clear-price>Reset</button>' : ''}</form>
      <p class="rf-ssource" role="status">${source}</p></section>`;
  }

  function carbonCard(c) {
    if (!c) return '<section class="rf-scard"><h3>Carbon</h3><p class="rf-sempty">Not enough information to work out the carbon footprint.</p></section>';
    const max = Math.max(c.store, c.print, 1e-9), lower = c.saved > 0;
    return `<section class="rf-scard" aria-labelledby="rfsCarbon"><h3 id="rfsCarbon">Carbon footprint</h3>
      <div class="rf-sbars">${bar('Buy from a store', kg(c.store), max, [[c.store, 'store', 'Making and delivering a bought item']], 'is-store')}
        ${bar('3D print with ReForm3D', kg(c.print), max, [[c.material, 'a', 'Material'], [c.printing, 'b', 'Printing electricity'], [c.failed, 'c', 'Failed-print allowance']], 'is-print')}</div>
      <p class="rf-sresult ${lower ? 'good' : 'neutral'}">${lower ? `<b>${pct(c.percent)} less</b> CO₂e <span>(${kg(c.saved)} avoided)</span>` : `<b>${pct(c.percent)} more</b> CO₂e than a bought item`}</p>
      <ul class="rf-skey"><li><i class="a"></i>Material ${kg(c.material)}</li><li><i class="b"></i>Printing ${kg(c.printing)}</li>${c.failed > 0 ? `<li><i class="c"></i>Failed prints ${kg(c.failed)}</li>` : ''}</ul>
      <p class="rf-ssource">Worked out from the ${Math.round(c.mass_g * 10) / 10} g part weight.${c.material_specific ? '' : ` ${esc(c.material_name || 'This material')} uses the PLA average per gram.`}</p></section>`;
  }

  function render() {
    if (!payload.report.simple) {
      host.innerHTML = '<div class="rf-impact-top"><button class="btn btn-ghost" data-impact-back>← Back to history</button></div><section class="rf-scard"><h3>Restart needed</h3><p class="rf-sempty">This page is newer than the ReForm3D server that is running. Close the Terminal window running ReForm3D, open <b>start.command</b> again, then reload this page.</p></section>';
      host.querySelector('[data-impact-back]').onclick = close; return;
    }
    const r = payload.report, s = r.simple, t = s.time, size = sizeText(r.geometry?.size_mm), grams = r.manufacturing?.filament_g;
    host.innerHTML = `<div class="rf-impact-top"><button class="btn btn-ghost" data-impact-back>← Back to history</button></div>
      <header class="rf-shead"><h2 id="rfImpactHeading">${esc(r.title)}</h2><p>${[r.material, grams != null ? Math.round(grams * 10) / 10 + ' g' : '', t ? mins(t.print_minutes) + ' to print' : ''].filter(Boolean).map(esc).join(' · ')}</p></header>
      <div class="rf-sgrid">${costCard(s.cost)}${carbonCard(s.carbon)}</div>
      <div class="rf-sextras">
        ${t ? `<div class="rf-sfact"><small>Ready in</small><b>${mins(t.print_minutes)}</b><span>vs ${t.delivery_days ? `${t.delivery_days.low}–${t.delivery_days.high} days` : 'days'} for delivery</span></div>` : ''}
        <div class="rf-sfact"><small>Made for you</small><b>${size || 'Your size'}</b><span>Store items come in fixed sizes. This one is built to your measurements and can be changed any time.</span></div>
      </div>
      <details class="rf-impact-details rf-show"><summary>How this is worked out</summary>
        <ul class="rf-impact-method"><li>Cost = filament + electricity + labour + machine time + a 20% allowance for failed prints.</li><li>Carbon = part weight × CO₂e per gram. For PLA that is 0.08 kg (material) + 0.06 kg (printing) per 35 g, from the team's life-cycle baseline (Faludi et al., 2023; TotalEnergies Corbion). A bought item is taken to weigh the same, at about 8.5 g CO₂e per gram to make and deliver.</li><li>These are estimates, not measured savings.</li></ul></details>`;
    host.querySelector('[data-impact-back]').onclick = close;
    const form = host.querySelector('[data-store-price]'), status = host.querySelector('.rf-ssource');
    const save = async value => {
      const token = ++request;
      try { const res = await rf.saveStorePrice(jobId, value); if (active && token === request) { payload = res; render(); host.querySelector('[data-store-price] input')?.focus(); } }
      catch (_) { if (active && token === request && status) status.textContent = 'The price could not be saved. Try again.'; }
    };
    form?.addEventListener('submit', e => { e.preventDefault(); const v = form.price.value.trim(); if (v === '' || !(Number(v) >= 0)) { status.textContent = 'Enter the store price in rupees.'; return; } save(Number(v)); });
    host.querySelector('[data-clear-price]')?.addEventListener('click', () => save(null));
  }
  return {open, deactivate};
}
