import { dom, S } from './state.js';
import { esc } from './dom.js';
import { renderNoise } from './panels/environment.js';
import { renderAmenities, amenHasErrors } from './panels/amenities.js';
import { refreshSaveBtn } from './compare.js';

// -- Noise (Environment panel) ---------------------------------------------
export async function fetchNoise(lat,lon){
  if(S.noiseFetching) return;
  S.noiseFetching=true;
  dom.$env.innerHTML=`<div class="loading"><span class="spinner"></span> Reading Berlin's 2022 façade noise map…</div>`;
  try{
    const r=await fetch(`/api/noise?lat=${lat}&lon=${lon}`);
    const d=await r.json();
    if(!r.ok){dom.$env.innerHTML=`<div class="error">${esc(d.error||'Failed to load noise data.')}</div>`;return}
    renderNoise(d.noise); dom.$env.dataset.loaded='1';
  }catch(e){dom.$env.innerHTML=`<div class="error">Network error: ${esc(e.message)}</div>`}
  finally{S.noiseFetching=false}
}

// -- Amenities (Amenities + Medical panels) --------------------------------
export async function fetchAmenities(lat,lon,isRetry){
  if(S.amenFetching) return;
  S.amenFetching=true;
  if(!isRetry) S.amenAttempts=0;
  S.amenAttempts++;
  const loading=`<div class="loading"><span class="spinner"></span> Reading Berlin Open Data + OpenStreetMap${isRetry?' (retrying)':''}…</div>`;
  dom.$amen.innerHTML=loading; dom.$med.innerHTML=loading;
  try{
    const r=await fetch(`/api/amenities?lat=${lat}&lon=${lon}`);
    const d=await r.json();
    if(!r.ok){
      const err=`<div class="error">${esc(d.error||'Failed to load amenities.')}</div>`;
      dom.$amen.innerHTML=err; dom.$med.innerHTML=err; return;
    }
    renderAmenities(d);
    dom.$amen.dataset.loaded='1'; dom.$med.dataset.loaded='1';
    refreshSaveBtn();
    // ponytail: Overpass throttles per-IP; a fresh call 3 s later usually
    // clears it. One silent retry, then accept whatever we have.
    if(!isRetry && amenHasErrors()){
      setTimeout(()=>{ if(S.lastCoord && lat===S.lastCoord.lat && lon===S.lastCoord.lon) fetchAmenities(lat,lon,true); else refreshSaveBtn(); }, 3000);
    }
  }catch(e){
    const err=`<div class="error">Network error: ${esc(e.message)}</div>`;
    dom.$amen.innerHTML=err; dom.$med.innerHTML=err;
  }
  finally{S.amenFetching=false; refreshSaveBtn();}
}
