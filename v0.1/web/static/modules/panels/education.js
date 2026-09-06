import { ico } from '../icons.js';
import { EDU_STYLE } from '../constants.js';
import { dom, S, strollerState } from '../state.js';
import { esc, walkMin, escapeHtml, countUp, haversineM, dropOrphanTooltips, _track } from '../dom.js';
import { showResults } from '../status.js';
import { kitaDetailHtml } from '../details.js';
import { applyCardOrder, enableDrag } from '../cards.js';
import { renderConn } from './connectivity.js';
import { renderOthers } from './others.js';
import { drawMap, iconPin } from '../maps.js';
import { fetchAmenities, fetchNoise } from '../api.js';
import { emptyAmenPending } from './amenities.js';
import { emptyEnvPending } from './environment.js';
import { refreshSaveBtn } from '../compare.js';
import { renderAllPanels } from '../lens/index.js';

export function render(d){
  showResults();          // reveal tabs + panels now that a lookup has real data
  dropOrphanTooltips();   // any popover portaled from the previous lookup goes away
  S.eduData=d; S.eduSelected=null;
  const a=d.address,c=d.catchment||{},ss=d.schools||[],i=d.intl_grundschule,k=d.kitas||{};
  const _gesixTile = (d?.lens?.newcomer?.tiles || []).find(t => t.key === 'gesix_newcomer');
  const _gesix     = (_gesixTile && _gesixTile.metadata && _gesixTile.metadata.gesix) || null;
  const _gq        = (_gesix && _gesix.quintile_5) || 0;
  const _gTier     = _gq >= 1 && _gq <= 2 ? 'good' : _gq === 3 ? 'mid' : _gq >= 4 ? 'bad' : 'unknown';
  const _gLabel    = (_gesix && (_gesix.class_en || _gesix.class_de)) || '';
  const _gPlr      = (_gesix && _gesix.plr_name) || '';
  const _gRank     = (_gesix && _gesix.rang != null) ? _gesix.rang : null;
  const _gTotal    = (_gesix && _gesix.total)         ? _gesix.total : null;
  const _gRankVal = (_gRank != null && _gTotal)
    ? `${_gRank} of ${_gTotal} Planungsräume`
    : `Quintile ${_gq} of 5`;
  const _localityPill = _gq
    ? `<details class="info-tip locality-info-tip locality-tier-${_gTier}">
         <summary class="locality-pill"
                  aria-label="Locality: quintile ${_gq} of 5${_gLabel ? ', ' + _gLabel : ''}. Click for details.">
           <span class="locality-label">Locality</span>
           <span class="gesix-track gesix-track-inline" aria-hidden="true">${
             [1,2,3,4,5].map(i => {
               const grade = i <= 2 ? ' seg-good' : i === 3 ? ' seg-mid' : ' seg-bad';
               const on    = i === _gq ? ' active' : '';
               return `<span class="gesix-seg${grade}${on}"></span>`;
             }).join('')
           }</span>
         </summary>
         <div class="info-body details-block locality-info-body">
           <div class="det-row"><div class="det-label">Rank</div>
             <div class="det-val">${esc(_gRankVal)}</div></div>
           ${_gPlr ? `<div class="det-row"><div class="det-label">Planungsraum</div>
             <div class="det-val">${esc(_gPlr)}</div></div>` : ''}
           ${_gLabel ? `<div class="det-row"><div class="det-label">Band</div>
             <div class="det-val">${esc(_gLabel)}</div></div>` : ''}
           <div class="det-row"><div class="det-label">Source</div>
             <div class="det-val dim">Berlin 2022 GESIx socioeconomic band</div></div>
         </div>
       </details>`
    : '';
  const _histCtx = {
    lat: a.lat, lon: a.lon,
    street: a.street, hnr: a.hnr, plz: a.plz,
    bezirk: c.district || '',
    ortsteil: ((a.raw || {}).ort_name) || '',
  };
  const addr=`<div class="cell edu-cell addr-cell gesix-tier-${_gTier}" data-edu-cat="address"><div class="cell-head"><div class="icon-badge">${ico.home}</div><span class="cell-label">Address</span></div>
    <h3>${esc(a.street)} ${esc(a.hnr)}</h3><p class="sub">${esc(a.plz)} Berlin</p>
    <div class="badges">${c.district?`<span class="badge b-dist">${esc(c.district)}</span>`:''}${c.esb?`<span class="badge b-esb">ESB ${esc(c.esb)}</span>`:''}<button type="button" class="pill-btn addr-history-btn" data-hist='${esc(JSON.stringify(_histCtx))}' title="Get history in plain English">Get History</button>${_localityPill}</div>
    <div class="addr-history-body" hidden></div>
  </div>`;
  const ssSorted = (ss || []).map(s => ({
    ...s,
    _distance_m: (typeof s.lat === 'number' && typeof s.lon === 'number' && a && a.lat && a.lon)
      ? Math.round(haversineM(a.lat, a.lon, s.lat, s.lon)) : null,
  })).sort((x, y) => (x._distance_m ?? Infinity) - (y._distance_m ?? Infinity));
  const isFallback = c.schools_source === 'nearest' || ssSorted.some(s => s._fallback);
  const multi = ssSorted.length > 1;
  let groupLabel, groupHint;
  if (isFallback) {
    groupLabel = `Nearest Grundschulen · outside this ESB polygon`;
    groupHint  = `<div class="prov" style="margin-top:6px;font-style:italic">No public Grundschule sits inside Einschulbereich ${esc(c.esb || '?')}. The ${ssSorted.length} nearest schools are shown below as a proximity best-guess — confirm the assignment with the Bezirksschulamt (${esc(c.district || 'district')}).</div>`;
  } else if (multi) {
    groupLabel = `Grundschule catchment · ${ssSorted.length} schools in this ESB`;
    groupHint  = `<div class="prov" style="margin-top:6px;font-style:italic">This Einschulbereich contains ${ssSorted.length} public Grundschulen. The Bezirksschulamt allocates each child by proximity, siblings, and capacity — nearer is shown first as a proximity hint, not a guarantee.</div>`;
  } else {
    groupLabel = 'Assigned Grundschule';
    groupHint  = '';
  }
  const schools = ssSorted.length ? ssSorted.map((s, idx) => {
    const distTxt = s._distance_m != null
      ? ` · ${s._distance_m} m · ~${walkMin(s._distance_m)} min walk` : '';
    const cellLabel = (isFallback || multi)
      ? `${groupLabel} — #${idx + 1} (nearest first)` : groupLabel;
    const rowProv = isFallback
      ? 'Nearest public Grundschule · outside catchment polygon'
      : (multi ? 'Same catchment (ESB), one of several options'
               : 'Assigned by Einschulbereich');
    return `<div class="cell edu-cell" data-edu-cat="school-${idx}">
    <div class="cell-head"><div class="icon-badge">${ico.school}</div><span class="cell-label">${esc(cellLabel)}</span></div>
    <h3>${esc(s.name)}</h3><p class="sub">${esc((s.street||'')+' '+(s.hnr||''))}, ${esc(s.plz||'')}${distTxt}${s.website?` · <a href="${esc(s.website)}" target="_blank" rel="noopener">website</a>`:''}</p>
    <div class="badges"><span class="badge b-public">Public · öffentlich</span>${c.district?`<span class="badge b-dist">${esc(c.district)}</span>`:''}${s.sesb_strand?`<span class="badge b-sesb">SESB · ${esc(s.sesb_strand)}</span>`:''}</div>
    <div class="prov">${rowProv} · Schuljahr ${esc(s.school_year||'')}</div>
    ${idx === 0 ? groupHint : ''}
    </div>`;
  }).join('') : '';
  const kitaItems=(k.items||[]).slice(0,6).map((it,idx)=>{
    const details=kitaDetailHtml(it);
    const tip=details?`<details class="info-tip"><summary aria-label="More info">${ico.info}</summary><div class="info-body details-block">${details}</div></details>`:'';
    return `<li data-idx="${idx}" title="Highlight on map"><span class="nm">${esc(it.name)}</span><span class="dist">${it.distance_m} m · ~${walkMin(it.distance_m)} min</span>${tip}</li>`;
  }).join('') || '<li class="none">None within 800 m.</li>';
  const kitaMore=(k.count||0)>6?`<p class="amen-more">+${k.count-6} more within 800 m</p>`:'';
  const kitaProv=k.provenance?esc(k.provenance)+' · ':'';
  const kita=k.count==null?'':`<div class="cell edu-cell" data-edu-cat="kita">
    <div class="cell-head"><div class="icon-badge">${ico.baby}</div><span class="cell-label">Kitas · 10-min walk</span>${k.count>0?`<span class="chev">${ico.chev}</span>`:''}</div>
    <div class="metric-big"><span class="n" id="kitaN">0</span><span class="cap">registered within ~800 m</span></div>
    <div class="amen-body">
      <ul class="amen-list" style="margin-top:12px">${kitaItems}</ul>${kitaMore}
      <div class="prov">${kitaProv}Availability isn't in any open dataset — call to check spots.</div>
    </div></div>`;
  const intl=i?`<div class="cell edu-cell" data-edu-cat="intl"><div class="cell-head"><div class="icon-badge">${ico.globe}</div><span class="cell-label">Nearest international / bilingual</span></div>
    <h3>${esc(i.name)}</h3><p class="sub">${(i.distance_m/1000).toFixed(1)} km · ~${walkMin(i.distance_m)} min walk${i.website?` · <a href="${esc(i.website)}" target="_blank" rel="noopener">website</a>`:''}</p></div>`:'';
  const map=`<div class="map-cell"><div class="map-hint" id="eduHint">Click a card to plot its location</div><div id="map"></div></div>`;
  dom.$out.innerHTML=`<div class="grid"><div class="stack">${addr}${schools}${kita}${intl}</div>${map}</div>`;
  renderConn(d.connectivity, d.provenance, d.address);
  renderOthers(d);
  drawMap(d); const kn=document.getElementById('kitaN'); if(kn&&k.count!=null)countUp(kn,k.count);
  dom.$out.querySelectorAll('.edu-cell').forEach(cell=>cell.addEventListener('click',(e)=>{
    if(e.target.closest('.info-tip')) return;                       // tooltip toggles its own state
    if(e.target.closest('.amen-list li[data-idx]')) return;         // per-item click handled below
    if(e.target.closest('.addr-history-btn')) return;               // v0.1: Get History flow
    if(e.target.closest('.addr-history-body')) return;               // v0.1: inside history panel
    selectEduCategory(cell.dataset.eduCat);
  }));
  dom.$out.querySelectorAll('.addr-cell details.locality-info-tip').forEach(det => {
    det.addEventListener('toggle', () => {
      if (det.open) _track('gesix_click', { quintile: _gq || 0, tier: _gTier });
    });
  });
  // Get History button — v0.1 only. POST /api/history, render paragraph.
  const closeHistory = (body, btn) => {
    body.hidden = true;
    body.innerHTML = '';
    btn.hidden = false;                                              // show 'Get History' pill again
  };
  dom.$out.querySelectorAll('.addr-history-btn').forEach(btn => btn.addEventListener('click', async (e) => {
    e.stopPropagation();
    _track('get_history');
    const cell = btn.closest('.edu-cell');
    const body = cell.querySelector('.addr-history-body');
    let ctx;
    try { ctx = JSON.parse(btn.dataset.hist || '{}'); } catch { ctx = {}; }
    if (!ctx.lat || !ctx.lon) {
      body.innerHTML = `<div class="error" style="margin-top:8px">Missing coordinates.</div>`;
      body.hidden = false; return;
    }
    btn.disabled = true;
    body.hidden = false;
    body.innerHTML = `<div class="loading" style="margin-top:10px"><span class="spinner"></span> Composing history…</div>`;
    try {
      const qs = new URLSearchParams(ctx).toString();
      const r = await fetch(`/api/history?${qs}`);
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      body.innerHTML = `
        <button type="button" class="addr-history-close" aria-label="Close history">✕</button>
        <h4 class="addr-history-heading">History:</h4>
        <p class="addr-history-text">${esc(d.history || '')}</p>
        <p class="addr-history-foot"><span class="addr-history-foot-lbl">Disclaimer:</span> Generated by AI and may display incorrect information.</p>`;
      btn.hidden = true;
      const closeBtn = body.querySelector('.addr-history-close');
      if (closeBtn) closeBtn.addEventListener('click', (ev) => {
        ev.stopPropagation(); closeHistory(body, btn);
      });
    } catch (err) {
      body.innerHTML = `<div class="error" style="margin-top:8px">${esc(String(err.message || err))}</div>`;
    } finally {
      btn.disabled = false;
    }
  }));
  dom.$out.querySelectorAll('.edu-cell[data-edu-cat="kita"] .amen-list li[data-idx]').forEach(li=>li.addEventListener('click',(e)=>{
    e.stopPropagation();
    highlightEduKita(+li.dataset.idx);
  }));
  const eduStack = dom.$out.querySelector('.stack');
  if(eduStack){ applyCardOrder('edu', eduStack); enableDrag('edu', eduStack); }
  S.lastCoord={lat:a.lat,lon:a.lon}; dom.$amen.dataset.loaded=''; emptyAmenPending();
  dom.$env.dataset.loaded=''; emptyEnvPending();
  S.amenData=null; S.envData=null;                       // drop previous address's counts before save-btn recomputes
  strollerState.floor=''; strollerState.lift=null; strollerState.kwr=false;    // fresh building = fresh answers
  refreshSaveBtn();            // will show "Loading data…" until amen + noise land
  fetchAmenities(a.lat,a.lon); // eager: loads in parallel with user reading Education panel
  fetchNoise(a.lat,a.lon);     // eager: single WFS call, small payload
  renderAllPanels();           // Life Mode: refresh lens view for new address data
}

export function selectEduCategory(cat){
  if(!S.mapRef || !S.eduData) return;
  if(S.eduLayer){S.mapRef.removeLayer(S.eduLayer);S.eduLayer=null;S.kitaMarkers=[];}
  const wasSelected=S.eduSelected===cat;
  S.eduSelected=wasSelected?null:cat;
  dom.$out.querySelectorAll('.edu-cell').forEach(c=>c.classList.toggle('active',c.dataset.eduCat===S.eduSelected));
  const hint=document.getElementById('eduHint');
  const a=S.eduData.address;
  requestAnimationFrame(()=>{
    if(!S.mapRef) return;
    S.mapRef.invalidateSize();
    if(wasSelected){
      if(hint) hint.textContent='Click a card to plot its location';
      if(S.addressMarker) S.addressMarker.closePopup();
      const poly=S.eduData.catchment&&S.eduData.catchment.polygon;
      if(poly){try{S.mapRef.fitBounds(L.geoJSON(poly).getBounds().pad(0.1))}catch(e){S.mapRef.setView([a.lat,a.lon],14)}}
      else S.mapRef.setView([a.lat,a.lon],14);
      return;
    }
    if(cat==='address'){
      if(hint) hint.textContent='Your address';
      S.mapRef.setView([a.lat,a.lon],16);
      if(S.addressMarker) S.addressMarker.openPopup();
      return;
    }
    let points=[], style, label;
    if(cat.startsWith('school-')){
      const s=(S.eduData.schools||[])[+cat.slice(7)];
      if(!s || s.lat==null) return;
      const addrStr=[s.street,s.hnr].filter(Boolean).join(' ').trim();
      const info=[addrStr, s.plz].filter(Boolean).join(', ');
      points=[{lat:s.lat,lon:s.lon,name:s.name,info}]; style=EDU_STYLE.school; label='Assigned Grundschule';
    } else if(cat==='kita'){
      points=(S.eduData.kitas&&S.eduData.kitas.items||[]).map(k=>({lat:k.lat,lon:k.lon,name:k.name,distance_m:k.distance_m,info:k.info}));
      style=EDU_STYLE.kita; label='Kitas';
    } else if(cat==='intl'){
      const i=S.eduData.intl_grundschule;
      if(!i) return;
      points=[{lat:i.lat,lon:i.lon,name:i.name,distance_m:i.distance_m}];
      style=EDU_STYLE.intl; label='International';
    } else return;
    if(hint) hint.textContent=points.length>1?`${label}: ${points.length} plotted`:label;
    const markers=points.map(pt=>L.marker([pt.lat,pt.lon],{icon:iconPin(ico[style.icon],style.color)})
      .bindPopup(`<b>${esc(pt.name)}</b>${pt.distance_m?`<br>${pt.distance_m} m · ~${walkMin(pt.distance_m)} min walk`:''}${pt.info?`<br><span style="color:#6B7280">${esc(pt.info)}</span>`:''}`));
    S.eduLayer=L.featureGroup(markers).addTo(S.mapRef);
    if(cat==='kita') S.kitaMarkers=markers;
    const b=L.latLngBounds(points.map(pt=>[pt.lat,pt.lon])); b.extend([a.lat,a.lon]);
    try{S.mapRef.fitBounds(b.pad(0.2))}catch(e){}
    if(markers.length===1) markers[0].openPopup();
  });
}

export function highlightEduKita(idx){
  const openIt = () => {
    const m = S.kitaMarkers[idx];
    if(!m || !S.mapRef) return;
    S.mapRef.setView(m.getLatLng(), Math.max(S.mapRef.getZoom(), 16), {animate:true});
    m.openPopup();
  };
  if(S.eduSelected === 'kita'){
    openIt();
  } else {
    selectEduCategory('kita');
    requestAnimationFrame(()=>requestAnimationFrame(openIt));
  }
}
