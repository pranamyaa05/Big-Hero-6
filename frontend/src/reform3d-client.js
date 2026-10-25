/* ReForm3D API client: no dependencies, works in any browser (or Node 18+). Drop it into the website and call it from the request form.
 *
 *   const rf = new ReForm3D('https://your-backend.example.com');         // '' = same origin
 *   const job = await rf.generateFromForm(document.querySelector('#repairForm'), { onStatus: s => console.log(s) });
 *   job.files.zip  -> download link,  job.files.stl[0].url -> STL,  job.files.glb -> 3D preview,  job.result.design -> how the AI understood the request and the sizes it assumed
 *
 * Field names match the existing form: #what, #dims, #mat, #who, #photos.
 *
 * The full flow, all optional except the last step:
 *   const q = await rf.clarify(fields)                      -> up to 3 questions with suggested answers
 *   const m = await rf.measure(photoFile, [[[x1,y1],[x2,y2]]])   -> mm from a photo of the printed marker (rf.markerUrl())
 *   const job = await rf.generateFromForm(fields, { measurements, answers })
 *   const v2 = await rf.revise(job.id, 'make the handle 10 mm longer')   (AI)
 *   const v3 = await rf.tune(job.id, { clearance: 0.6 })                  (no AI, instant)
 */
(function (root) {
  class ReForm3DError extends Error {
    constructor(message, status, detail) { super(message); this.status = status; this.detail = detail; }
  }

  class ReForm3D {
    constructor(baseUrl = '', { apiKey = '' } = {}) {
      this.base = baseUrl.replace(/\/$/, '');
      if (!root.rfClientId) {
        root.rfClientId = root.crypto?.randomUUID?.() || 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => { const n = Math.random()*16|0; return (c === 'x' ? n : (n&3|8)).toString(16); });
        try { root.rfClientId = localStorage.getItem('rf-client-id') || root.rfClientId; localStorage.setItem('rf-client-id', root.rfClientId); } catch (_) {}
      }
      this.clientId = root.rfClientId;
      this.apiKey = apiKey;           // only needed if the server sets REFORM3D_API_KEY; do not ship a secret key in a public website
    }

    url(path) { return this.base + path; }
    abs(rel) { return rel && rel.startsWith('/') ? this.base + rel : rel; }   // turn a file URL from a job into a full URL

    async _fetch(path, opts = {}) {
      const headers = Object.assign({}, opts.headers || {});
      headers['X-Client-Id'] = this.clientId;
      if (this.apiKey) headers['X-API-Key'] = this.apiKey;
      let res;
      try { res = await fetch(this.url(path), Object.assign({}, opts, { headers })); }
      catch (e) { throw new ReForm3DError('Could not reach the ReForm3D server. Check your connection and try again.', 0, String(e)); }
      const body = await res.json().catch(() => ({}));
      if (!res.ok && res.status !== 202) {
        const detail = body.detail;
        const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg).join('; ') : 'The request failed.';
        throw new ReForm3DError(msg, res.status, detail);
      }
      return body;
    }

    _json(body) { return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }; }

    health() { return this._fetch('/health'); }
    history(limit = 10000) { return this._fetch('/api/v1/history?limit=' + limit); }
    historySummaries() { return this._fetch('/api/v1/history-summaries'); }
    impact(id, reportId = '') { return this._fetch('/api/v1/history/' + encodeURIComponent(id) + '/impact' + (reportId ? '?report_id=' + encodeURIComponent(reportId) : '')); }
    researchImpact(id, force = false) { return this._fetch('/api/v1/history/' + encodeURIComponent(id) + '/research?force=' + force, {method:'POST'}); }
    saveStorePrice(id, price) { return this._fetch('/api/v1/history/' + encodeURIComponent(id) + '/store-price', this._json({price_inr: price})); }
    saveImpact(id, inputs) { return this._fetch('/api/v1/history/' + encodeURIComponent(id) + '/impact', this._json(inputs)); }
    historyEntry(id) { return this._fetch('/api/v1/history/' + encodeURIComponent(id)); }
    stats() { return this._fetch('/api/v1/stats'); }
    clearHistory() { return this._fetch('/api/v1/history', { method: 'DELETE' }); }
    parts() { return this._fetch('/api/v1/parts').then(r => r.parts); }
    part(id) { return this._fetch('/api/v1/parts/' + encodeURIComponent(id)); }

    /** Template matching only: which ready-made template and values would be used, without building anything. */
    plan({ description = '', dims = '', who_for = '', material = '' }) {
      return this._fetch('/api/v1/plan', this._json({ description, dims, who_for, material }));
    }

    /** Free text / measurements -> job. mode: 'auto' (AI designs from scratch when the server has a model) | 'design' (require that) | 'template' (ready-made templates only). */
    async generate(fields, { mode = 'auto', onStatus, timeoutMs = 300000 } = {}) {
      const job = await this._fetch('/api/v1/generate?wait=25', this._json(Object.assign({ mode }, fields)));
      return this.waitFor(job, { onStatus, timeoutMs });
    }

    /** No AI: build a ready-made template from explicit parameters. */
    async build(partId, params = {}, { onStatus, timeoutMs = 300000 } = {}) {
      const job = await this._fetch('/api/v1/parts/' + encodeURIComponent(partId) + '/build?wait=25', this._json({ params }));
      return this.waitFor(job, { onStatus, timeoutMs });
    }

    _formData(formOrFields) {
      const fd = new FormData();
      const f = formOrFields;
      const isEl = typeof HTMLElement !== 'undefined' && f instanceof HTMLElement;
      const val = (id) => (isEl ? (f.querySelector('#' + id) || {}).value : f[id]) || '';
      fd.append('what', val('what')); fd.append('dims', val('dims')); fd.append('mat', val('mat')); fd.append('who', val('who')); fd.append('lang', val('lang'));
      const photos = isEl ? (f.querySelector('#photos') || {}).files : f.photos;
      if (photos) for (const p of Array.from(photos).slice(0, 3)) fd.append('photos', p, p.name);
      return fd;
    }

    /** The website's request form (what, dims, mat, who, photos). Accepts a <form> element or a plain object.
     *  measurements: [{label, value_mm, plusminus_mm, source: 'measured'|'typed'}], answers: [{question, answer}], fresh: design again even if cached. */
    async generateFromForm(formOrFields, { mode = 'auto', measurements = [], answers = [], fresh = false, onStatus, timeoutMs = 300000 } = {}) {
      const fd = this._formData(formOrFields);
      fd.append('mode', mode);
      if (measurements.length) fd.append('measurements', JSON.stringify(measurements));
      if (answers.length) fd.append('answers', JSON.stringify(answers));
      if (fresh) fd.append('fresh', 'true');
      const job = await this._fetch('/api/v1/generate/form?wait=25', { method: 'POST', body: fd });
      return this.waitFor(job, { onStatus, timeoutMs });
    }

    /** Up to three clarifying questions, each {id, question, why, suggestion, kind: number|choice|text, unit, options}. */
    clarify(formOrFields, { measurements = [] } = {}) {
      const fd = this._formData(formOrFields);
      if (measurements.length) fd.append('measurements', JSON.stringify(measurements));
      return this._fetch('/api/v1/clarify', { method: 'POST', body: fd });
    }

    /** Link to the printable measuring sheet (print at 100 %). */
    markerUrl() { return this.url('/api/v1/marker.svg'); }

    /** Distances in mm on a photo of the measuring sheet. segments: [[[x1, y1], [x2, y2]], ...] in the photo's own pixels. */
    measure(photo, segments) {
      const fd = new FormData();
      fd.append('photo', photo, photo.name || 'photo.jpg');
      fd.append('segments', JSON.stringify(segments));
      return this._fetch('/api/v1/measure', { method: 'POST', body: fd });
    }

    /** The AI changes a finished design as asked. Returns the new job. */
    async revise(jobId, feedback, { onStatus, timeoutMs = 300000 } = {}) {
      const job = await this._fetch('/api/v1/jobs/' + jobId + '/revise?wait=25', this._json({ feedback }));
      return this.waitFor(job, { onStatus, timeoutMs });
    }

    /** No AI: rebuild a finished design with new values for its adjustable sizes (job.result.design.parameters). */
    async tune(jobId, params, { onStatus, timeoutMs = 120000 } = {}) {
      const job = await this._fetch('/api/v1/jobs/' + jobId + '/tune?wait=25', this._json({ params }));
      return this.waitFor(job, { onStatus, timeoutMs });
    }

    job(id) { return this._fetch('/api/v1/jobs/' + id); }

    /** Poll until a job is done or failed. Resolves with the job; rejects with ReForm3DError if it failed. */
    async waitFor(job, { onStatus, timeoutMs = 300000 } = {}) {
      const t0 = Date.now();
      for (;;) {
        if (onStatus) onStatus(job.status, job);
        if (job.status === 'done') return this._absolutize(job);
        if (job.status === 'failed' || job.status === 'declined') throw new ReForm3DError(job.error || 'The part could not be made.', 422, job);
        if (Date.now() - t0 > timeoutMs) throw new ReForm3DError('This is taking longer than expected. Try again in a moment.', 408, job);
        await new Promise(r => setTimeout(r, 1000));
        job = await this.job(job.id);
      }
    }

    _absolutize(job) {
      const f = job.files || {};
      if (f.stl) f.stl.forEach(s => { s.url = this.abs(s.url); });
      ['glb', 'preview', 'zip', 'readme', 'code', 'drawing', 'fit_test'].forEach(k => { if (f[k]) f[k] = this.abs(f[k]); });
      return job;
    }
  }

  ReForm3D.Error = ReForm3DError;
  if (typeof module !== 'undefined' && module.exports) module.exports = ReForm3D;
  root.ReForm3D = ReForm3D;
})(typeof window !== 'undefined' ? window : globalThis);
