import { _LENS_WITH_AI, _ICON_DOWNLOAD } from '../constants.js';
import { escapeHtml, _track } from '../dom.js';
import { getActiveLens } from './state.js';
import { readJson } from '../api.js';

export function _hasLensAI(slug) { return _LENS_WITH_AI.has(slug); }

// Idle state — call-to-action button.
export function renderLensAIIdle(lensLabel, audience) {
  const title = (audience || '').trim() || `Insight for the ${lensLabel || 'this'} lens`;
  return `
    <div class="lens-ai-idle">
      <div class="lens-ai-idle-copy">
        <div class="lens-ai-idle-title">${escapeHtml(title)}</div>
        <div class="lens-ai-idle-sub">Turn this address into a decision-ready ${escapeHtml(lensLabel || 'lens')} brief — headline verdict, criteria breakdown, and the standout facts to weigh.</div>
      </div>
      <button type="button" class="lens-ai-btn" data-action="generate">
        <span class="lens-ai-btn-label">Lens Insight</span>
        <span class="lens-ai-btn-arrow" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </span>
      </button>
    </div>`;
}

export function renderLensAISkeleton() {
  return `
    <div class="lens-ai-skel-summary">
      <div class="skel-line skel-w-90"></div>
      <div class="skel-line skel-w-75"></div>
    </div>
    <div class="lens-ai-skel-grid">
      <div class="skel-block"></div><div class="skel-block"></div><div class="skel-block"></div>
    </div>`;
}

export function _computeFitScore(sections) {
  const W = { green: 100, amber: 60, red: 20 };
  let sum = 0, n = 0;
  (sections || []).forEach(s => {
    if (W[s.verdict] != null) { sum += W[s.verdict]; n++; }
  });
  if (!n) return null;
  return Math.round(sum / n);
}

export function _fitBand(score) {
  if (score == null) return 'neutral';
  if (score >= 80) return 'strong';
  if (score >= 60) return 'balanced';
  if (score >= 40) return 'mixed';
  return 'challenged';
}

// Semi-circular gauge — 4 coloured band arcs.
export function _renderFitGauge(score) {
  const s = (typeof score === 'number') ? Math.max(0, Math.min(100, score)) : 50;
  const angle = -90 + (s / 100) * 180;
  const bandCls = 'band-' + _fitBand(s);
  return `<svg class="lens-ai-gauge ${bandCls}" viewBox="0 0 100 60" role="img"
               aria-label="Newcomer fit ${s} of 100 — ${_fitBand(s)}">
    <!-- Band arcs: coordinates pre-computed on a radius-40 arc from 180° to 0° -->
    <path class="lens-ai-gauge-band band-red"      d="M 10 50 A 40 40 0 0 1 37.64 12" fill="none" stroke-width="8" stroke-linecap="butt"/>
    <path class="lens-ai-gauge-band band-amber"    d="M 37.64 12 A 40 40 0 0 1 62.36 12" fill="none" stroke-width="8" stroke-linecap="butt"/>
    <path class="lens-ai-gauge-band band-lgreen"   d="M 62.36 12 A 40 40 0 0 1 82.36 26.48" fill="none" stroke-width="8" stroke-linecap="butt"/>
    <path class="lens-ai-gauge-band band-dgreen"   d="M 82.36 26.48 A 40 40 0 0 1 90 50" fill="none" stroke-width="8" stroke-linecap="butt"/>
    <!-- Needle -->
    <line class="lens-ai-gauge-needle" x1="50" y1="50" x2="50" y2="15"
          stroke-linecap="round" stroke-width="2.5"
          transform="rotate(${angle} 50 50)"/>
    <!-- Hub -->
    <circle class="lens-ai-gauge-hub" cx="50" cy="50" r="4"/>
  </svg>`;
}

export function renderLensAIBody(li, tileTierByKey, ctx) {
  if (!li || typeof li !== 'object') return '';
  ctx = ctx || {};
  const TIER_DOT = (v) => `<span class="tier-dot tier-${escapeHtml(v || 'unknown')}"></span>`;
  const SECTION_HEAD = { green: 'What works', amber: 'What to watch', red: "What won't", unknown: 'Neutral' };
  const tierOf = (k) => (tileTierByKey && tileTierByKey[k]) || 'unknown';
  const sections = li.sections || [];
  const fitScore = (typeof li.fit_score === 'number')
    ? li.fit_score : _computeFitScore(sections);
  const bezirk = (ctx.bezirk || '').trim();
  const ortsteil = (ctx.ortsteil || '').trim();
  const chipLabel = ortsteil || bezirk;
  const lensLabel = ctx.lensLabel || 'Newcomer';
  const ts = new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC';

  const buckets = { green: [], amber: [], red: [], unknown: [] };
  sections.forEach(s => (buckets[s.verdict] || buckets.unknown).push(s));
  const col = (verdict) => {
    const list = buckets[verdict] || [];
    if (!list.length) return '';
    return `<div class="lens-ai-col lens-ai-col-${verdict}">
      <div class="lens-ai-col-head">${SECTION_HEAD[verdict]} · ${list.length}</div>
      ${list.map(s => `
        <div class="lens-ai-sec">
          <div class="lens-ai-sec-title">${TIER_DOT(s.verdict)}${escapeHtml(s.title)}</div>
          <div class="lens-ai-sec-note">${escapeHtml(s.note || '')}</div>
        </div>`).join('')}
    </div>`;
  };
  const highlights = (arr, tone) => {
    if (!arr || !arr.length) return '';
    return `<ul class="lens-ai-hilights lens-ai-hilights-${tone}">${
      arr.map(h => `<li>${TIER_DOT(tierOf(h.tile))}<span class="hl-tile">${escapeHtml(h.tile)}</span><span class="hl-line">${escapeHtml(h.one_line)}</span></li>`).join('')
    }</ul>`;
  };
  const bezirkChip = chipLabel
    ? `<span class="lens-ai-bezirk" title="${escapeHtml([ortsteil, bezirk].filter(Boolean).join(' · '))}">${escapeHtml(chipLabel)}</span>` : '';
  const bandLabel = _fitBand(fitScore).toUpperCase();
  const scoreBlock = fitScore != null
    ? `<div class="lens-ai-fit" title="${escapeHtml(lensLabel)} fit — ${bandLabel.toLowerCase()}">
         ${_renderFitGauge(fitScore)}
         <div class="lens-ai-fit-nums">
           <span class="lens-ai-fit-n">${fitScore}</span>
           <span class="lens-ai-fit-cap">${escapeHtml(bandLabel)} · ${escapeHtml(lensLabel)} fit</span>
         </div>
       </div>` : '';
  const scoreCardBlock = scoreBlock
    ? `<aside class="lens-ai-score-card">${bezirkChip}${scoreBlock}</aside>`
    : (chipLabel
       ? `<aside class="lens-ai-score-card lens-ai-score-empty">${bezirkChip}</aside>`
       : '');
  const summaryText = (li.executive_summary || '')
    .replace(/^\s*["'‘“„«‹„"''‚‹]+\s*/, '');
  return `
    <button type="button" class="lens-ai-close-btn" data-action="close-report"
            aria-label="Dismiss insight report" title="Dismiss">✕</button>
    <div class="lens-ai-hero${scoreCardBlock ? '' : ' lens-ai-hero-solo'}">
      <div class="lens-ai-hero-copy">
        <div class="lens-ai-hero-rule"></div>
        <p class="lens-ai-summary">${escapeHtml(summaryText)}</p>
      </div>
      ${scoreCardBlock}
    </div>
    <div class="lens-ai-grid">${col('green')}${col('amber')}${col('red')}${col('unknown')}</div>
    ${(li.highlights_green && li.highlights_green.length) || (li.highlights_red && li.highlights_red.length)
       ? `<div class="lens-ai-hilights-wrap">
            ${highlights(li.highlights_green, 'green')}
            ${highlights(li.highlights_red, 'red')}
          </div>` : ''}
    <div class="lens-ai-footer-row">
      <button type="button" class="lens-ai-dl-btn" data-action="download-pdf"
              aria-label="Download insight as PDF" title="Download as PDF">
        <span class="lens-ai-dl-icon" aria-hidden="true">${_ICON_DOWNLOAD}</span>
        <span class="lens-ai-dl-label">Download PDF</span>
      </button>
      <div class="lens-ai-signature">
        <img class="lens-ai-signature-brand" src="/static/img/logo.png"
             alt="AddrLens" width="500" height="500">
        <span class="lens-ai-signature-dot">·</span>
        <span class="lens-ai-signature-meta">Berlin · generated ${escapeHtml(ts)}</span>
      </div>
    </div>`;
}

export function hydrateLensAIPanel(addr) {
  const active = getActiveLens();
  if (!_hasLensAI(active)) return;
  const panel = document.getElementById('lens-ai-panel');
  if (!panel) return;
  const lens = addr && addr.lens && addr.lens[active];
  if (!lens || lens.error || !Array.isArray(lens.tiles)) {
    panel.hidden = true; return;
  }
  const btn = panel.querySelector('.lens-ai-btn[data-action="generate"]');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    _track('lens_insight_click', { lens: active });
    panel.innerHTML = renderLensAISkeleton();
    panel.classList.add('lens-ai-loading');
    const a = addr.address || {};
    const payload = {
      lens: active,
      address: { lat: a.lat, lon: a.lon,
                 bezirk:   a.raw?.bez_name || a.raw?.bezirk   || '',
                 ortsteil: a.raw?.ort_name || a.raw?.ortsteil || '' },
      tiles: lens.tiles.map(t => ({
        key: t.key, label: t.label, tier: t.tier,
        rule: t.rule, numeric: t.numeric, caveat: t.caveat,
      })),
    };
    try {
      const r = await fetch('/api/lens_insight', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await readJson(r);
      const tierByKey = Object.fromEntries(lens.tiles.map(t => [t.key, t.tier || 'unknown']));
      const bezirk = a.raw?.bez_name || a.raw?.bezirk || '';
      const ortsteil = a.raw?.ort_name || a.raw?.ortsteil || '';
      panel.innerHTML = renderLensAIBody(data.lens_insight, tierByKey, {
        bezirk: bezirk, ortsteil: ortsteil, lensLabel: lens.label || active,
      });
      panel.classList.remove('lens-ai-loading');
      _bindLensAIDownload(panel, addr, lens, active);
      _bindLensAIClose(panel, addr, lens, active);
    } catch (e) {
      panel.classList.remove('lens-ai-loading');
      panel.innerHTML = renderLensAIIdle(lens.label || active, lens.audience) +
        `<div class="lens-ai-err">Insight generation failed. Please try again.</div>`;
      hydrateLensAIPanel(addr);
    }
  }, { once: true });
}

function _bindLensAIDownload(panel, addr, lens, active) {
  const btn = panel.querySelector('.lens-ai-dl-btn[data-action="download-pdf"]');
  if (!btn) return;
  let _pdfBusy = false;
  btn.addEventListener('click', () => {
    if (_pdfBusy) return;
    _pdfBusy = true;
    document.querySelectorAll('#lens-ai-print-root').forEach(n => n.remove());
    document.body.classList.remove('pdf-export-mode');

    const a = addr.address || {};
    const bezirk = a.raw?.bez_name || a.raw?.bezirk || 'Berlin';
    const ortsteil = a.raw?.ort_name || a.raw?.ortsteil || '';
    // NFKD splits characters like `ö` into `o` + combining-diaeresis
    // (U+0308); the regex strips the diacritic range (U+0300–U+036F).
    // Escape form is used deliberately — inline combining chars in the
    // source are invisible in most editors and get silently mangled by
    // copy/paste or IDE normalisation.
    const slug = (s) => String(s || '').toLowerCase()
      .normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    const ortsteilSlug = slug(ortsteil) || slug(bezirk) || 'berlin';
    const date = new Date().toISOString().slice(0, 10);
    const originalTitle = document.title;

    const root = document.createElement('div');
    root.id = 'lens-ai-print-root';
    root.dataset.exportAddress = [a.street, a.hnr, a.plz].filter(Boolean).join(' ');
    root.dataset.exportBezirk  = ortsteil || bezirk;
    root.dataset.exportLens    = lens.label || active;
    const clone = panel.cloneNode(true);
    clone.removeAttribute('id');
    clone.querySelectorAll('.lens-ai-dl-btn, .lens-ai-close-btn')
         .forEach(el => el.remove());
    root.appendChild(clone);
    document.body.appendChild(root);

    document.title = `AddrLens-${active}-${ortsteilSlug}-${date}`;
    document.body.classList.add('pdf-export-mode');

    const cleanup = () => {
      document.body.classList.remove('pdf-export-mode');
      document.title = originalTitle;
      const stray = document.getElementById('lens-ai-print-root');
      if (stray) stray.remove();
      window.removeEventListener('afterprint', cleanup);
      _pdfBusy = false;
    };
    window.addEventListener('afterprint', cleanup);
    requestAnimationFrame(() => window.print());
  });
}

function _bindLensAIClose(panel, addr, lens, active) {
  const btn = panel.querySelector('.lens-ai-close-btn[data-action="close-report"]');
  if (!btn) return;
  btn.addEventListener('click', () => {
    panel.classList.remove('lens-ai-loading');
    panel.innerHTML = renderLensAIIdle(lens.label || active, lens.audience);
    hydrateLensAIPanel(addr);
  }, { once: true });
}
