/* Speak the problem instead of typing it.
   Uses the browser's own speech recognition (Chrome, Edge, Safari; not Firefox). The browser sends the audio to its speech service and returns text,
   so nothing here is stored by ReForm3D. The language comes from the page's language picker. */
import { t, speechLang, onLang } from './i18n.js';

const Rec = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);
const ICON = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><rect x="9" y="3" width="6" height="12" rx="3" fill="currentColor"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';

/** Put a microphone on a textarea or text input. Dictation is added to what is already there. */
export function attachMic(field) {
  if (!field || field.dataset.mic) return;
  field.dataset.mic = '1';
  const label = field.closest('label') || field.parentElement;
  label.classList.add('has-mic');
  const btn = document.createElement('button');
  btn.type = 'button'; btn.className = 'rf-mic'; btn.innerHTML = ICON; btn.setAttribute('aria-pressed', 'false');
  const note = document.createElement('p');
  note.className = 'rf-mic-note mono'; note.setAttribute('aria-live', 'polite');
  label.append(btn); label.after(note);

  let rec = null, listening = false, base = '', wanted = false;
  const words = () => { btn.setAttribute('aria-label', t(listening ? 'mic.stop' : 'mic.start')); btn.title = t(listening ? 'mic.stop' : 'mic.start'); };
  const say = (key, bad) => { note.textContent = key ? t(key) : ''; note.classList.toggle('rf-bad', !!bad); };
  const ui = on => { listening = on; btn.classList.toggle('on', on); btn.setAttribute('aria-pressed', String(on)); words(); };
  words();

  function stop() { wanted = false; if (rec) { try { rec.stop(); } catch (e) { /* already stopped */ } } }

  function start() {
    if (!Rec) { say('mic.unsupported', true); return; }
    rec = new Rec();
    rec.lang = speechLang(); rec.continuous = true; rec.interimResults = true; rec.maxAlternatives = 1;
    base = field.value && !/\s$/.test(field.value) ? field.value + ' ' : field.value;
    wanted = true; let heard = false, failed = false;
    rec.onstart = () => { ui(true); say('mic.listening'); };
    rec.onresult = e => {
      heard = true;
      const parts = [];
      for (let i = 0; i < e.results.length; i++) parts.push(String(e.results[i][0].transcript).trim());   // rebuilt from every result each time, so nothing is typed twice
      field.value = base + parts.filter(Boolean).join(' ');
      field.dispatchEvent(new Event('input', { bubbles: true }));
    };
    rec.onerror = e => {
      failed = true;
      const k = { 'not-allowed': 'mic.denied', 'service-not-allowed': 'mic.denied', 'no-speech': 'mic.nospeech', 'network': 'mic.network', 'language-not-supported': 'mic.nolang' }[e.error];
      if (e.error === 'aborted') { failed = false; return; }
      say(k || 'mic.network', true);
    };
    rec.onend = () => { ui(false); if (!failed) { if (heard) say(''); else if (wanted) say('mic.nospeech', true); } wanted = false; rec = null; };
    try { rec.start(); } catch (e) { ui(false); say('mic.network', true); }
  }

  btn.addEventListener('click', () => { if (listening) stop(); else { say(''); start(); } });
  onLang(() => { if (listening) stop(); words(); if (note.textContent) say(''); });
}

export function initSpeech() { attachMic(document.getElementById('what')); }
