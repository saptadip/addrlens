import { _TITLE_SMALL } from './constants.js';

// -- Pure helpers (verbatim from the old IIFE) -----------------------------

export function esc(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
export function walkMin(m){return Math.round(m/62);}
export function shortUrl(u){ try{ return new URL(u).hostname.replace(/^www\./,''); } catch(e){ return u.length>40?u.slice(0,40)+'…':u; } }

// escapeHtml — alias to existing esc(); brief requires this name.
export function escapeHtml(s) { return esc(s == null ? '' : s); }

// Normalise a FastAPI error body into a short user-readable string.
// FastAPI serialises validation errors as `{ "detail": [ { "msg", "loc", ... }, ... ] }`
// — passing that array straight into esc() renders `[object Object]`. Any
// error-showing site that consumes JSON from /api/* should route through
// this helper first. Returns a plain string; caller still escapes for HTML.
//
//   payload            → returned string
//   ----------------------------------------------------------------
//   { detail: "text" } → "text"
//   { detail: [ { msg: "value_error", loc: ["query","address"] } ] }
//                      → "value_error (address)"  (or fallback shape)
//   { error: "text" }  → "text"
//   {}                 → fallback ("Something went wrong.")
export function formatApiError(payload, fallback){
  const fb = fallback || 'Something went wrong.';
  if (!payload || typeof payload !== 'object') return fb;
  const d = payload.detail;
  if (typeof d === 'string' && d) return d;
  if (Array.isArray(d) && d.length) {
    const first = d[0] || {};
    const msg = typeof first.msg === 'string' && first.msg ? first.msg : '';
    // loc is typically ["query", "<field>"] or ["body", "<field>", ...]
    let field = '';
    if (Array.isArray(first.loc) && first.loc.length) {
      const last = first.loc[first.loc.length - 1];
      if (typeof last === 'string') field = last;
    }
    if (msg && field) return `${msg} (${field})`;
    if (msg) return msg;
    if (field) return `Invalid input in ${field}.`;
    return fb;
  }
  if (typeof payload.error === 'string' && payload.error) return payload.error;
  return fb;
}

// Split a "Main (Gloss)" label so callers can style the parenthetical
// separately (muted brand accent). Falls back to {main: label, gloss: ''}.
export function splitLabelGloss(label){
  const m = (label || '').match(/^(.*?)\s*\((.*)\)\s*$/);
  return m ? { main: m[1].trim(), gloss: m[2].trim() }
           : { main: (label || '').trim(), gloss: '' };
}
export function labelWithGlossHtml(label){
  const { main, gloss } = splitLabelGloss(label);
  return gloss
    ? `${escapeHtml(main)} <span class="lm-gloss">(${escapeHtml(gloss)})</span>`
    : escapeHtml(main);
}

// Title-case for tile headers. English small-word exceptions are lowercased
// unless they're the first token. Words that already contain an uppercase
// letter pass through untouched — preserves German admin terms ("Bürgeramt"),
// initialisms ("NO₂", "LEA", "GESIx"), and hyphenated brand-cases ("Wi-Fi").
export function toTitleCase(s) {
  if (!s) return s;
  const capOne = w => w.replace(/^([^\p{L}]*)(\p{L})/u,
                                (_, p, c) => p + c.toUpperCase());
  const capHyphenated = tok => tok.split('-')
    .map(part => /[A-ZÄÖÜ]/.test(part) ? part : capOne(part))
    .join('-');
  const parts = s.split(/(\s+)/);
  let seenWord = false;
  return parts.map(tok => {
    if (/^\s+$/.test(tok)) return tok;
    const isFirst = !seenWord;
    seenWord = true;
    const low = tok.toLowerCase();
    if (!isFirst && _TITLE_SMALL.has(low.replace(/[^a-z]/g,''))) return low;
    return capHyphenated(tok);
  }).join('');
}

export function countUp(el,to,dur=900){if(matchMedia('(prefers-reduced-motion:reduce)').matches){el.textContent=to;return}
  const t0=performance.now();(function step(t){const p=Math.min(1,(t-t0)/dur);el.textContent=Math.round(to*(1-Math.pow(1-p,3)));if(p<1)requestAnimationFrame(step)})(t0);}

export function haversineM(la1,lo1,la2,lo2){
  const R=6371000, toRad=d=>d*Math.PI/180;
  const p1=toRad(la1), p2=toRad(la2), dp=toRad(la2-la1), dl=toRad(lo2-lo1);
  const h=Math.sin(dp/2)**2 + Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;
  return 2*R*Math.asin(Math.sqrt(h));
}

// -- Umami event tracker helper -------------------------------------------
// Umami's script exposes window.umami.track(name, data). It is injected by
// app/main.py only when UMAMI_WEBSITE_ID + UMAMI_SCRIPT_URL are set — so in
// local dev the object is undefined. Guard every call so the app runs
// unmodified when the tracker is absent. Failures inside umami.track (e.g.
// network hiccup) are swallowed — analytics must never break the UX.
export function _track(name, data){
  try {
    if (window.umami && typeof window.umami.track === 'function') {
      window.umami.track(name, data || undefined);
    }
  } catch (e) { /* analytics is best-effort */ }
}

// -- Tooltip portal (used by info-tips across many panels) ------------------
// When an <details class="info-tip"> opens, move its .info-body out of the
// details and into <body> with position:fixed. Escapes ancestor stacking
// contexts (.cell creates one via its entry-animation transform).
export function _reposTooltip(det){
  const body = det._portaledBody;
  if(!body) return;
  const sum = det.querySelector('summary').getBoundingClientRect();
  const spaceBelow = window.innerHeight - sum.bottom - 12;
  const spaceAbove = sum.top - 12;
  const needed = body.scrollHeight;
  body.style.position = 'fixed';
  body.style.left = 'auto';
  body.style.right = (window.innerWidth - sum.right) + 'px';
  body.style.zIndex = '9999';
  if(needed > spaceBelow && spaceAbove > spaceBelow){
    body.style.top = 'auto';
    body.style.bottom = (window.innerHeight - sum.top + 6) + 'px';
    body.style.maxHeight = (spaceAbove - 6) + 'px';
  } else {
    body.style.top = (sum.bottom + 6) + 'px';
    body.style.bottom = 'auto';
    body.style.maxHeight = (spaceBelow - 6) + 'px';
  }
}

// Any orphaned .info-body left in <body> from a previous render is dropped
// as soon as a fresh lookup starts.
export function dropOrphanTooltips(){
  document.body.querySelectorAll(':scope > .info-body').forEach(b => b.remove());
}

// Toast (bottom-right notification).
let _toastTimer = null;
export function toast(msg){
  let el=document.getElementById('_toast');
  if(!el){ el=document.createElement('div'); el.id='_toast'; el.className='toast'; document.body.appendChild(el); }
  el.textContent=msg; el.classList.add('show');
  clearTimeout(_toastTimer); _toastTimer=setTimeout(()=>el.classList.remove('show'), 1800);
}
