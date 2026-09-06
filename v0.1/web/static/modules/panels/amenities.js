import { ico } from '../icons.js';
import { AMEN, tabOf } from '../constants.js';
import { dom, S, panels } from '../state.js';
import { esc, walkMin, dropOrphanTooltips } from '../dom.js';
import { fmtDistance } from './connectivity.js';
import { amenDetailHtml } from '../details.js';
import { applyCardOrder, enableDrag } from '../cards.js';
import { drawAmenMap, iconPin, amenPin } from '../maps.js';

export function amenHasErrors(){
  if(!S.amenData) return true;
  return Object.values(S.amenData).some(b => b && b.error);
}

export function emptyAmenPending(){
  ['amen','med'].forEach(t=>{ if(panels[t].mapRef){panels[t].mapRef.remove();panels[t].mapRef=null} });
  dom.$amen.innerHTML=`<div class="empty" style="margin-top:14px">
  <div class="row"><div class="icon-badge">${ico.playground}</div><div class="icon-badge">${ico.tree}</div><div class="icon-badge">${ico.transit}</div></div>
  <p>Open the Amenities tab to load playgrounds, parks, supermarkets, drinking fountains, and transit stops within 800 m.</p></div>`;
  dom.$med.innerHTML=`<div class="empty" style="margin-top:14px">
  <div class="row"><div class="icon-badge">${ico.pharmacy}</div><div class="icon-badge">${ico.gp}</div><div class="icon-badge">${ico.hospital}</div></div>
  <p>Open the Medical tab to load pharmacies, GPs and hospitals near this address.</p></div>`;
}

function _amenCardHtml(entry){
  const [k,label,icon,,cap]=entry;
  const rangeCap=cap||'within ~800 m';
  const rangeShort=cap ? cap.replace(/^within ~?/, '') : '800 m';
  const b=S.amenData[k]||{count:0,items:[]};
  if(b.error) return `<div class="cell amen-cell" data-cat="${k}" style="cursor:default">
    <div class="amen-tile-top"><div class="icon-badge">${icon}</div></div>
    <span class="cell-label">${label}</span>
    <p class="sub" style="color:var(--danger)">Overpass error: ${esc(b.error)}</p></div>`;
  const items=(b.items||[]).slice(0,6).map((it,i)=>{
    const details=amenDetailHtml(k, it);
    const tip=details?`<details class="info-tip"><summary aria-label="More info">${ico.info}</summary><div class="info-body details-block">${details}</div></details>`:'';
    const dist = it.distance_m != null
      ? `${it.distance_m} m · ~${walkMin(it.distance_m)} min`
      : esc(it.info || '');
    return `<li data-idx="${i}" title="Highlight on map"><span class="nm">${esc(it.name)}</span><span class="dist">${dist}</span>${tip}</li>`;
  }).join('') || `<li class="none">None within ${rangeShort}.</li>`;
  const more=(b.count||0)>6 && typeof b.count === 'number' ?`<p class="amen-more">+${b.count-6} more within ${rangeShort}</p>`:'';
  return `<div class="cell amen-cell" data-cat="${k}">
    <div class="amen-tile-top">
      <div class="icon-badge">${icon}</div>
      <div class="metric-big"><span class="n">${b.count==null?'—':b.count}</span></div>
    </div>
    <div class="cell-caption">
      <span class="cell-label">${label}</span>
      <span class="amen-tag">${rangeCap}</span>
    </div>
    <div class="amen-body">
      <ul class="amen-list">${items}</ul>${more}
      <div class="prov">${esc(b.provenance || '© OpenStreetMap contributors (ODbL)')}</div>
    </div></div>`;
}

function _renderAmenPanel(tab){
  const p=panels[tab];
  p.selected=null;
  if(p.mapRef){p.mapRef.remove();p.mapRef=null}
  const entries=AMEN.filter(e=>tabOf(e[0])===tab);
  const cards=entries.map(_amenCardHtml).join('');
  p.$el.innerHTML=`<div class="grid">
    <div class="stack tiles-grid two-per-row">${cards}<div class="amen-modal" id="amen-modal-${tab}" hidden></div></div>
    <div class="map-cell amen-map-cell"><div class="map-hint" id="${p.hintId}">Click a tile for details</div><div id="${p.mapId}"></div></div>
  </div>`;
  if(p.$el.closest('.panel')?.classList.contains('active')) drawAmenMap(tab);
  p.$el.querySelectorAll('.amen-cell').forEach(cell=>cell.addEventListener('click',(e)=>{
    if(e.target.closest('.info-tip')) return;
    if(e.target.closest('.amen-list li[data-idx]')) return;
    const cat=cell.dataset.cat, b=S.amenData[cat];
    if(!b) return;
    openAmenModal(tab, cat);
    selectAmenCategory(cat);
  }));
  const modal=document.getElementById('amen-modal-'+tab);
  modal.addEventListener('click',(e)=>{
    if(e.target.closest('.amen-modal-close')){ closeAmenModal(tab); return; }
    const li=e.target.closest('.amen-list li[data-idx]');
    if(li){ e.stopPropagation(); const cat=li.dataset.cat; highlightAmenItem(cat, +li.dataset.idx); }
  });
  const stackEl = p.$el.querySelector('.stack');
  if(stackEl){ applyCardOrder(tab, stackEl); enableDrag(tab, stackEl); }
}

// Phase-1 tiles come from /api/lookup, not /api/amenities. Bridge them into
// S.amenData so they render through the same tile+modal pipeline.
function _hydrateLookupTiles(d){
  if(!d) return;
  S.amenData = S.amenData || {};
  const fr = d.fire_rescue;
  if(fr && fr.nearest){
    S.amenData.fireRescue = {
      count: fmtDistance(fr.nearest.distance_m),
      items: (fr.top3 || []).map(s => ({
        name: s.name,
        lat: s.lat, lon: s.lon,
        distance_m: s.distance_m,
        info: `${s.type === 'BF' ? 'Professional' : 'Volunteer'}${s.address ? ' · ' + s.address : ''}`,
        _phone_bf: s.phone_bf, _phone_ff: s.phone_ff, _zone: s.zone_code,
      })),
      provenance: (d.provenance || {}).fire || '',
      _zone_name: fr.zone_name, _zone_code: fr.zone_code,
    };
  }
  const sw = d.swim;
  if(sw){
    const pools = sw.pools || [], nat = sw.natural || [];
    const items = [
      ...pools.slice(0, 6).map(p => ({name: p.name, lat: p.lat, lon: p.lon,
                                       distance_m: p.distance_m,
                                       info: p.eu_rating ? `${p.category} · EU rating: ${p.eu_rating}` : p.category,
                                       _kind: 'pool',
                                       _website: p.website, _hours_hint: p.hours_hint,
                                       _rating: p.eu_rating})),
      ...nat.slice(0, 6).map(n => ({name: n.name, lat: n.lat, lon: n.lon,
                                     distance_m: n.distance_m,
                                     info: `Natural swim · EU rating: ${n.eu_rating || '—'}`,
                                     _kind: 'natural', _website: n.website, _rating: n.eu_rating})),
    ].sort((a,b) => a.distance_m - b.distance_m);
    S.amenData.swimSpots = {
      count: pools.length + nat.length,
      items,
      provenance: [(d.provenance || {}).pools, (d.provenance || {}).natural_swim]
                    .filter(Boolean).join(' + '),
    };
  }
}

export function renderAmenities(d){
  dropOrphanTooltips();
  S.amenData=d.amenities||{};
  _hydrateLookupTiles(S.eduData);
  _renderAmenPanel('amen');
  _renderAmenPanel('med');
}

export function openAmenModal(tab, cat){
  const modal=document.getElementById('amen-modal-'+tab); if(!modal) return;
  const entry=AMEN.find(e=>e[0]===cat); if(!entry) return;
  const [k,label,icon,,cap]=entry;
  const rangeCap=cap||'within ~800 m';
  const rangeShort=cap?cap.replace(/^within ~?/,''):'800 m';
  const b=S.amenData[k]||{count:0,items:[]};
  const items=(b.items||[]).slice(0,25).map((it,i)=>{
    const details=amenDetailHtml(k,it);
    const tip=details?`<details class="info-tip"><summary aria-label="More info">${ico.info}</summary><div class="info-body details-block">${details}</div></details>`:'';
    const dist = it.distance_m != null
      ? `${it.distance_m} m · ~${walkMin(it.distance_m)} min`
      : esc(it.info || '');
    return `<li data-idx="${i}" data-cat="${k}" title="Highlight on map"><span class="nm">${esc(it.name)}</span><span class="dist">${dist}</span>${tip}</li>`;
  }).join('') || `<li class="none">None within ${rangeShort}.</li>`;
  const more=(b.count||0)>25 && typeof b.count === 'number' ?`<p class="amen-more">+${b.count-25} more within ${rangeShort}</p>`:'';
  modal.innerHTML=`
    <button class="amen-modal-close" aria-label="Close">✕</button>
    <div class="modal-head"><div class="icon-badge">${icon}</div><h3>${label}</h3></div>
    <div class="metric-big"><span class="n">${b.count==null?'—':b.count}</span><span class="cap">${rangeCap}</span></div>
    <div class="amen-body"><ul class="amen-list">${items}</ul>${more}
      <div class="prov">${esc(b.provenance||'© OpenStreetMap contributors (ODbL)')}</div>
    </div>`;
  modal.hidden=false;
}
export function closeAmenModal(tab){
  const modal=document.getElementById('amen-modal-'+tab); if(!modal) return;
  modal.hidden=true; modal.innerHTML='';
  dropOrphanTooltips();
}

export function selectAmenCategory(cat){
  const p=panels[tabOf(cat)];
  if(!p.mapRef) return;
  if(p.layer){p.mapRef.removeLayer(p.layer);p.layer=null}
  p.markers=[];
  const wasSelected=p.selected===cat;
  p.selected=wasSelected?null:cat;
  p.$el.querySelectorAll('.amen-cell').forEach(c=>c.classList.toggle('active',c.dataset.cat===p.selected));
  const hint=document.getElementById(p.hintId);
  requestAnimationFrame(()=>{
    if(!p.mapRef) return;
    p.mapRef.invalidateSize();
    if(wasSelected){
      if(hint) hint.textContent='Click a card to plot its locations';
      p.mapRef.setView([S.lastCoord.lat,S.lastCoord.lon],14);
      return;
    }
    const items=((S.amenData[cat]?.items)||[]).filter(it => it.lat != null && it.lon != null);
    const label=AMEN.find(a=>a[0]===cat)[1];
    if(!items.length){
      if(hint) hint.textContent = `${label}: no plottable items`;
      return;
    }
    if(hint) hint.textContent = cat === 'fireRescue'
      ? `${label}: ${items.length} nearest · closest ${S.amenData[cat].count}`
      : `${label}: ${items.length} shown · ${S.amenData[cat].count} total`;
    p.markers=items.map(it=>L.marker([it.lat,it.lon],{icon:amenPin(cat)})
      .bindPopup(`<b>${esc(it.name)}</b><br>${it.distance_m} m · ~${walkMin(it.distance_m)} min walk${it.info?`<br><span style="color:#6B7280">${esc(it.info)}</span>`:''}`));
    p.layer=L.featureGroup(p.markers).addTo(p.mapRef);
    const b=L.latLngBounds(items.map(i=>[i.lat,i.lon])); b.extend([S.lastCoord.lat,S.lastCoord.lon]);
    try{p.mapRef.fitBounds(b.pad(0.15))}catch(e){}
  });
}

export function highlightAmenItem(cat, idx){
  const p=panels[tabOf(cat)];
  const openIt = () => {
    const m = p.markers[idx];
    if(!m || !p.mapRef) return;
    p.mapRef.setView(m.getLatLng(), Math.max(p.mapRef.getZoom(), 16), {animate:true});
    m.openPopup();
  };
  if(p.selected === cat){
    openIt();
  } else {
    selectAmenCategory(cat);
    requestAnimationFrame(()=>requestAnimationFrame(openIt));
  }
}
