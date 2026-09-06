import { ico } from '../icons.js';
import { CONN_META } from '../constants.js';
import { dom, S } from '../state.js';
import { esc } from '../dom.js';
import { applyCardOrder, enableDrag } from '../cards.js';
import { drawConnMap, iconPin } from '../maps.js';

export function fmtDistance(m){
  // < 1000 m → "340 m"; ≥ 1000 m → "1.2 km".
  if(m==null) return '—';
  return m < 1000 ? `${m} m` : `${(m/1000).toFixed(1)} km`;
}

export function renderConn(c, prov, addr){
  if(!c){ dom.$conn.innerHTML=''; S.connData=null; return; }
  S.connData = {connectivity:c, address:addr}; S.connSelected=null;
  const order = Object.entries(CONN_META)
    .map(([key, meta]) => ({key, meta, val:c[key]}))
    .sort((a,b) => (a.val?.distance_m ?? Infinity) - (b.val?.distance_m ?? Infinity));
  const cards = order.map(({key, meta, val}) => {
    if(!val){
      return `<div class="cell conn-cell" data-conn-key="${key}" title="Not available">
        <div class="conn-tile-top">
          <div class="icon-badge">${ico.transit}</div>
          <div class="metric-big"><span class="n" style="font-size:20px;color:var(--muted)">—</span></div>
        </div>
        <div class="cell-caption">
          <span class="cell-label">${meta.label}</span>
          <span class="conn-stop">Not available</span>
        </div>
      </div>`;
    }
    const captionName = val.iata && !val.name.includes(val.iata) ? `${esc(val.name)} (${esc(val.iata)})` : esc(val.name);
    return `<div class="cell conn-cell" data-conn-key="${key}" title="${captionName}">
      <div class="conn-tile-top">
        <div class="icon-badge">${ico.transit}</div>
        <div class="metric-big"><span class="n">${fmtDistance(val.distance_m)}</span></div>
      </div>
      <div class="cell-caption">
        <span class="cell-label">${meta.label}</span>
        <span class="conn-stop" title="${captionName}">${captionName}</span>
      </div>
    </div>`;
  }).join('');
  const map = `<div class="map-cell"><div class="map-hint" id="connHint">Click a card to plot its location</div><div id="map-conn"></div></div>`;
  dom.$conn.innerHTML = `<div class="grid"><div class="stack tiles-grid conn-tiles">${cards}</div>${map}</div>`;
  drawConnMap();
  dom.$conn.querySelectorAll('.conn-cell').forEach(cell=>cell.addEventListener('click',()=>selectConnMode(cell.dataset.connKey)));
  const connStack = dom.$conn.querySelector('.stack');
  if(connStack){ applyCardOrder('conn', connStack); enableDrag('conn', connStack); }
}

export function selectConnMode(mode){
  if(!S.connMap || !S.connData) return;
  if(S.connLayer){ S.connMap.removeLayer(S.connLayer); S.connLayer=null; }
  const wasSelected=S.connSelected===mode;
  S.connSelected = wasSelected ? null : mode;
  dom.$conn.querySelectorAll('.conn-cell').forEach(c=>c.classList.toggle('active', c.dataset.connKey===S.connSelected));
  const hint = document.getElementById('connHint');
  const a = S.connData.address;
  requestAnimationFrame(()=>{
    if(!S.connMap) return;
    S.connMap.invalidateSize();
    if(wasSelected){
      if(hint) hint.textContent='Click a card to plot its location';
      if(S.connAddressMarker) S.connAddressMarker.closePopup();
      S.connMap.setView([a.lat,a.lon],13);
      return;
    }
    const dest = S.connData.connectivity[mode];
    if(!dest){
      if(hint) hint.textContent = `${CONN_META[mode]?.label || mode}: not available`;
      return;
    }
    const meta = CONN_META[mode] || {label: mode};
    if(hint) hint.textContent = `${meta.label} · ${dest.name} · ${fmtDistance(dest.distance_m)}`;
    const destMarker = L.marker([dest.lat,dest.lon],{icon:iconPin(ico.transit,'#4F46E5')})
      .bindPopup(`<b>${esc(dest.name)}</b><br>${fmtDistance(dest.distance_m)} from your address`);
    S.connLayer = L.featureGroup([destMarker]).addTo(S.connMap);
    try{ S.connMap.fitBounds(L.latLngBounds([[a.lat,a.lon],[dest.lat,dest.lon]]).pad(0.2)); }catch(e){}
    destMarker.openPopup();
  });
}
