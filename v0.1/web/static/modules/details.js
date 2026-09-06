import { esc, walkMin, shortUrl } from './dom.js';

// Kita detail rows + amenity detail rows — pure HTML string builders.
// Kita detail rows for the ⓘ tooltip on each list item.
// Availability is intentionally NOT here — Berlin's open data doesn't publish
// live spots, so "capacity" means total places, not open ones. Product doc §6.
export function kitaDetailHtml(it){
  const p = it.props || {};
  const streetLine = [p.e_strasse, p.e_hnr].filter(Boolean).join(' ').trim() + (p.e_zusatz ? p.e_zusatz.trim() : '');
  const fullAddr = [streetLine.trim(), (p.e_plz||'').trim()].filter(Boolean).join(', ');
  const approaches = [p.ang_1, p.ang_2].map(x=>x&&x.trim()).filter(Boolean).join(' · ');
  const rows = [];
  if(fullAddr)    rows.push(['Address', esc(fullAddr)]);
  if(p.e_tel)     rows.push(['Phone',   `<a href="tel:${esc(p.e_tel.replace(/\s+/g,''))}">${esc(p.e_tel)}</a>`]);
  if(p.e_web)     rows.push(['Website', `<a href="${esc(p.e_web)}" target="_blank" rel="noopener">${esc(shortUrl(p.e_web))}</a>`]);
  if(p.t_name)    rows.push(['Träger',  esc(p.t_name) + (p.t_art?` <span class="dim">(${esc(p.t_art)})</span>`:'')]);
  if(approaches)  rows.push(['Approach', esc(approaches)]);
  if(p.e_platz)   rows.push(['Capacity', `${esc(p.e_platz)} places <span class="dim">(total, not availability)</span>`]);
  return rows.map(([l,v])=>`<div class="det-row"><span class="det-label">${l}</span><span class="det-val">${v}</span></div>`).join('');
}

// Rich detail rows for an amenity item, per category.
// Uses OSM tags when it.source==='osm', BOD props for BOD polygon items
// (playgrounds/parks). Only populated fields become rows — no empty labels.
export function amenDetailHtml(cat, it){
  const isOsm = it.source === 'osm';
  const t = it.tags || {};
  const p = it.props || {};
  const rows = [];
  const push = (l,v) => v && rows.push([l,v]);
  const telLink = (v) => `<a href="tel:${esc(String(v).replace(/\s+/g,''))}">${esc(v)}</a>`;
  const webLink = (v) => `<a href="${esc(v)}" target="_blank" rel="noopener">${esc(shortUrl(v))}</a>`;

  // Address — OSM addr:* or BOD district/neighborhood
  if(isOsm){
    const street = [t['addr:street'], t['addr:housenumber']].filter(Boolean).join(' ').trim();
    const addr = [street, t['addr:postcode']].filter(Boolean).join(', ');
    if(addr) push('Address', esc(addr));
  } else if(p.bezirkname){
    push('Location', esc([p.ortstlname, p.bezirkname].filter(x=>x&&x.trim()).join(' · ')));
  }

  const phone = (t.phone || t['contact:phone']);
  const web   = (t.website || t['contact:website']);

  if(cat === 'pharmacies'){
    if(t.dispensing === 'yes')       push('Prescriptions', 'Yes');
    if(t.opening_hours)              push('Opening hours', esc(t.opening_hours));
    if(phone)                        push('Phone', telLink(phone));
    if(web)                          push('Website', webLink(web));
    if(t.level)                      push('Floor', esc(t.level));
    if(t.wheelchair === 'yes')       push('Access', 'Step-free');
    if(t.operator)                   push('Operator', esc(t.operator));
  }
  else if(cat === 'supermarkets'){
    if(t.brand)                      push('Brand', esc(t.brand));
    if(t.opening_hours)              push('Opening hours', esc(t.opening_hours));
    if(t.organic === 'yes')          push('Organic', 'Yes');
    const pays = [];
    if(t['payment:cash']         === 'yes') pays.push('Cash');
    if(t['payment:credit_cards'] === 'yes') pays.push('Credit');
    if(t['payment:debit_cards']  === 'yes' || t['payment:ec'] === 'yes') pays.push('Debit / EC');
    if(pays.length)                  push('Payment', pays.join(' · '));
    if(phone)                        push('Phone', telLink(phone));
    if(t.wheelchair === 'yes')       push('Access', 'Step-free');
  }
  else if(cat === 'gps'){
    const spec = t['healthcare:speciality'] || t['healthcare:specialty'];
    if(spec)                         push('Speciality', esc(spec.replace(/;/g,', ').replace(/_/g,' ')));
    if(t.opening_hours)              push('Opening hours', esc(t.opening_hours));
    if(phone)                        push('Phone', telLink(phone));
    if(web)                          push('Website', webLink(web));
    if(t.wheelchair === 'yes')       push('Access', 'Step-free');
  }
  else if(cat === 'hospitals'){
    // BOD identity fields (address, beds, Träger) + OSM overlay (ER, phone, website).
    const hStreet=[p.gc_strasse, p.gc_haus].filter(Boolean).join(' ').trim();
    const hAddr=[hStreet, [(p.gc_plz||'').trim(), p.gc_ortsteil].filter(Boolean).join(' ')].filter(x=>x&&x.trim()).join(', ');
    if(hAddr)                        push('Address', esc(hAddr));
    if(p._layer==='weitere'){
      if(p.fachabteilungen)          push('Speciality', esc(p.fachabteilungen));
      if(p.betten)                   push('Beds', esc(p.betten));
    } else {
      if(p.betten_insgesamt)         push('Beds', esc(p.betten_insgesamt));
      if(p.kkh && p.kkh_standort && p.kkh.trim() !== p.kkh_standort.trim())
                                     push('Träger', esc(p.kkh));
    }
    const o = it.osm || {};
    if(o.emergency === 'yes')        push('Emergency room', '✓ Yes');
    else if(o.emergency === 'no')    push('Emergency room', 'No');
    if(o.phone)                      push('Phone', telLink(o.phone));
    if(o.website)                    push('Website', webLink(o.website));
    if(o.wheelchair === 'yes')       push('Access', 'Step-free');
  }
  else if(cat === 'fountains'){
    // BOD-only. Address comes from standort (free text) + district.
    const loc=[p.standort, p.postleitzahl&&(p.postleitzahl+' '+(p.bezirk||''))].filter(x=>x&&String(x).trim()).join(', ');
    if(loc)                          push('Location', esc(loc));
    if(p.einschraenkungen)           push('Out of service', esc(p.einschraenkungen));
    if(p.trinkbrunnenart)            push('Type', esc(p.trinkbrunnenart));
    if(p.baujahr)                    push('Installed', esc(p.baujahr));
    if(p.informationen && p.informationen.trim())
                                     push('Season', esc(p.informationen.trim()));
  }
  else if(cat === 'transit'){
    const modes = [];
    if(t.subway === 'yes' || t.station === 'subway')             modes.push('U-Bahn');
    if(t.light_rail === 'yes' || t.station === 'light_rail')     modes.push('S-Bahn');
    if(t.tram === 'yes')  modes.push('Tram');
    if(t.bus === 'yes')   modes.push('Bus');
    if(t.train === 'yes') modes.push('Train');
    if(modes.length)                 push('Modes', modes.join(' · '));
    if(t.operator)                   push('Operator', esc(t.operator));
    if(t.network && t.network !== t.operator) push('Network', esc(t.network));
    if(t.ref)                        push('Platform', esc(t.ref));
    const facilities = [];
    if(t.shelter === 'yes')          facilities.push('Shelter');
    if(t.bench === 'yes')            facilities.push('Bench');
    if(t.lit === 'yes')              facilities.push('Lit at night');
    if(t.passenger_information_display === 'yes') facilities.push('Live board');
    if(facilities.length)            push('Facilities', facilities.join(' · '));
    const access = [];
    if(t.wheelchair === 'yes')       access.push('Step-free');
    if(t.tactile_paving === 'yes')   access.push('Tactile paving');
    if(access.length)                push('Access', access.join(' · '));
  }
  else if(cat === 'playgrounds'){
    if(isOsm){
      const aMin = t.min_age || t['age:min'];
      const aMax = t.max_age || t['age:max'];
      if(aMin || aMax)               push('Ages', `${esc(aMin||'?')}–${esc(aMax||'?')}`);
      if(t.surface)                  push('Surface', esc(t.surface));
      if(t.playground)               push('Equipment', esc(t.playground.replace(/;/g,', ')));
      if(t.fenced === 'yes')         push('Fenced', 'Yes');
      if(t.fee === 'yes')            push('Fee', 'Yes');
      if(t.access && t.access !== 'yes') push('Access', esc(t.access));
      if(t.wheelchair === 'yes')     push('Wheelchair', 'Step-free');
    } else {
      if(p.katasterfl)               push('Area', `${(+p.katasterfl).toLocaleString('en-US')} m²`);
      if(p.baujahr && p.baujahr.trim())     push('Built',     esc(p.baujahr.trim()));
      if(p.sanierjahr && p.sanierjahr.trim()) push('Renovated', esc(p.sanierjahr.trim()));
      if(p.widmung)                  push('Status', esc(p.widmung));
    }
  }
  else if(cat === 'parks'){
    if(isOsm){
      if(t.opening_hours)            push('Opening hours', esc(t.opening_hours));
      if(t.access && t.access !== 'yes') push('Access', esc(String(t.access).replace(/^./,c=>c.toUpperCase())));
      if(t.dog)                      push('Dogs', esc(t.dog === 'leashed' ? 'On leash' : t.dog));
      if(t.wheelchair === 'yes')     push('Wheelchair', 'Step-free');
      if(t.protection_title)         push('Status', esc(t.protection_title));
      if(t.wikipedia){
        const parts = t.wikipedia.split(':');
        const lang = parts.length > 1 ? parts[0] : 'en';
        const title = parts.slice(1).join(':') || parts[0];
        push('More', `<a href="https://${esc(lang)}.wikipedia.org/wiki/${encodeURIComponent(title)}" target="_blank" rel="noopener">Wikipedia</a>`);
      }
    } else {
      if(p.katasterfl){
        const a = +p.katasterfl;
        push('Area', a >= 10_000 ? `${(a/10_000).toFixed(1)} ha` : `${a.toLocaleString('en-US')} m²`);
      }
      if(p.baujahr && p.baujahr.trim())     push('Built', esc(p.baujahr.trim()));
      if(p.sanierjahr && p.sanierjahr.trim()) push('Renovated', esc(p.sanierjahr.trim()));
      if(p.widmung)                  push('Status', esc(p.widmung));
      if(p.namezusatz && p.namezusatz.trim() && p.namezusatz.trim() !== p.namenr) push('Also', esc(p.namezusatz.trim()));
    }
  }
  // Phase-1 tile detail rows.
  else if(cat === 'fireRescue'){
    if(it._zone)                     push('Zone', esc(it._zone));
    if(it._phone_bf && it._phone_bf !== '-')  push('Phone (Berufsfeuerwehr)', telLink(it._phone_bf));
    if(it._phone_ff && it._phone_ff !== '-')  push('Phone (Freiwillige)',     telLink(it._phone_ff));
    if(it.info)                      push('Kind',    esc(it.info));
  }
  else if(cat === 'swimSpots'){
    if(it._kind === 'natural'){
      if(it._rating)                 push('EU water quality', esc(it._rating));
      if(it._website)                push('Info',    webLink(it._website));
    } else {
      if(it.info)                    push('Type',    esc(it.info));
      if(it._rating)                 push('EU water quality (natural bath)', esc(it._rating));
      if(it._hours_hint)             push('Hours',   esc(it._hours_hint));
      if(it._website)                push('Website', webLink(it._website));
    }
  }

  return rows.map(([l,v])=>`<div class="det-row"><span class="det-label">${l}</span><span class="det-val">${v}</span></div>`).join('');
}
