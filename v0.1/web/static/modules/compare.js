import { ico } from './icons.js';
import { COMPARE_KEY, COMPARE_MAX } from './constants.js';
import { S } from './state.js';
import { esc, haversineM, toast, _track } from './dom.js';
import { fmtDistance } from './panels/connectivity.js';
import { noiseTierFromDen, airTierFor, heatTierFor } from './panels/environment.js';
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
             transit:cnt('transit'),
             evCharging: cnt('ev_charging')},
    nearestHospital: (S.amenData && S.amenData.hospitals && S.amenData.hospitals.items && S.amenData.hospitals.items[0])
      ? {name:S.amenData.hospitals.items[0].name, distance_m:S.amenData.hospitals.items[0].distance_m}
      : null,
    noise: (S.envData && !S.envData.unavailable) ? {
      l_den: S.envData.l_den?.total, l_night: S.envData.l_night?.total, tier_den: S.envData.tier,
      // Source-split rows for the STREET NOISE report section. Rail is
      // captured here alongside the requested road/air split in case a
      // future row wants it — costs nothing to stash.
      den_road:   S.envData.l_den?.road   ?? null,
      night_road: S.envData.l_night?.road ?? null,
      den_air:    S.envData.l_den?.air    ?? null,
      night_air:  S.envData.l_night?.air  ?? null,
    } : null,
    // ENVIRONMENT & CLIMATE section — raw view renders these off S.eduData.{air,heat,quiet_zone}.
    aq:        (S.eduData.air        && !S.eduData.air.unavailable        && S.eduData.air.no2_ugm3 != null)
                 ? { no2_ugm3: S.eduData.air.no2_ugm3 } : null,
    heat:      (S.eduData.heat       && !S.eduData.heat.unavailable       && S.eduData.heat.day_class)
                 ? { day_class: S.eduData.heat.day_class } : null,
    quietZone: S.eduData.quiet_zone
                 ? { name: S.eduData.quiet_zone.name || null,
                     inside: !!S.eduData.quiet_zone.inside,
                     distance_m: S.eduData.quiet_zone.distance_m ?? null }
                 : null,
    // Nearest swim spot (raw view uses 3 km radius; per-row caption
    // announces that so the parent DAILY ESSENTIALS · 800 m header is
    // not misread as covering swim spots too).
    swim: (S.amenData && S.amenData.swimSpots)
      ? { count: S.amenData.swimSpots.count,
          nearest: (S.amenData.swimSpots.items && S.amenData.swimSpots.items[0])
            ? { name: S.amenData.swimSpots.items[0].name,
                info: S.amenData.swimSpots.items[0].info,
                distance_m: S.amenData.swimSpots.items[0].distance_m }
            : null }
      : null,
    // OFFICIAL SERVICES — one nearest office per admin card. Payload
    // for the section is d.others.bureaucracy.tiles[] as shaped by
    // app.core.others_admin.build; features[0] is the nearest per key.
    // Keys are hardcoded to the current 5 cards in cfg.others_admin_cards;
    // add new keys here if that list grows.
    admin: (() => {
      const tiles = (S.eduData?.others?.bureaucracy?.tiles) || [];
      const nearest = (key) => {
        const t = tiles.find(x => x.key === key);
        const f = t && t.features && t.features[0];
        return f ? { name: f.name, distance_m: f.distance_m } : null;
      };
      return {
        buergeramt:     nearest('buergeramt'),
        finanzamt:      nearest('finanzamt'),
        standesamt:     nearest('standesamt'),
        lea:            nearest('lea'),
        arbeitsagentur: nearest('arbeitsagentur'),
      };
    })(),
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
  // Row-level cell renderers for the new sections. Kept next to their
  // callers so future edits touch one contiguous block.
  const nameDistCell = (o) => o
    ? `<td>${esc(o.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(o.distance_m)})</span></td>`
    : `<td class="na">—</td>`;
  const noiseSourceCell = (v, isNight=false) => {
    if(v == null) return `<td class="na">—</td>`;
    // Night-time uses the same tier scale offset by +10 dB, matching the
    // total-L_Night rendering above (55/65/70 dB thresholds in `noiseTierFromDen`
    // are for L_DEN; L_Night is ~10 dB quieter for the same annoyance level).
    const tier = noiseTierFromDen(isNight ? v + 10 : v);
    return `<td><span class="noise-cell tier-${tier}">${v.toFixed(0)} dB</span></td>`;
  };
  const aqCell = (aq) => {
    if(!aq || aq.no2_ugm3 == null) return `<td class="na">—</td>`;
    return `<td><span class="noise-cell tier-${airTierFor(aq.no2_ugm3)}">${aq.no2_ugm3.toFixed(1)} µg/m³</span></td>`;
  };
  const heatCell = (h) => {
    if(!h || !h.day_class) return `<td class="na">—</td>`;
    // day_class is the raw Umweltatlas PET string, e.g.
    // "> 33 °C - <= 35 °C - mäßige Belastung". The trailing German
    // label (after the last " - ") is the human-readable level; that's
    // what the raw-view Summer-heat card foregrounds.
    const level = h.day_class.split(' - ').slice(-1)[0] || h.day_class;
    const tier = heatTierFor(h.day_class);
    // Unrecognised class strings (heatTierFor → 'unknown') would render as
    // a naked padded pill with no background — fall back to a plain cell.
    if(tier === 'unknown') return `<td>${esc(level)}</td>`;
    return `<td><span class="noise-cell tier-${tier}">${esc(level)}</span></td>`;
  };
  const quietZoneCell = (qz) => {
    if(!qz || (!qz.name && !qz.inside && qz.distance_m == null)) return `<td class="na">—</td>`;
    const name = esc(qz.name || 'Unnamed zone');
    const state = qz.inside
      ? 'You are inside'
      : (qz.distance_m != null ? `${qz.distance_m} m to edge` : '');
    return `<td>${name}${state ? ` <span style="color:var(--muted);font-weight:500">(${state})</span>` : ''}</td>`;
  };
  const swimCell = (s) => {
    if(!s || s.count == null) return `<td class="na">—</td>`;
    if(s.count === 0)         return `<td><span class="metric-num">0</span></td>`;
    const near = s.nearest;
    const info = near
      ? `<div style="margin-top:2px;font-size:12px;color:var(--muted);font-weight:500">${esc(near.name)}${near.info ? ` · ${esc(near.info)}` : ''}</div>`
      : '';
    return `<td><span class="metric-num">${s.count}</span>${info}</td>`;
  };

  // Aircraft-noise rows collapse when both compared addresses have no
  // aircraft dB reading — most of Berlin is far from any approach path,
  // so the row would otherwise be all em-dashes for most comparisons.
  const someHasAirDen   = list.some(s => s.noise && s.noise.den_air   != null);
  const someHasAirNight = list.some(s => s.noise && s.noise.night_air != null);

  const rows = [
    sect('Location & Schools'),
    row('District',        list.map(s=>cell(esc(s.address.district))).join('')),
    row('Catchment Grundschule', list.map(schoolCell).join('')),
    row('SESB bilingual',  list.map(s=>cell(s.school&&s.school.sesb_strand?`<span class="sesb-cell">${esc(s.school.sesb_strand)}</span>`:null)).join('')),
    row('Nearest international', list.map(s=>cell(s.intl?`${esc(s.intl.name)} <span style="color:var(--muted);font-weight:500">(${(s.intl.distance_m/1000).toFixed(1)} km)</span>`:null)).join('')),
    sect('Official services'),
    row('Bürgeramt · nearest',     list.map(s => nameDistCell(s.admin?.buergeramt)).join('')),
    row('Finanzamt · nearest',     list.map(s => nameDistCell(s.admin?.finanzamt)).join('')),
    row('Standesamt · assigned',   list.map(s => nameDistCell(s.admin?.standesamt)).join('')),
    row('LEA · Berlin',            list.map(s => nameDistCell(s.admin?.lea)).join('')),
    row('Arbeitsagentur · nearest',list.map(s => nameDistCell(s.admin?.arbeitsagentur)).join('')),
    sect('Kids & family within 800 m walk'),
    row('Kitas (registered)',    list.map(s=>cell(s.counts.kitas,'metric-num')).join('')),
    row('Playgrounds',           list.map(s=>cell(s.counts.playgrounds,'metric-num')).join('')),
    row('Parks / green',         list.map(s=>cell(s.counts.parks,'metric-num')).join('')),
    sect('Daily essentials within 800 m walk'),
    row('Supermarkets',          list.map(s=>cell(s.counts.supermarkets,'metric-num')).join('')),
    row('Drinking fountains',    list.map(s=>cell(s.counts.fountains,'metric-num')).join('')),
    row('Transit stops',         list.map(s=>cell(s.counts.transit,'metric-num')).join('')),
    row('EV charging',           list.map(s=>cell(s.counts.evCharging,'metric-num')).join('')),
    row('Swim spots · 3 km',     list.map(s => swimCell(s.swim)).join('')),
    sect('Medical services'),
    row('Pharmacies · 800 m',    list.map(s=>cell(s.counts.pharmacies,'metric-num')).join('')),
    row('Doctors · 800 m',       list.map(s=>cell(s.counts.gps,'metric-num')).join('')),
    row('Hospitals · 2 km',      list.map(s=>cell(s.counts.hospitals,'metric-num')).join('')),
    row('Nearest hospital',      list.map(s=>cell(s.nearestHospital?`${esc(s.nearestHospital.name)} <span style="color:var(--muted);font-weight:500">(${s.nearestHospital.distance_m} m)</span>`:null)).join('')),
    sect('Street noise (Berlin 2022 façade)'),
    row('L_DEN · 24 h',          list.map(s=>s.noise?`<td><span class="noise-cell tier-${noiseTierFromDen(s.noise.l_den)}">${s.noise.l_den!=null?s.noise.l_den.toFixed(0)+' dB':'—'}</span></td>`:`<td class="na">—</td>`).join('')),
    row('L_Night · 22–06',       list.map(s=>s.noise?`<td><span class="noise-cell tier-${noiseTierFromDen(s.noise.l_night==null?null:s.noise.l_night+10)}">${s.noise.l_night!=null?s.noise.l_night.toFixed(0)+' dB':'—'}</span></td>`:`<td class="na">—</td>`).join('')),
    row('L_DEN Road-traffic',    list.map(s => noiseSourceCell(s.noise?.den_road,   false)).join('')),
    row('L_Night Road-traffic',  list.map(s => noiseSourceCell(s.noise?.night_road, true )).join('')),
    someHasAirDen   ? row('L_DEN Aircraft',   list.map(s => noiseSourceCell(s.noise?.den_air,   false)).join('')) : null,
    someHasAirNight ? row('L_Night Aircraft', list.map(s => noiseSourceCell(s.noise?.night_air, true )).join('')) : null,
    sect('Environment & climate'),
    row('Air quality (NO₂)',     list.map(s => aqCell(s.aq)).join('')),
    row('Summer heat class',     list.map(s => heatCell(s.heat)).join('')),
    row('Nearest quiet zone',    list.map(s => quietZoneCell(s.quietZone)).join('')),
    sect('Connectivity'),
    row('Nearest S-Bahn',        list.map(s=>cell(s.connectivity?.sbahn         ? `${esc(s.connectivity.sbahn.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(s.connectivity.sbahn.distance_m)})</span>` : null)).join('')),
    row('Nearest U-Bahn',        list.map(s=>cell(s.connectivity?.ubahn         ? `${esc(s.connectivity.ubahn.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(s.connectivity.ubahn.distance_m)})</span>` : null)).join('')),
    row('Nearest tram',          list.map(s=>cell(s.connectivity?.tram          ? `${esc(s.connectivity.tram.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(s.connectivity.tram.distance_m)})</span>` : null)).join('')),
    row('Nearest regional rail', list.map(s=>cell(s.connectivity?.regional_rail ? `${esc(s.connectivity.regional_rail.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(s.connectivity.regional_rail.distance_m)})</span>` : null)).join('')),
    row('Nearest bus',           list.map(s=>cell(s.connectivity?.bus           ? `${esc(s.connectivity.bus.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(s.connectivity.bus.distance_m)})</span>` : null)).join('')),
    row('Airport (BER)',         list.map(s=>cell(s.connectivity?.airport       ? `${esc(s.connectivity.airport.name)} <span style="color:var(--muted);font-weight:500">(${fmtDistance(s.connectivity.airport.distance_m)})</span>` : null)).join('')),
  ].filter(Boolean).join('');
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
