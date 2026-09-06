import { _reposTooltip } from './dom.js';

// Portal-based info-tip system for <details class="info-tip"> elements.
// When one opens, its .info-body moves out to <body> position:fixed so it
// escapes ancestor stacking contexts.
export function installTooltipHandlers(){
  document.addEventListener('toggle', (e) => {
    const det = e.target;
    if(!det.classList || !det.classList.contains('info-tip')) return;
    if(det.open){
      document.querySelectorAll('details.info-tip[open]').forEach(other => {
        if(other !== det) other.open = false;
      });
      const body = det.querySelector('.info-body');
      if(body){
        document.body.appendChild(body);
        det._portaledBody = body;
      }
      _reposTooltip(det);
    } else if(det._portaledBody){
      const b = det._portaledBody;
      b.removeAttribute('style');
      if(det.isConnected) det.appendChild(b);
      else b.remove();
      det._portaledBody = null;
    }
  }, true);

  // Keep the open tooltip anchored to its ⓘ during scroll/resize.
  ['scroll','resize'].forEach(ev => window.addEventListener(ev, () => {
    document.querySelectorAll('details.info-tip[open]').forEach(_reposTooltip);
  }, {passive:true}));

  // Outside-click auto-close for the Locality info-tip.
  document.addEventListener('click', (ev) => {
    document.querySelectorAll('details.locality-info-tip[open]').forEach(det => {
      if (det.contains(ev.target)) return;
      if (det._portaledBody && det._portaledBody.contains(ev.target)) return;
      det.open = false;
    });
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Escape') return;
    document.querySelectorAll('details.locality-info-tip[open]').forEach(det => {
      det.open = false;
      const summary = det.querySelector('summary');
      if (summary) summary.focus();
    });
  });

  // Escape closes any open amen modal (amen + med tabs).
  document.addEventListener('keydown', e => {
    if(e.key!=='Escape') return;
    ['amen','med'].forEach(t => {
      const m = document.getElementById('amen-modal-'+t);
      if(m && !m.hidden){ m.hidden = true; m.innerHTML = ''; }
    });
  });

  // Escape closes the Others tab modal.
  document.addEventListener('keydown', (e) => {
    if(e.key !== 'Escape') return;
    const m = document.getElementById('amen-modal-others');
    if(m && !m.hidden){ m.hidden = true; m.innerHTML = ''; }
  });
}
