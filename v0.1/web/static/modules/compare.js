import { ico } from './icons.js';
import { COMPARE_KEY, COMPARE_MAX } from './constants.js';
import { S } from './state.js';
import { esc, haversineM, toast, _track } from './dom.js';
import { fmtDistance } from './panels/connectivity.js';
import { noiseTierFromDen } from './panels/environment.js';
import { amenHasErrors } from './panels/amenities.js';
import { renderLensCompare } from './lens/index.js';

export function compareLoad(){ try{ return JSON.parse(localStorage.getItem(COMPARE_KEY)||'[]'); } catch(e){ return []; } }
export function compareSave(list){ try{ localStorage.setItem(COMPARE_KEY, JSON.stringify(list)); } catch(e){ alert('Storage unavailable — comparison disabled for this session.'); } }
export function compareRefreshPill(){
  const list=compareLoad();
  const pill=document.getElementById('compare-pill'), n=document.getElementById('compare-count');
  n.textContent=list.length;
  pill.hidden = list.length===0;
}
export function snapshotId(a){ return `${a.street}-${a.hnr}-${a.plz}`.toLowerCase().replace(/\s+/g,'-'); }

export function buildSnapshot(){
  if(!S.eduData||!S.eduData.address) return null;
  const a=S.eduData.address, c=S.eduData.catchment||{}, s=(S.eduData.schools||[])[0], i=S.eduData.intl_grundschule, k=S.eduData.kitas||{};
  const cnt=(cat)=> (S.amenData && S.amenData[cat]) ? S.amenData[cat].count : null;
  const schoolDist = s && s.lat!=null ? Math.round(haversineM(a.lat, a.lon, s.lat, s.lon)) : null;
  return {
    id: snapshotId(a),
    savedAt: Date.now(),
    address: {street:a.street, hnr:a.hnr, plz:a.plz, district:c.district, lat:a.lat, lon:a.lon},
    catchment: {esb:c.esb, district:c.district},
    school: s ? {name:s.name, sesb_strand:s.sesb_strand, school_year:s.school_year, distance_m:schoolDist} : null,
    intl: i ? {name:i.name, distance_m:i.distance_m} : null,
    counts: {kitas:k.count, playgrounds:cnt('playgrounds'), parks:cnt('parks'),
             pharmacies:cnt('pharmacies'), supermarkets:cnt('supermarkets'),
             gps:cnt('gps'), hospitals:cnt('hospitals'), fountains:cnt('fountains'),
             transit:cnt('transit')},
    nearestHospital: (S.amenData && S.amenData.hospitals && S.amenData.hospitals.items && S.amenData.hospitals.items[0])
      ? {name:S.amenData.hospitals.items[0].name, distance_m:S.amenData.hospitals.items[0].distance_m}
      : null,
    noise: (S.envData && !S.envData.unavailable) ? {
      l_den: S.envData.l_den?.total, l_night: S.envData.l_night?.total, tier_den: S.envData.tier,
    } : null,
    connectivity: S.eduData.connectivity || null,
    lens: S.eduData.lens || null,
  };
}

export function saveCurrent(){
  const snap=buildSnapshot(); if(!snap) return;
  const list=compareLoad();
  if(list.find(x=>x.id===snap.id)){ toast('Already saved'); return; }
  if(list.length>=COMPARE_MAX){ alert(`Comparison holds up to ${COMPARE_MAX} addresses. Remove one first.`); return; }
  list.push(snap); compareSave(list); compareRefreshPill(); refreshSaveBtn();
  toast('Saved ✓');
}

export function refreshSaveBtn(){
  const btn=document.getElementById('save-btn'); if(!btn) return;
  const snap=buildSnapshot();
  if(!snap){ btn.hidden=true; return; }
  btn.hidden=false;
  const already=compareLoad().find(x=>x.id===snap.id);
  if(already){ btn.textContent='✓ Added to Compare'; btn.disabled=true; return; }
  // Ready if both fetches landed AND (no OSM errors OR we've already retried once).
  const ready = S.amenData && S.envData && (!amenHasErrors() || S.amenAttempts>=2);
  btn.textContent = ready ? '+ Add to Compare' : 'Loading data…';
  btn.disabled = !ready;
}

export function showView(){
  const isCompare = location.hash === '#compare';
  if (isCompare) _track('compare_open', { count: compareLoad().length });
  document.getElementById('view-main').hidden = isCompare;
  document.getElementById('view-compare').hidden = !isCompare;
  if(isCompare) renderCompare();
}

export function renderCompare(){
  const list=compareLoad();
  const $c=document.getElementById('compare-content');
  const header=`<div class="compare-header">
    <h2>Comparison board</h2>
    <div class="compare-actions">
      ${list.length?`<button class="pill-btn" id="export-pdf-btn" title="Print or Save as PDF">↓ Export PDF</button>`:''}
      ${list.length?`<button class="pill-btn" id="clear-all-btn">Clear all</button>`:''}
      <a class="pill-btn pill-btn-brand" href="#">← Back to lookup</a>
    </div></div>`;
  const printHeader = list.length ? `<div class="print-only print-header">
    <div class="print-header-row">
      <div class="print-header-brand">
        <img src="/static/img/logo.png" alt="AddrLens" class="print-header-logo">
        <div class="print-header-title-group">
          <h1 class="print-header-title">Comparison Report</h1>
          <p class="print-header-subtitle">Berlin · Open Data + OpenStreetMap</p>
        </div>
      </div>
      <div class="print-header-meta">
        <span class="print-header-date">${new Date().toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric'})}</span>
        <span class="print-header-site">addrlens.de</span>
      </div>
    </div>
    <div class="print-header-rule" aria-hidden="true"></div>
  </div>` : '';
  if(!list.length){
    $c.innerHTML=`${header}<div class="compare-empty">
      <div class="icon-badge">${ico.home}</div>
      <p>No saved addresses yet. Look one up, then click "Save to comparison" to add it here — up to ${COMPARE_MAX} side by side.</p></div>`;
    return;
  }
  // Life Mode branch: render the 7×N dot matrix instead of the raw table.
  if (document.body.classList.contains('life-mode')) {
    $c.innerHTML = `${header}${renderLensCompare(list)}`;
    const clr=document.getElementById('clear-all-btn');
    if(clr) clr.addEventListener('click',()=>{
      if(confirm('Remove all saved addresses?')){ compareSave([]); compareRefreshPill(); refreshSaveBtn(); renderCompare(); }
    });
    const pdf=document.getElementById('export-pdf-btn');
    if(pdf) pdf.addEventListener('click',()=>{
      const originalTitle=document.title;
      document.title='AddrLensComparisonReport';
      const restore=()=>{ document.title=originalTitle; window.removeEventListener('afterprint',restore); };
      window.addEventListener('afterprint',restore);
      window.print();
    });
    return;
  }
  const cols=list.map((snap,idx)=>{
    const a=snap.address;
    return `<th class="addr-col">
      <button class="col-remove" data-id="${esc(snap.id)}" title="Remove">✕</button>
      <span class="addr-title">${esc(a.street)} ${esc(a.hnr)}</span>
      <span class="addr-sub">${esc(a.plz)} ${esc(a.district||'')}</span></th>`;
  }).join('');
  const row = (label, cells, cls='') => `<tr class="${cls}"><th>${label}</th>${cells}</tr>`;
  const sect = (label) => `<tr class="section-row"><th colspan="${list.length+1}">${label}</th></tr>`;
  const cell = (v, cls='') => v==null||v==='' ? `<td class="na">—</td>` : `<td class="${cls}">${v}</td>`;
  const noiseCell = (n) => {
    if(!n||n.l_den==null) return `<td class="na">—</td>`;
    const t = n.tier_den || 'unknown';
    return `<td><span class="noise-cell tier-${t}">${n.l_den.toFixed(0)} dB<span class="noise-sub">/ ${n.l_night!=null?n.l_night.toFixed(0)+' night':'—'}</span></span></td>`;
  };
  const schoolCell = (s) => {
    if(!s.school) return `<td class="na">—</td>`;
    const dist = s.school.distance_m!=null ? ` <span style="color:var(--muted);font-weight:500">(${s.school.distance_m} m · ~${Math.round(s.school.distance_m/80)} min walk)</span>` : '';
    return `<td>${esc(s.school.name)}${dist}</td>`;
  };
  const rows = [
    sect('Location & Schools'),
    row('District',        list.map(s=>cell(esc(s.address.district))).join('')),
    row('Catchment Grundschule', list.map(schoolCell).join('')),
    row('SESB bilingual',  list.map(s=>cell(s.school&&s.school.sesb_strand?`<span class="sesb-cell">${esc(s.school.sesb_strand)}</span>`:null)).join('')),
    row('Nearest international', list.map(s=>cell(s.intl?`${esc(s.intl.name)} <span style="color:var(--muted);font-weight:500">(${(s.intl.distance_m/1000).toFixed(1)} km)</span>`:null)).join('')),
    sect('Kids & family within 800 m walk'),
    row('Kitas (registered)',    list.map(s=>cell(s.counts.kitas,'metric-num')).join('')),
    row('Playgrounds',           list.map(s=>cell(s.counts.playgrounds,'metric-num')).join('')),
    row('Parks / green',         list.map(s=>cell(s.counts.parks,'metric-num')).join('')),
    sect('Daily essentials within 800 m walk'),
    row('Supermarkets',          list.map(s=>cell(s.counts.supermarkets,'metric-num')).join('')),
    row('Drinking fountains',    list.map(s=>cell(s.counts.fountains,'metric-num')).join('')),
    row('Transit stops',         list.map(s=>cell(s.counts.transit,'metric-num')).join('')),
    sect('Medical services'),
    row('Pharmacies · 800 m',    list.map(s=>cell(s.counts.pharmacies,'metric-num')).join('')),
    row('Doctors · 800 m',       list.map(s=>cell(s.counts.gps,'metric-num')).join('')),
    row('Hospitals · 2 km',      list.map(s=>cell(s.counts.hospitals,'metric-num')).join('')),
    row('Nearest hospital',      list.map(s=>cell(s.nearestHospital?`${esc(s.nearestHospital.name)} <span style="color:var(--muted);font-weight:500">(${s.nearestHospital.distance_m} m)</span>`:null)).join('')),
    sect('Street noise (Berlin 2022 façade)'),
    row('L_DEN · 24 h',          list.map(s=>s.noise?`<td><span class="noise-cell tier-${noiseTierFromDen(s.noise.l_den)}">${s.noise.l_den!=null?s.noise.l_den.toFixed(0)+' dB':'—'}</span></td>`:`<td class="na">—</td>`).join('')),
    row('L_Night · 22–06',       list.map(s=>s.noise?`<td><span class="noise-cell tier-${noiseTierFromDen(s.noise.l_night==null?null:s.noise.l_night+10)}">${s.noise.l_night!=null?s.noise.l_night.toFixed(0)+' dB':'—'}</span></td>`:`<td class="na">—</td>`).join('')),
    sect('Connectivity'),
    row('Nearest S-Bahn',        list.map(s=>cell(s.connectivity?.sbahn         ? `${esc(s.connectivity.sbahn.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(s.connectivity.sbahn.distance_m)})</span>` : null)).join('')),
    row('Nearest U-Bahn',        list.map(s=>cell(s.connectivity?.ubahn         ? `${esc(s.connectivity.ubahn.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(s.connectivity.ubahn.distance_m)})</span>` : null)).join('')),
    row('Nearest tram',          list.map(s=>cell(s.connectivity?.tram          ? `${esc(s.connectivity.tram.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(s.connectivity.tram.distance_m)})</span>` : null)).join('')),
    row('Nearest regional rail', list.map(s=>cell(s.connectivity?.regional_rail ? `${esc(s.connectivity.regional_rail.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(s.connectivity.regional_rail.distance_m)})</span>` : null)).join('')),
    row('Nearest bus',           list.map(s=>cell(s.connectivity?.bus           ? `${esc(s.connectivity.bus.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(s.connectivity.bus.distance_m)})</span>` : null)).join('')),
    row('Airport (BER)',         list.map(s=>cell(s.connectivity?.airport       ? `${esc(s.connectivity.airport.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(s.connectivity.airport.distance_m)})</span>` : null)).join('')),
  ].join('');
  $c.innerHTML=`${header}${printHeader}<div class="compare-wrap"><table class="compare-table">
    <thead><tr><th class="metric-col"></th>${cols}</tr></thead>
    <tbody>${rows}</tbody></table></div>`;
  $c.querySelectorAll('.col-remove').forEach(b=>b.addEventListener('click',()=>{
    const list=compareLoad().filter(x=>x.id!==b.dataset.id);
    compareSave(list); compareRefreshPill(); refreshSaveBtn(); renderCompare();
  }));
  const clr=document.getElementById('clear-all-btn');
  if(clr) clr.addEventListener('click',()=>{
    if(confirm('Remove all saved addresses?')){ compareSave([]); compareRefreshPill(); refreshSaveBtn(); renderCompare(); }
  });
  const pdf=document.getElementById('export-pdf-btn');
  if(pdf) pdf.addEventListener('click',()=>{
    const originalTitle=document.title;
    document.title='AddrLensComparisonReport';
    const restore=()=>{ document.title=originalTitle; window.removeEventListener('afterprint',restore); };
    window.addEventListener('afterprint',restore);
    window.print();
  });
}
