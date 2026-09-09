// AddrLens SPA bootstrap. Modules do the work — this file wires DOM events
// and kicks off initial view routing. Native ES modules `defer` by default,
// so all DOM references made at import top-level are safe.

import { dom, S, panels, othersState, strollerState } from './modules/state.js';
import { _track, formatApiError } from './modules/dom.js';
import { showStatus, clearResultState } from './modules/status.js';
import { fetchAmenities, fetchNoise } from './modules/api.js';
import { render } from './modules/panels/education.js';
import { drawAmenMap, drawOthersMap } from './modules/maps.js';
import { wireSuggest } from './modules/suggest.js';
import { installTooltipHandlers } from './modules/tooltips.js';
import { compareRefreshPill, showView, saveCurrent } from './modules/compare.js';
import { initLifeMode } from './modules/lens/index.js';

// -- Tab switching -----------------------------------------------------------
document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>{
  const target=t.dataset.tab;
  document.querySelectorAll('.tab').forEach(x=>{const on=x.dataset.tab===target;x.classList.toggle('active',on);x.setAttribute('aria-selected',on)});
  document.querySelectorAll('.panel').forEach(p=>{const on=p.id==='panel-'+target;p.classList.toggle('active',on);p.hidden=!on});
  // Leaflet was hidden — force a remeasure so tiles fill the container
  if(target==='edu' && S.mapRef) requestAnimationFrame(()=>S.mapRef.invalidateSize());
  // lazy: only fetch amenities when the user actually opens either tab.
  if((target==='amen'||target==='med') && S.lastCoord && !dom.$amen.dataset.loaded) fetchAmenities(S.lastCoord.lat,S.lastCoord.lon);
  if(panels[target]){
    if(!panels[target].mapRef && document.getElementById(panels[target].mapId))
      requestAnimationFrame(()=>drawAmenMap(target));
    else if(panels[target].mapRef)
      requestAnimationFrame(()=>panels[target].mapRef.invalidateSize());
  }
  if(target==='env'  && S.lastCoord && !dom.$env.dataset.loaded)  fetchNoise(S.lastCoord.lat,S.lastCoord.lon);
  if(target==='conn' && S.connMap) requestAnimationFrame(()=>S.connMap.invalidateSize());
  if(target==='others'){
    if(!othersState.mapRef && document.getElementById('map-others'))
      requestAnimationFrame(drawOthersMap);
    else if(othersState.mapRef)
      requestAnimationFrame(() => othersState.mapRef.invalidateSize());
  }
}));

// -- Button ripple effect ----------------------------------------------------
document.querySelector('.btn').addEventListener('mousemove',e=>{
  const r=e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty('--x',(e.clientX-r.left)+'px');
  e.currentTarget.style.setProperty('--y',(e.clientY-r.top)+'px');
});

// -- Chip suggestions --------------------------------------------------------
document.querySelectorAll('.chip').forEach(c=>c.addEventListener('click',()=>{dom.$q.value=c.dataset.q;_track('chip_click',{address:c.dataset.q});dom.$f.dispatchEvent(new Event('submit'))}));

// -- Address autocomplete ----------------------------------------------------
wireSuggest();

// -- Reset button — clear localStorage + reload ------------------------------
document.getElementById('reset-btn')?.addEventListener('click', () => {
  if(!confirm('Clear card order and saved comparisons? This cannot be undone.')) return;
  ['addrlens.cardOrder.v1', 'berlin-lens-compare-v1'].forEach(k => localStorage.removeItem(k));
  location.reload();
});

// -- Form submit -------------------------------------------------------------
dom.$f.addEventListener('submit',async ev=>{ev.preventDefault();const q=dom.$q.value.trim();if(!q)return;
  _track('lookup', { query_len: q.length });
  showStatus('loading', "Reading Berlin's open data…");
  try{
    const r=await fetch('/api/lookup?address='+encodeURIComponent(q));
    const d=await r.json();
    if(!r.ok){ clearResultState(); showStatus('error', formatApiError(d)); return; }
    render(d);   // render() calls showResults() once the panels are populated
  }catch(e){ clearResultState(); showStatus('error', 'Network error: '+e.message); }
});

// -- Save-to-compare button --------------------------------------------------
document.getElementById('save-btn').addEventListener('click', saveCurrent);

// -- Tooltip portal + Locality outside-click + modal Escape ------------------
installTooltipHandlers();

// -- Hash routing (compare view) ---------------------------------------------
window.addEventListener('hashchange', showView);

// -- Initial view routing ----------------------------------------------------
// Run last so every const/function referenced by showView → renderCompare is
// fully initialized (avoids a TDZ error when the page is loaded directly at
// #compare).
compareRefreshPill(); showView(); initLifeMode();

// -- Ship B: swap city-specific labels from /api/config ----------------------
// Fire-and-forget — the SSR-shipped Berlin defaults are the fallback if the
// fetch fails. Attribution list is composed from the server's per-dataset
// strings so each city gets legally-correct provenance without a rebuild.
fetch('/api/config').then(r=>r.ok?r.json():null).then(cfg=>{
  if(!cfg) return;
  const dn = cfg.display_name || 'Berlin';
  document.title = 'AddrLens';
  const $bn = document.getElementById('brand-name');
  if ($bn && !$bn.querySelector('img')) $bn.textContent = 'AddrLens';
  const $pill = document.getElementById('open-data-pill');
  if ($pill) $pill.textContent = `Open Data · ${dn}`;
  const $attrPrint = document.getElementById('footer-city-attr-print');
  if (cfg.attribution && $attrPrint) {
    const seen = new Set(), lines = [];
    for (const s of Object.values(cfg.attribution)) {
      if (!s || seen.has(s)) continue;
      seen.add(s); lines.push(s);
    }
    $attrPrint.textContent = `${dn} Open Data: ${lines.join(' · ')}.`;
  }
  const $attrOpen = document.getElementById('attribution-open');
  const $attrModal = document.getElementById('attribution-modal');
  const $attrClose = document.getElementById('attribution-close');
  if ($attrOpen && $attrModal && !$attrOpen.__wired) {
    $attrOpen.__wired = true;
    const openAttr = () => { $attrModal.hidden = false; };
    $attrOpen.addEventListener('click', (e) => {
      e.preventDefault();        // the <a href="#attribution"> would otherwise scroll
      openAttr();
    });
    $attrClose && $attrClose.addEventListener('click', () => { $attrModal.hidden = true; });
    $attrModal.addEventListener('click', (e) => {
      if (e.target === $attrModal) $attrModal.hidden = true;
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !$attrModal.hidden) $attrModal.hidden = true;
    });
    // Open on direct URL / hashchange too, so shared /#attribution links land
    // on the modal and don't just no-op scroll.
    window.addEventListener('hashchange', () => {
      if (location.hash === '#attribution') openAttr();
    });
    if (location.hash === '#attribution') openAttr();
  }
}).catch(()=>{ /* keep Berlin defaults; harmless */ });
