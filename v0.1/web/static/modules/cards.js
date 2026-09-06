import { CARD_ORDER_KEY } from './constants.js';
import { dropOrphanTooltips } from './dom.js';

// -- Card drag-reorder ------------------------------------------------------
// Native HTML5 DnD on .stack > .cell. Order persists per tab in localStorage
// so a reload / re-lookup keeps the user's arrangement. Cells without a
// stable key (env noise cells) are skipped — they stay in narrative order.
export function cardKey(cell){ return cell.dataset.cat || cell.dataset.eduCat || cell.dataset.envCat || cell.dataset.connKey || null; }
export function loadCardOrder(){ try{ return JSON.parse(localStorage.getItem(CARD_ORDER_KEY)||'{}'); }catch(e){ return {}; } }
// Direct-child items that participate in drag reorder. Includes .cell plus
// composite wrappers like .noise-row (L_DEN + L_NIGHT paired). Descendant
// .cell nodes inside those wrappers are deliberately excluded so a nested
// half-width card can't be dragged out of its pair.
function _stackItems(stackEl){
  return Array.from(stackEl.children).filter(c =>
    c.classList.contains('cell') || c.classList.contains('noise-row'));
}
export function saveCardOrder(tab, stackEl){
  const order = _stackItems(stackEl).map(cardKey).filter(Boolean);
  const all = loadCardOrder(); all[tab] = order;
  localStorage.setItem(CARD_ORDER_KEY, JSON.stringify(all));
}
export function applyCardOrder(tab, stackEl){
  const order = loadCardOrder()[tab] || [];
  if(!order.length) return;
  const items = _stackItems(stackEl);
  const byKey = new Map(items.map(c=>[cardKey(c),c]).filter(([k])=>k));
  // Reorder: saved keys first (in order), then any new/keyless items at end.
  order.forEach(k => { const c = byKey.get(k); if(c) stackEl.appendChild(c); });
  items.forEach(c => { const k = cardKey(c); if(!k || !order.includes(k)) stackEl.appendChild(c); });
}
export function enableDrag(tab, stackEl){
  _stackItems(stackEl).forEach(c => { if(cardKey(c)) c.draggable = true; });
  let dragged = null;
  const clearMarks = () => stackEl.querySelectorAll('.drop-target').forEach(el => el.classList.remove('drop-target'));
  // Resolve `evt.target` up to whichever direct-child of stackEl contains it.
  // Handles nested cards (e.g. .cell inside .noise-row) → returns the wrapper.
  const _stackItemFor = (t) => {
    let el = t;
    while(el && el !== stackEl && el.parentElement !== stackEl) el = el.parentElement;
    return (el && el.parentElement === stackEl) ? el : null;
  };
  stackEl.addEventListener('dragstart', e => {
    const item = _stackItemFor(e.target);
    if(!item || !item.draggable) return;
    dragged = item; item.classList.add('dragging');
    document.querySelectorAll('details.info-tip[open]').forEach(d => d.open = false);
    dropOrphanTooltips();
    e.dataTransfer.effectAllowed = 'move';
    try{ e.dataTransfer.setData('text/plain', cardKey(item) || ''); }catch(_){}
  });
  stackEl.addEventListener('dragend', () => {
    if(dragged) dragged.classList.remove('dragging');
    clearMarks(); dragged = null;
  });
  stackEl.addEventListener('dragover', e => {
    if(!dragged) return;
    e.preventDefault();
    const over = _stackItemFor(e.target);
    clearMarks();
    if(over && over !== dragged) over.classList.add('drop-target');
  });
  stackEl.addEventListener('drop', e => {
    if(!dragged) return;
    e.preventDefault();
    const over = _stackItemFor(e.target);
    if(!over || over === dragged) return;
    const rect = over.getBoundingClientRect();
    const after = (e.clientY - rect.top) > rect.height/2;
    over.parentNode.insertBefore(dragged, after ? over.nextSibling : over);
    saveCardOrder(tab, stackEl);
  });
}
