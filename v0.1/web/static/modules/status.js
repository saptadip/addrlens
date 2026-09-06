import { ico } from './icons.js';
import { dom, S } from './state.js';
import { esc } from './dom.js';
import { refreshSaveBtn } from './compare.js';

// Panel empty-states — retained only as a per-tab fallback if a lookup
// somehow lands with no panel content. Initial page load hides tabs entirely.
export function empty(){dom.$out.innerHTML=`<div class="empty">
  <div class="row"><div class="icon-badge">${ico.home}</div><div class="icon-badge">${ico.school}</div><div class="icon-badge">${ico.baby}</div></div>
  <p>Enter an address above — we'll build the family picture for that flat.</p></div>`;}
export function emptyAmen(){dom.$amen.innerHTML=`<div class="empty" style="margin-top:14px">
  <div class="row"><div class="icon-badge">${ico.playground}</div><div class="icon-badge">${ico.tree}</div><div class="icon-badge">${ico.transit}</div></div>
  <p>Look up an address to see playgrounds, parks, supermarkets, drinking fountains, and transit stops within an 800 m walk.</p></div>`;}
export function emptyMed(){dom.$med.innerHTML=`<div class="empty" style="margin-top:14px">
  <div class="row"><div class="icon-badge">${ico.pharmacy}</div><div class="icon-badge">${ico.gp}</div><div class="icon-badge">${ico.hospital}</div></div>
  <p>Look up an address to see pharmacies, GPs and hospitals — walkable (800 m) plus the nearest hospitals within ~2 km.</p></div>`;}
export function emptyEnv(){dom.$env.innerHTML=`<div class="empty" style="margin-top:14px">
  <div class="row"><div class="icon-badge">${ico.waves}</div><div class="icon-badge">${ico.moon}</div></div>
  <p>Look up an address to see façade-level street noise (day + night) from Berlin's 2022 strategic noise map.</p></div>`;}

export function showStatus(kind, msg){
  dom.$tabs.hidden = true;
  document.querySelectorAll('.panel').forEach(p => p.hidden = true);
  dom.$status.hidden = false;
  if(kind === 'loading') dom.$status.innerHTML = `<div class="loading"><span class="spinner"></span> ${esc(msg)}</div>`;
  else if(kind === 'error')   dom.$status.innerHTML = `<div class="error">${esc(msg)}</div>`;
}
export function showResults(){
  dom.$status.hidden = true; dom.$status.innerHTML = '';
  dom.$tabs.hidden = false;
  // Reveal only the currently-active panel; tab-switch handler manages the rest.
  document.querySelectorAll('.panel').forEach(p => p.hidden = !p.classList.contains('active'));
}
export function clearResultState(){ S.eduData=null; S.amenData=null; S.envData=null; refreshSaveBtn(); }
