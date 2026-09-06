import { ico } from './icons.js';
import { AMEN, TIER_PIN_COLORS } from './constants.js';
import { S, panels, othersState } from './state.js';
import { esc, escapeHtml } from './dom.js';

export function pin(color,size){return L.divIcon({className:'',html:`<div style="width:${size}px;height:${size}px;border-radius:99px;background:${color};border:2.5px solid #fff;box-shadow:0 3px 8px rgba(17,24,39,.25)"></div>`,iconSize:[size,size],iconAnchor:[size/2,size/2]})}
export function iconPin(svg,color){return L.divIcon({className:'',html:`<div class="amen-pin" style="background:${color}">${svg}</div>`,iconSize:[30,30],iconAnchor:[15,15],popupAnchor:[0,-14]})}
export function amenPin(cat){const meta=AMEN.find(a=>a[0]===cat);return iconPin(meta[2],meta[3])}

export function lensNumberedPin(idx, color) {
  // divIcon HTML — .lens-pin CSS class handles size/shape; --pin-color from inline style
  return L.divIcon({
    className: '',
    html: `<div class="lens-pin" style="--pin-color:${color}" aria-label="Feature ${idx + 1}">${idx + 1}</div>`,
    iconSize: [30, 30], iconAnchor: [15, 15], popupAnchor: [0, -14],
  });
}

// Education-tab map. Draws the catchment polygon + address pin + walk circle.
export function drawMap(d){
  if(S.mapRef){S.mapRef.remove();S.mapRef=null}
  S.eduLayer=null;
  const a=d.address;
  S.mapRef=L.map('map',{scrollWheelZoom:false}).setView([a.lat,a.lon],14);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(S.mapRef);
  const p=d.catchment&&d.catchment.polygon;
  if(p){const l=L.geoJSON(p,{style:{color:'#4F46E5',weight:2.5,fillColor:'#4F46E5',fillOpacity:.10}}).addTo(S.mapRef);try{S.mapRef.fitBounds(l.getBounds().pad(0.1))}catch(e){}}
  L.circle([a.lat,a.lon],{radius:800,color:'#22C55E',weight:1.5,fillColor:'#22C55E',fillOpacity:.05,dashArray:'5 6'}).addTo(S.mapRef);
  S.addressMarker=L.marker([a.lat,a.lon],{icon:iconPin(ico.home,'#EC4899')}).addTo(S.mapRef)
    .bindPopup(`<b>${esc(a.street)} ${esc(a.hnr)}</b><br>${esc(a.plz)} Berlin`);
  requestAnimationFrame(()=>S.mapRef&&S.mapRef.invalidateSize());
}

// Amenities/Medical panel map (per tab).
export function drawAmenMap(tab){
  const p=panels[tab];
  if(p.mapRef){p.mapRef.remove();p.mapRef=null}
  if(!S.lastCoord) return;
  const {lat,lon}=S.lastCoord;
  p.mapRef=L.map(p.mapId,{scrollWheelZoom:false}).setView([lat,lon],14);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(p.mapRef);
  L.circle([lat,lon],{radius:800,color:'#22C55E',weight:1.5,fillColor:'#22C55E',fillOpacity:.05,dashArray:'5 6'}).addTo(p.mapRef);
  L.marker([lat,lon],{icon:iconPin(ico.home,'#EC4899')}).addTo(p.mapRef).bindPopup('Your address');
  p.layer=null;
  requestAnimationFrame(()=>p.mapRef&&p.mapRef.invalidateSize());
}

export function drawConnMap(){
  if(S.connMap){ S.connMap.remove(); S.connMap=null; S.connLayer=null; }
  if(!S.connData) return;
  const a = S.connData.address;
  S.connMap = L.map('map-conn',{scrollWheelZoom:false}).setView([a.lat,a.lon],13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(S.connMap);
  S.connAddressMarker = L.marker([a.lat,a.lon],{icon:iconPin(ico.home,'#EC4899')}).addTo(S.connMap)
    .bindPopup(`<b>${esc(a.street)} ${esc(a.hnr)}</b><br>${esc(a.plz)} Berlin`);
  requestAnimationFrame(()=>S.connMap&&S.connMap.invalidateSize());
}

export function drawOthersMap(){
  if(othersState.mapRef){ othersState.mapRef.remove(); othersState.mapRef = null; }
  if(!S.lastCoord) return;
  const {lat, lon} = S.lastCoord;
  const el = document.getElementById('map-others');
  if(!el) return;
  othersState.mapRef = L.map('map-others', {scrollWheelZoom:false}).setView([lat, lon], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    {maxZoom:19, attribution:'© OpenStreetMap contributors'})
    .addTo(othersState.mapRef);
  L.marker([lat, lon], {icon: iconPin(ico.home, '#EC4899')})
    .addTo(othersState.mapRef).bindPopup('Your address');
  othersState.layer = null;
  requestAnimationFrame(() => othersState.mapRef && othersState.mapRef.invalidateSize());
}

export function initLensMap(addr) {
  const el = document.getElementById('lens-map');
  if (!el || !addr) return;
  // Tear down any previous instance first (address change / re-render)
  if (S.lensMap) {
    try { S.lensMap.remove(); } catch (e) {}
    S.lensMap = null;
    S.lensAddressMarker = null;
    S.lensMapFeaturePins = [];
  }
  try {
    S.lensMap = L.map('lens-map', { scrollWheelZoom: false })
               .setView([addr.lat, addr.lon], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
    }).addTo(S.lensMap);
    S.lensAddressMarker = L.marker([addr.lat, addr.lon],
        { icon: iconPin(ico.home || ico.pin || '', '#EC4899') })
      .addTo(S.lensMap)
      .bindPopup('Your address');
  } catch (e) {
    // Leaflet CDN blocked or offline — fail visible but don't crash the app.
    // Tiles + modal still work; just no map pins.
    S.lensMap = null;
    el.innerHTML = '<div style="padding:14px;color:var(--muted);font-style:italic">Map unavailable.</div>';
  }
}

export function _updateLensMapPins(tile) {
  if (!S.lensMap) return;
  // Clear previous feature pins (address pin stays)
  S.lensMapFeaturePins.forEach(m => { try { S.lensMap.removeLayer(m); } catch (e) {} });
  S.lensMapFeaturePins = [];

  const features = Array.isArray(tile.features) ? tile.features : [];
  const hint = document.getElementById('lens-map-hint');
  if (features.length === 0) {
    if (hint) hint.textContent = 'Reading at your address';
    return;
  }

  const color = TIER_PIN_COLORS[tile.tier || 'unknown'] || TIER_PIN_COLORS.unknown;
  features.forEach((f, i) => {
    if (typeof f.lat !== 'number' || typeof f.lon !== 'number') return;
    const marker = L.marker([f.lat, f.lon], { icon: lensNumberedPin(i, color) })
      .addTo(S.lensMap)
      .bindPopup(`<b>${escapeHtml(f.name)}</b><br>${f.distance_m != null ? f.distance_m + ' m' : ''}`);
    marker._lensFeatureIdx = i;         // for two-way sync — see Task 9's pin-click callback
    S.lensMapFeaturePins.push(marker);
  });

  // Fit bounds to include address + all feature pins, with padding.
  const addrLL = S.lensAddressMarker.getLatLng();
  const latlngs = [
    [addrLL.lat, addrLL.lng],
    ...S.lensMapFeaturePins.map(m => { const ll = m.getLatLng(); return [ll.lat, ll.lng]; })
  ];
  if (latlngs.length > 1) {
    S.lensMap.fitBounds(latlngs, { padding: [30, 30] });
  } else {
    S.lensMap.setView([S.lensAddressMarker.getLatLng().lat, S.lensAddressMarker.getLatLng().lng], 14);
  }

  if (hint) hint.textContent = `${tile.label}: ${features.length} on map`;
}
