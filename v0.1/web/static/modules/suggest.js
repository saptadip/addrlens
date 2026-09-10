import { dom } from './state.js';
import { escapeHtml, _track } from './dom.js';
import { readJson } from './api.js';

// /api/suggest typeahead — combobox pattern (WAI-ARIA 1.2).
// Debounces to 130 ms so a fast typist emits ~7-8 requests per address rather
// than one per keystroke. Aborts the in-flight fetch on each new keystroke so
// a slow response never overwrites a newer one.
export function wireSuggest(){
  const wrap = document.querySelector('.autocomplete-wrap');
  const list = document.getElementById('q-suggest-list');
  const $q = dom.$q, $f = dom.$f;
  if(!wrap || !list) return;

  const MIN_Q = 2, DEBOUNCE_MS = 130, MAX_HITS = 8;
  let debounceTimer = null, inflight = null, hits = [], activeIx = -1, lastQuery = '';

  function closeList(){
    list.hidden = true;
    list.innerHTML = '';
    wrap.setAttribute('aria-expanded','false');
    $q.setAttribute('aria-activedescendant','');
    hits = []; activeIx = -1;
  }
  function positionList(){
    if(list.hidden) return;
    const r = $q.getBoundingClientRect();
    list.style.top   = (r.bottom + 6) + 'px';
    list.style.left  = r.left           + 'px';
    list.style.width = r.width          + 'px';
  }
  function highlight(text, needle){
    if(!needle) return escapeHtml(text);
    const i = text.toLowerCase().indexOf(needle.toLowerCase());
    if(i < 0) return escapeHtml(text);
    return escapeHtml(text.slice(0,i))
         + '<mark>' + escapeHtml(text.slice(i, i+needle.length)) + '</mark>'
         + escapeHtml(text.slice(i+needle.length));
  }
  function render(){
    if(!hits.length){ closeList(); return; }
    list.innerHTML = hits.map((h,i) =>
      `<li id="q-sug-${i}" role="option" data-ix="${i}" data-value="${escapeHtml(h.label)}"
           class="suggest-item${i===activeIx?' active':''}"
           aria-selected="${i===activeIx?'true':'false'}">
         <span class="suggest-label">${highlight(h.label, lastQuery)}</span>
       </li>`
    ).join('');
    list.hidden = false;
    wrap.setAttribute('aria-expanded','true');
    if(activeIx >= 0) $q.setAttribute('aria-activedescendant', `q-sug-${activeIx}`);
    positionList();
  }
  function setActive(newIx){
    if(!hits.length) return;
    activeIx = ((newIx % hits.length) + hits.length) % hits.length;
    render();
    const el = list.querySelector('.suggest-item.active');
    if(el) el.scrollIntoView({block:'nearest'});
  }
  function commit(ix){
    if(ix < 0 || ix >= hits.length) return;
    _track('suggest_selected', {
      label: hits[ix].label,
      position: ix,
      query_len: (lastQuery || '').length
    });
    $q.value = hits[ix].label;
    closeList();
    $f.dispatchEvent(new Event('submit'));
  }
  async function fetchSuggest(q){
    if(inflight) inflight.abort();
    inflight = new AbortController();
    try{
      const r = await fetch(`/api/suggest?q=${encodeURIComponent(q)}&limit=${MAX_HITS}`,
                            {signal: inflight.signal});
      if(!r.ok) throw new Error('http '+r.status);
      const d = await readJson(r);
      if($q.value.trim() !== q) return;
      hits = Array.isArray(d.hits) ? d.hits : [];
      activeIx = hits.length ? 0 : -1;
      lastQuery = q;
      render();
    }catch(e){
      if(e.name === 'AbortError') return;
      closeList();
    }
  }

  $q.addEventListener('input', () => {
    const q = $q.value.trim();
    clearTimeout(debounceTimer);
    if(q.length < MIN_Q){ closeList(); return; }
    debounceTimer = setTimeout(() => fetchSuggest(q), DEBOUNCE_MS);
  });

  $q.addEventListener('keydown', ev => {
    if(list.hidden || !hits.length){
      if(ev.key === 'ArrowDown' && $q.value.trim().length >= MIN_Q){
        ev.preventDefault();
        fetchSuggest($q.value.trim());
      }
      return;
    }
    switch(ev.key){
      case 'ArrowDown': ev.preventDefault(); setActive(activeIx + 1); break;
      case 'ArrowUp':   ev.preventDefault(); setActive(activeIx - 1); break;
      case 'Enter':
        if(activeIx >= 0){
          ev.preventDefault();
          commit(activeIx);
        }else{
          closeList();
        }
        break;
      case 'Escape': ev.preventDefault(); closeList(); break;
      case 'Tab':    closeList(); break;
    }
  });

  list.addEventListener('mousemove', ev => {
    const li = ev.target.closest('.suggest-item');
    if(!li) return;
    const ix = Number(li.dataset.ix);
    if(!Number.isNaN(ix) && ix !== activeIx){ activeIx = ix; render(); }
  });
  list.addEventListener('mousedown', ev => {
    const li = ev.target.closest('.suggest-item');
    if(!li) return;
    ev.preventDefault();
    commit(Number(li.dataset.ix));
  });

  document.addEventListener('click', ev => {
    if(!wrap.contains(ev.target)) closeList();
  });
  $q.addEventListener('blur', () => setTimeout(closeList, 150));

  window.addEventListener('scroll', positionList, {passive: true});
  window.addEventListener('resize', positionList);
}
