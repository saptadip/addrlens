import { ico } from '../icons.js';
import { dom, S, othersState } from '../state.js';
import { esc, dropOrphanTooltips, labelWithGlossHtml } from '../dom.js';
import { fmtDistance } from './connectivity.js';
import { drawOthersMap, iconPin } from '../maps.js';

// -- Others tab: German admin office reach (buergeramt / finanzamt / -------
// standesamt / lea / arbeitsagentur). Reads d.others.bureaucracy.tiles
// from the /api/lookup response.

export function renderOthers(d){
  if(!dom.$others) return;
  const bur = d && d.others && d.others.bureaucracy;
  if(!bur || bur.error || !Array.isArray(bur.tiles) || !bur.tiles.length){
    othersState.tiles = []; othersState.byKey = {}; othersState.prov = '';
    dom.$others.innerHTML = `<div class="empty" style="margin-top:14px">
      <p>No public-admin data available for this address.</p></div>`;
    return;
  }
  othersState.tiles = bur.tiles;
  othersState.byKey = Object.fromEntries(bur.tiles.map(t => [t.key, t]));
  othersState.prov  = bur.provenance || '';
  othersState.selected = null;
  if(othersState.mapRef){ othersState.mapRef.remove(); othersState.mapRef = null; }
  othersState.layer = null;
  othersState.markers = [];

  const cards = bur.tiles.map(t => {
    const icon = (ico && ico[t.icon]) || (ico && ico.compass) || '';
    const features = Array.isArray(t.features) ? t.features : [];
    const bigHtml = features.length
      ? `<span class="n">${esc(fmtDistance(features[0].distance_m))}</span>`
      : `<span class="n" style="font-size:20px;color:var(--muted)">—</span>`;
    return `<div class="cell amen-cell others-cell" data-cat="${esc(t.key)}">
      <div class="amen-tile-top">
        <div class="icon-badge">${icon}</div>
        <div class="metric-big">${bigHtml}</div>
      </div>
      <span class="cell-label">${labelWithGlossHtml(t.label)}</span>
    </div>`;
  }).join('');
  const map = `<div class="map-cell amen-map-cell">
    <div class="map-hint" id="othersHint">Click a card to plot its locations</div>
    <div id="map-others"></div>
  </div>`;
  dom.$others.innerHTML = `<div class="grid">
    <div class="stack tiles-grid two-per-row">${cards}<div class="amen-modal" id="amen-modal-others" hidden></div></div>
    ${map}
  </div>`;

  dom.$others.querySelectorAll('.amen-cell').forEach(cell => cell.addEventListener('click', (e) => {
    if(e.target.closest('.info-tip')) return;
    if(e.target.closest('.amen-list li[data-idx]')) return;
    if(e.target.closest('.amen-modal-close')) return;
    const cat = cell.dataset.cat;
    openOthersModal(cat);
    selectOthersCategory(cat);
  }));

  const modal = document.getElementById('amen-modal-others');
  modal && modal.addEventListener('click', (e) => {
    if(e.target.closest('.amen-modal-close')){ closeOthersModal(); return; }
    const li = e.target.closest('.amen-list li[data-idx]');
    if(li){ e.stopPropagation();
            const cat = li.dataset.cat;
            highlightOthersItem(cat, +li.dataset.idx); }
  });

  if(document.getElementById('panel-others')?.classList.contains('active')){
    requestAnimationFrame(drawOthersMap);
  }
}

export function selectOthersCategory(cat){
  if(!othersState.mapRef){ drawOthersMap(); }
  if(!othersState.mapRef) return;
  if(othersState.layer){ othersState.mapRef.removeLayer(othersState.layer); othersState.layer = null; }
  othersState.markers = [];
  const wasSelected = othersState.selected === cat;
  othersState.selected = wasSelected ? null : cat;
  dom.$others.querySelectorAll('.amen-cell').forEach(c =>
    c.classList.toggle('active', c.dataset.cat === othersState.selected));
  const hint = document.getElementById('othersHint');
  requestAnimationFrame(() => {
    if(!othersState.mapRef) return;
    othersState.mapRef.invalidateSize();
    if(wasSelected){
      if(hint) hint.textContent = 'Click a card to plot its locations';
      othersState.mapRef.setView([S.lastCoord.lat, S.lastCoord.lon], 13);
      return;
    }
    const tile = othersState.byKey[cat];
    const items = ((tile && tile.features) || [])
      .filter(f => typeof f.lat === 'number' && typeof f.lon === 'number');
    if(!items.length){
      if(hint) hint.textContent = `${tile ? tile.label : cat}: no plottable items`;
      return;
    }
    const grp = L.layerGroup();
    items.forEach((it, i) => {
      const m = L.marker([it.lat, it.lon], {icon: iconPin(ico[tile.icon] || ico.compass, '#4F46E5')})
        .bindPopup(`<b>${esc(it.name || '')}</b>${it.address ? '<br>' + esc(it.address) : ''}${
                    it.distance_m != null ? '<br>' + fmtDistance(it.distance_m) : ''}`);
      grp.addLayer(m);
      othersState.markers.push(m);
    });
    grp.addTo(othersState.mapRef);
    othersState.layer = grp;
    const bounds = L.latLngBounds(items.map(it => [it.lat, it.lon]).concat([[S.lastCoord.lat, S.lastCoord.lon]]));
    othersState.mapRef.fitBounds(bounds, {padding: [30, 30]});
    if(hint) hint.textContent = `${tile.label}: ${items.length} on map`;
  });
}

export function highlightOthersItem(cat, idx){
  const m = othersState.markers[idx];
  if(m && othersState.mapRef){
    othersState.mapRef.setView(m.getLatLng(), Math.max(othersState.mapRef.getZoom(), 15));
    m.openPopup();
  }
}

function _othersItemDetailHtml(f){
  const rows = [];
  const push = (l, v) => v && rows.push([l, v]);
  if(f.address)               push('Address', esc(f.address));
  if(f.distance_m != null)    push('Distance', fmtDistance(f.distance_m));
  const webUrl  = (typeof f.website === 'string') ? f.website.trim() : '';
  const webSafe = /^https?:\/\//i.test(webUrl) ? webUrl : '';
  if(webSafe)                 push('Website',
    `<a href="${esc(webSafe)}" target="_blank" rel="noopener">Visit ↗</a>`);
  return rows.map(([l, v]) =>
    `<div class="det-row"><span class="det-label">${l}</span><span class="det-val">${v}</span></div>`
  ).join('');
}

export function openOthersModal(cat){
  const modal = document.getElementById('amen-modal-others'); if(!modal) return;
  const tile = othersState.byKey[cat]; if(!tile) return;
  const iconSVG = (ico && ico[tile.icon]) || '';
  const features = Array.isArray(tile.features) ? tile.features : [];
  const items = features.slice(0, 25).map((f, i) => {
    const details = _othersItemDetailHtml(f);
    const tip = details
      ? `<details class="info-tip"><summary aria-label="More info">${ico.info}</summary><div class="info-body details-block">${details}</div></details>` : '';
    const dist = f.distance_m != null ? fmtDistance(f.distance_m) : '';
    return `<li data-idx="${i}" data-cat="${esc(cat)}" title="Highlight on map">
      <span class="nm">${esc(f.name || '')}</span>
      <span class="dist">${dist}</span>
      ${tip}
    </li>`;
  }).join('') || '<li class="none">No matches nearby.</li>';
  const more = features.length > 25 ? `<p class="amen-more">+${features.length - 25} more</p>` : '';
  const caveat = tile.caveat
    ? `<div class="prov" style="margin-top:8px;font-style:italic">${esc(tile.caveat)}</div>` : '';
  const prov = othersState.prov
    ? `<div class="prov">${esc(othersState.prov)}</div>` : '';
  modal.innerHTML = `
    <button class="amen-modal-close" aria-label="Close">✕</button>
    <div class="modal-head"><div class="icon-badge">${iconSVG}</div><h3>${labelWithGlossHtml(tile.label)}</h3></div>
    <div class="metric-big"><span class="n">${features.length}</span><span class="cap">nearby offices</span></div>
    <div class="sub" style="margin:2px 0 8px">${esc(tile.rule || '')}${
      tile.numeric ? ' · ' + esc(tile.numeric) : ''}</div>
    <div class="amen-body">
      <ul class="amen-list">${items}</ul>${more}
      ${caveat}
      ${prov}
    </div>`;
  modal.hidden = false;
}

export function closeOthersModal(){
  const modal = document.getElementById('amen-modal-others'); if(!modal) return;
  modal.hidden = true; modal.innerHTML = '';
  dropOrphanTooltips();
}
