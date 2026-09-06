import { ico } from '../icons.js';
import { NOISE_TIER_LABEL } from '../constants.js';
import { dom, S, strollerState } from '../state.js';
import { esc } from '../dom.js';
import { applyCardOrder, enableDrag } from '../cards.js';
import { refreshSaveBtn } from '../compare.js';

export function emptyEnvPending(){
  dom.$env.innerHTML=`<div class="empty" style="margin-top:14px">
  <div class="row"><div class="icon-badge">${ico.waves}</div><div class="icon-badge">${ico.moon}</div></div>
  <p>Open the Environment tab to load street noise (day + night) for this address.</p></div>`;
}

export function strollerCardHtml(){
  return `<div class="cell tier-unknown" id="stroller-card" data-env-cat="stroller">
    <div class="cell-head"><div class="icon-badge">${ico.baby}</div><span class="cell-label">Stroller access</span>
      <span class="stroller-badge tier-badge tier-unknown">Fill inputs</span></div>
    <div class="stroller-form">
      <label>Floor <input id="stroller-floor" type="number" min="0" max="20" placeholder="e.g. 3"></label>
      <label>Lift? <select id="stroller-lift"><option value="">—</option><option value="yes">Yes</option><option value="no">No</option></select></label>
      <label class="chk"><input id="stroller-kwr" type="checkbox"> Kinderwagenraum</label>
    </div>
    <ul class="stroller-reasons"></ul>
    <div class="prov">Rule-based: floor × lift × Kinderwagenraum × nearest playground.</div>
  </div>`;
}

export function noiseCardsHtml(n){
  if(n.unavailable){
    return `<div class="cell"><div class="cell-head"><div class="icon-badge">${ico.waves}</div><span class="cell-label">Street noise</span></div>
      <p class="sub">${esc(n.reason || 'Noise data unavailable for this address.')}</p>
      <div class="prov">${esc(n.provenance || 'Geoportal Berlin / Strategische Lärmkarten 2022')}</div></div>`;
  }
  const den=n.l_den.total, ngt=n.l_night.total;
  // Night thresholds are ~10 dB stricter than day (WHO 45 vs 55). Shift the
  // night value UP by 10 before running through the day tier function so a
  // 58 dB night reads as 'orange' (bad), not 'green' via a naive < 55 test.
  const tDen=n.tier || 'unknown', tNgt=noiseTierFromDen(ngt==null?null:ngt+10);
  const sources=[
    ['road', 'Road traffic',       n.l_den.road,  n.l_night.road],
    ['rail', 'Rail (S+U-Bahn)',    n.l_den.rail,  n.l_night.rail],
    ['air',  'Aircraft',           n.l_den.air,   n.l_night.air],
  ].filter(([,,d,ng])=>d!=null||ng!=null);
  const srcRows=sources.map(([k,label,d,ng])=>`
    <li><span class="nm">${label}</span><span class="dist">${d!=null?d.toFixed(1)+' dB day':'—'} · ${ng!=null?ng.toFixed(1)+' dB night':'—'}</span></li>`).join('') || '<li class="none">No dominant source recorded.</li>';
  return `
    <div class="cell tier-${tDen}" data-env-cat="noise-den"><div class="cell-head"><div class="icon-badge">${ico.sun}</div><span class="cell-label">L<sub>DEN</sub> · 24 h weighted</span></div>
      <div class="metric-big"><span class="n">${den!=null?den.toFixed(0):'—'}</span><span class="cap">dB · ${NOISE_TIER_LABEL[tDen]}<br>WHO recommends &lt; 55 dB</span></div></div>
    <div class="cell tier-${tNgt}" data-env-cat="noise-night"><div class="cell-head"><div class="icon-badge">${ico.moon}</div><span class="cell-label">L<sub>Night</sub> · 22:00–06:00</span></div>
      <div class="metric-big"><span class="n">${ngt!=null?ngt.toFixed(0):'—'}</span><span class="cap">dB · ${NOISE_TIER_LABEL[tNgt]}<br>WHO recommends &lt; 45 dB</span></div></div>
    <div class="cell" data-env-cat="noise-sources"><div class="cell-head"><div class="icon-badge">${ico.waves}</div><span class="cell-label">Dominant sources at this façade</span></div>
      <ul class="amen-list">${srcRows}</ul>
      <p class="amen-more">Nearest façade measurement: ${n.distance_m} m from your address.</p>
      <div class="prov">${esc(n.provenance)}</div></div>`;
}

export function quietZoneCardHtml(qz){
  if(!qz) return '';
  const inside = !!qz.inside;
  const dLabel = inside ? 'You are inside' : `${qz.distance_m} m to nearest edge`;
  const sizeHa = qz.size_ha != null ? `${(+qz.size_ha).toFixed(1)} ha` : '—';
  const kind = qz.kind || '';
  return `<div class="cell" data-env-cat="quietzone">
    <div class="cell-head"><div class="icon-badge">${ico.quiet}</div><span class="cell-label">Quiet zone (nearest)</span></div>
    <h3 style="margin:6px 0 2px">${esc(qz.name || 'Unnamed zone')}</h3>
    <p class="sub">${esc(dLabel)} · ${sizeHa} · <span style="color:var(--muted)">${esc(kind)}</span></p>
    <div class="prov">Berlin BOD · §47d BImSchG (2018 designation).</div>
  </div>`;
}

export function protectionCardHtml(pr){
  if(!pr) return '';
  const m = pr.milieuschutz || {}, h = pr.heritage || {};
  const shieldSvg = ico.shield;
  const badge = (inside, cls, textOn, textOff, name) =>
    `<span class="protect-badge-inline b-${inside ? cls : 'neutral'}" title="${esc(name || '')}">${shieldSvg}${inside ? textOn : textOff}${inside && name ? ` · ${esc(name)}` : ''}</span>`;
  const anyInside = m.inside || h.inside;
  const body = anyInside
    ? `Rent-hike and unit-conversion rules protect this neighborhood from displacement. Landlords face extra approval steps to renovate or split units — usually a plus for long-term family renters.`
    : `This address isn't in a §172 BauGB protection zone. Rent and renovation rules follow standard Berlin tenancy law.`;
  const dateRow = m.inside && m.in_force ? `<p class="sub" style="margin:4px 0 0">Effective: ${esc(m.in_force)}${m.code?` · <span style="color:var(--muted)">${esc(m.code)}</span>`:''}</p>` : '';
  return `<div class="cell" data-env-cat="protection">
    <div class="cell-head"><div class="icon-badge">${shieldSvg}</div><span class="cell-label">Neighborhood protection</span></div>
    <div class="protect-badges">
      ${badge(m.inside, 'protect', 'Milieuschutz · Protected', 'Milieuschutz · Not in zone', m.area_name)}
      ${badge(h.inside, 'heritage', 'Heritage · Protected', 'Heritage · Not in zone', h.area_name)}
    </div>
    <p class="protect-body">${esc(body)}</p>
    ${dateRow}
    <div class="prov">Berlin BOD · §172 BauGB · <a href="https://www.berlin.de/sen/sbw/stadtdaten/geoportal/" target="_blank" rel="noopener">official designation ↗</a></div>
  </div>`;
}

export function streetTreesCardHtml(t){
  if(!t || t.count == null) return '';
  const fmtBands = t.age_bands
    ? `Young &lt; 20 yr: ${t.age_bands.young} · Mature: ${t.age_bands.mature} · Old &gt; 60 yr: ${t.age_bands.old}`
    : '—';
  const groups = Object.entries(t.group_mix || {})
    .sort((a,b) => b[1]-a[1])
    .map(([g,n]) => `${g}: ${n}`).join(' · ') || '—';
  const range = t.planting_range
    ? `${t.planting_range[0]}–${t.planting_range[1]}`
    : '—';
  const topN = (t.top_species || []).slice(0, 3)
    .map(sp => `${sp.name} (${sp.n})`).join(' · ') || '—';
  const canopyPct = t.crown_coverage_pct != null ? `${t.crown_coverage_pct}%` : '—';
  const canopyM2 = t.crown_coverage_m2 != null ? ` (${(+t.crown_coverage_m2).toLocaleString('en-US')} m²)` : '';
  return `<div class="cell" data-env-cat="trees">
    <div class="cell-head"><div class="icon-badge">${ico.tree}</div><span class="cell-label">Street trees · ${t.radius_m} m</span></div>
    <div class="metric-big"><span class="n">${t.count}</span><span class="cap">trees within ${t.radius_m} m</span></div>
    <ul class="amen-list" style="margin-top:8px">
      <li><span class="nm">Age mix</span><span class="dist">${esc(fmtBands.replace(/&lt;/g,'<').replace(/&gt;/g,'>'))}</span></li>
      <li><span class="nm">Species diversity</span><span class="dist">${t.unique_species} species · ${t.unique_genera} genera</span></li>
      <li><span class="nm">Group mix</span><span class="dist">${esc(groups)}</span></li>
      <li><span class="nm">Planting years</span><span class="dist">${esc(range)}</span></li>
      <li><span class="nm">Canopy coverage</span><span class="dist">${canopyPct} of query area${canopyM2}</span></li>
      <li><span class="nm">Tallest / avg height</span><span class="dist">${t.tallest_m != null ? t.tallest_m + ' m' : '—'} / ${t.avg_height_m != null ? t.avg_height_m + ' m' : '—'}</span></li>
      <li><span class="nm">Top species</span><span class="dist">${esc(topN)}</span></li>
    </ul>
    <div class="prov">Berlin BOD · Baumbestand (Straßenbäume).</div>
  </div>`;
}

// Phase 2 tier helpers: colour-code numeric readings + PET class strings.
export function airTierFor(no2){
  if(no2 == null) return 'unknown';
  if(no2 < 20)   return 'green';
  if(no2 < 30)   return 'amber';
  if(no2 < 40)   return 'orange';
  return 'red';                                  // ≥ 40 breaches EU annual limit
}
export function heatTierFor(dayClass){
  if(!dayClass) return 'unknown';
  const s = dayClass.toLowerCase();
  if(s.includes('keine belastung'))      return 'green';
  if(s.includes('geringe belastung'))    return 'green';
  if(s.includes('mäßige belastung'))     return 'amber';
  if(s.includes('erhöhte belastung'))    return 'orange';
  if(s.includes('sehr starke'))          return 'red';
  if(s.includes('starke belastung'))     return 'red';
  return 'unknown';
}

export function airQualityCardHtml(a){
  if(!a || a.unavailable){
    if(!a) return '';
    return `<div class="cell" data-env-cat="air"><div class="cell-head"><div class="icon-badge">${ico.waves}</div><span class="cell-label">Air quality (NO₂)</span></div>
      <p class="sub">${esc(a.reason || a.error || 'Air-quality data unavailable for this address.')}</p>
      <div class="prov">${esc(a.provenance || 'Berlin BOD · Umweltatlas Luft')}</div></div>`;
  }
  const tier = airTierFor(a.no2_ugm3);
  const no2 = a.no2_ugm3 != null ? a.no2_ugm3.toFixed(1) : '—';
  const idx = a.index_2020 != null ? a.index_2020.toFixed(2) : '—';
  const traffic = a.traffic_day != null ? Math.round(a.traffic_day).toLocaleString('en-US') : '—';
  return `<div class="cell tier-${tier}" data-env-cat="air">
    <div class="cell-head"><div class="icon-badge">${ico.waves}</div><span class="cell-label">Air quality (NO₂ · 2020)</span></div>
    <div class="metric-big"><span class="n">${no2}</span><span class="cap">µg/m³ · EU limit &lt; 40<br>${esc(a.street || 'nearest street')} · ${a.distance_m} m</span></div>
    <p class="amen-more" style="margin:6px 0 0">Traffic: ${traffic} vehicles/day · combined index ${idx}</p>
    <div class="prov">${esc(a.provenance)}</div>
  </div>`;
}

export function summerHeatCardHtml(h){
  if(!h || h.unavailable){
    if(!h) return '';
    return `<div class="cell" data-env-cat="heat"><div class="cell-head"><div class="icon-badge">${ico.sun}</div><span class="cell-label">Summer heat</span></div>
      <p class="sub">${esc(h.reason || h.error || 'Heat classification unavailable for this address.')}</p>
      <div class="prov">${esc(h.provenance || 'Berlin BOD · Umweltatlas Klima')}</div></div>`;
  }
  const tier = heatTierFor(h.day_class);
  const cls = h.day_class || 'unknown';
  const parts = cls.split(' - ');
  const range = parts.slice(0, 2).join(' – ');       // e.g. "> 33 °C – <= 35 °C"
  const level = parts.slice(-1)[0] || '';            // e.g. "mäßige Belastung"
  return `<div class="cell tier-${tier}" data-env-cat="heat">
    <div class="cell-head"><div class="icon-badge">${ico.sun}</div><span class="cell-label">Summer heat · PET day</span></div>
    <div class="metric-big"><span class="n" style="font-size:20px">${esc(level || '—')}</span><span class="cap">${esc(range)}<br>PET at 14:00 · residential block</span></div>
    <div class="prov">${esc(h.provenance)}</div>
  </div>`;
}

export function envExtraCardsHtml(d){
  if(!d) return '';
  // Ordered by natural card height so paired rows have similar bottoms.
  return streetTreesCardHtml(d.trees)
       + protectionCardHtml(d.protection)
       + airQualityCardHtml(d.air)
       + quietZoneCardHtml(d.quiet_zone)
       + summerHeatCardHtml(d.heat);
}

export function renderNoise(n){
  S.envData=n;
  dom.$env.innerHTML=`<div class="grid"><div class="stack two-per-row">${noiseCardsHtml(n)}${strollerCardHtml()}${envExtraCardsHtml(S.eduData)}</div></div>`;
  bindStrollerForm();
  renderStrollerCard();
  refreshSaveBtn();
  const envStack = dom.$env.querySelector('.stack');
  if(envStack){ applyCardOrder('env', envStack); enableDrag('env', envStack); }
}

export function noiseTierFromDen(v){
  if(v==null) return 'unknown';
  if(v<55) return 'green';
  if(v<65) return 'amber';
  if(v<70) return 'orange';
  return 'red';
}

// Stroller scoring — MIRROR of stroller_score() in server.py.
export function strollerScore(floor, lift, kwr, playgroundM){
  const reasons=[];
  if(floor==null || lift==null) return {tier:'unknown', reasons:[{kind:'info',text:'Enter floor and lift to score.'}]};
  let tier='green';
  if(lift)              reasons.push({kind:'good',text:`Floor ${floor} with lift — carry solved.`});
  else if(floor===0)    reasons.push({kind:'good',text:'Ground floor — no stairs (verify no entrance step).'});
  else if(floor<=2){ tier='amber'; reasons.push({kind:'warn',text:`Floor ${floor} without lift — manageable but tiring daily.`}); }
  else            { tier='red';   reasons.push({kind:'bad', text:`Floor ${floor} without lift — a hard no with a toddler.`}); }
  if(kwr){
    reasons.push({kind:'good',text:'Kinderwagenraum — leave the stroller downstairs.'});
    if(tier==='amber') tier='green';
    else if(tier==='red') tier='amber';
  }
  if(playgroundM==null)          reasons.push({kind:'info',text:'Playground data not loaded.'});
  else if(playgroundM<400)       reasons.push({kind:'good',text:`Playground ${playgroundM} m away — under 5 min walk.`});
  else if(playgroundM<800)       reasons.push({kind:'info',text:`Nearest playground ${playgroundM} m — about 10 min walk.`});
  else { reasons.push({kind:'warn',text:'No playground within 800 m.'}); if(tier==='green') tier='amber'; }
  return {tier, reasons};
}

export function nearestPlaygroundM(){
  const items = (S.amenData && S.amenData.playgrounds && S.amenData.playgrounds.items) || [];
  return items.length ? items[0].distance_m : null;
}
export function renderStrollerCard(){
  const el=document.getElementById('stroller-card'); if(!el) return;
  const floor = strollerState.floor==='' ? null : parseInt(strollerState.floor,10);
  const s = strollerScore(Number.isFinite(floor)?floor:null, strollerState.lift, strollerState.kwr, nearestPlaygroundM());
  const rowsHtml = s.reasons.map(r=>`<li class="r-${r.kind}">${esc(r.text)}</li>`).join('');
  const tierLabel = {green:'Easy',amber:'Workable',red:'Hard',unknown:'Fill inputs'}[s.tier];
  el.className = `cell tier-${s.tier}`;
  el.querySelector('.stroller-badge').textContent = tierLabel;
  el.querySelector('.stroller-badge').className = `stroller-badge tier-badge tier-${s.tier}`;
  el.querySelector('.stroller-reasons').innerHTML = rowsHtml;
}

export function bindStrollerForm(){
  const f=document.getElementById('stroller-floor'), l=document.getElementById('stroller-lift'), k=document.getElementById('stroller-kwr');
  if(!f) return;
  f.value = strollerState.floor;
  l.value = strollerState.lift===true?'yes':strollerState.lift===false?'no':'';
  k.checked = !!strollerState.kwr;
  f.addEventListener('input',()=>{ strollerState.floor=f.value; renderStrollerCard(); });
  l.addEventListener('change',()=>{ strollerState.lift = l.value==='yes'?true:l.value==='no'?false:null; renderStrollerCard(); });
  k.addEventListener('change',()=>{ strollerState.kwr=k.checked; renderStrollerCard(); });
}
