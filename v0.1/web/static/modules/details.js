import { esc, walkMin, shortUrl } from './dom.js';
import { S } from './state.js';

// Kita detail rows + amenity detail rows — pure HTML string builders.
// Kita detail rows for the ⓘ tooltip on each list item.
// Availability is intentionally NOT here — Berlin's open data doesn't publish
// live spots, so "capacity" means total places, not open ones. Product doc §6.
export function kitaDetailHtml(it){
  const p = it.props || {};
  const rows = [];
  const push = (l, v) => v && rows.push([l, v]);
  const telHtml = (v) => `<a href="tel:${esc(String(v).replace(/\s+/g,''))}">${esc(v)}</a>`;
  const webHtml = (v) => `<a href="${esc(v)}" target="_blank" rel="noopener">${esc(shortUrl(v))}</a>`;

  // Hamburg's WFS uses German field names (Strasse/Hausnr/PLZ/Ort/Telefon/…)
  // — detect by presence and fall through to Berlin's e_* prefix shape below.
  if(p.Strasse || p.Hausnr || p.Telefon || p.PLZ){
    const street = [p.Strasse, p.Hausnr].filter(Boolean).join(' ').trim();
    const addr = [street, [p.PLZ, p.Ort].filter(Boolean).join(' ').trim()].filter(x => x).join(', ');
    if(addr)              push('Address', esc(addr));
    if(p.Telefon)         push('Phone',   telHtml(p.Telefon));
    if(p.Ansprechpartner) push('Contact', esc(p.Ansprechpartner));
    // Leistungsname is an array (['Krippe bis zu 12-stündige Betreuung', …]);
    // fall through to Leistungsarten code when array is empty.
    const approaches = Array.isArray(p.Leistungsname) ? p.Leistungsname.filter(Boolean) : [];
    if(approaches.length) push('Approach', esc(approaches.join(' · ')));
    else if(p.Leistungsarten) push('Approach', esc(p.Leistungsarten));
    const cap = p.Anzahl_betreuter_Kinder;
    if(cap != null && cap !== '') push('Capacity',
      `${esc(String(cap))} places <span class="dim">(total, not availability)</span>`);
    const area = p['Pädagogische_Fläche_in_qm'];
    if(area)              push('Indoor area', `${esc(String(area))} m²`);
    if(p.Erhebungsstichtag) push('As of', esc(p.Erhebungsstichtag));
    return rows.map(([l,v])=>`<div class="det-row"><span class="det-label">${l}</span><span class="det-val">${v}</span></div>`).join('');
  }

  // Berlin BOD shape (e_* prefix).
  const streetLine = [p.e_strasse, p.e_hnr].filter(Boolean).join(' ').trim() + (p.e_zusatz ? p.e_zusatz.trim() : '');
  const fullAddr = [streetLine.trim(), (p.e_plz||'').trim()].filter(Boolean).join(', ');
  const approaches = [p.ang_1, p.ang_2].map(x=>x&&x.trim()).filter(Boolean).join(' · ');
  if(fullAddr)    push('Address', esc(fullAddr));
  if(p.e_tel)     push('Phone',   telHtml(p.e_tel));
  if(p.e_web)     push('Website', webHtml(p.e_web));
  if(p.t_name)    push('Träger',  esc(p.t_name) + (p.t_art?` <span class="dim">(${esc(p.t_art)})</span>`:''));
  if(approaches)  push('Approach', esc(approaches));
  if(p.e_platz)   push('Capacity', `${esc(p.e_platz)} places <span class="dim">(total, not availability)</span>`);
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
    // Hamburg's BOD publishes address/beds/traeger/homepage under different keys —
    // detect via `adresse` presence and shape rows from those fields.
    if(p.adresse || p.traegerschaft){
      const hAddr = [p.adresse, p.ort].filter(x => x && x.trim()).join(', ');
      if(hAddr)                       push('Address', esc(hAddr));
      if(p.planbetten != null && p.planbetten !== '')
                                       push('Beds', esc(String(p.planbetten)));
      else if(p.groessenklasse_krankenhaus)
                                       push('Beds', esc(p.groessenklasse_krankenhaus));
      if(p.teilstationaere_behandlungsplaetze != null && p.teilstationaere_behandlungsplaetze !== '')
                                       push('Day-care places', esc(String(p.teilstationaere_behandlungsplaetze)));
      if(p.traegerschaft)              push('Träger', esc(p.traegerschaft));
      if(p.art_der_stationaeren_versorgung)
                                       push('Care model', esc(p.art_der_stationaeren_versorgung));
      if(p.not_und_unfallversorgung){
        const t = String(p.not_und_unfallversorgung);
        const isER = /Teilnahme/i.test(t) && !/keine/i.test(t);
        push('Emergency room', isER ? '✓ Yes' : 'No');
      }
      if(p.homepage)                   push('Website', webLink(p.homepage));
    } else {
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
    }
    const o = it.osm || {};
    if(o.emergency === 'yes')        push('Emergency room (OSM)', '✓ Yes');
    else if(o.emergency === 'no')    push('Emergency room (OSM)', 'No');
    if(o.phone)                      push('Phone', telLink(o.phone));
    if(o.website && !p.homepage)     push('Website', webLink(o.website));
    if(o.wheelchair === 'yes')       push('Access', 'Step-free');
  }
  else if(cat === 'fountains'){
    // Berlin BOD (Trinkbrunnenart / Baujahr / Informationen) vs. Hamburg's
    // combined WC+Trinkbrunnen layer (toilette / adresse / kostenlos /
    // behindertengerecht). Detect Hamburg via `toilette` presence.
    if(p.toilette || p.adresse){
      const loc=[p.standort, p.adresse, p.bezirk].filter(x=>x&&String(x).trim()).join(' · ');
      if(loc)                        push('Location', esc(loc));
      if(p.toilette)                 push('Type', esc(p.toilette));
      const perks = [];
      if(p.kostenlos === 'ja')             perks.push('Free');
      if(p.behindertengerecht === 'ja')    perks.push('Step-free');
      if(p.genderneutral === 'ja')         perks.push('Gender-neutral');
      if(p.wickeltisch === 'ja')           perks.push('Changing table');
      if(perks.length)               push('Amenities', esc(perks.join(' · ')));
    } else {
      const loc=[p.standort, p.postleitzahl&&(p.postleitzahl+' '+(p.bezirk||''))].filter(x=>x&&String(x).trim()).join(', ');
      if(loc)                        push('Location', esc(loc));
      if(p.einschraenkungen)         push('Out of service', esc(p.einschraenkungen));
      if(p.trinkbrunnenart)          push('Type', esc(p.trinkbrunnenart));
      if(p.baujahr)                  push('Installed', esc(p.baujahr));
      if(p.informationen && p.informationen.trim())
                                     push('Season', esc(p.informationen.trim()));
    }
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
    } else if(p.beschreibung || p.anbindung || p.link){
      // Hamburg BOD (spielplaetze_hh): name/beschreibung/link/bild/anbindung.
      // No Baujahr/Sanierjahr/Fläche/Widmung fields; render what's available.
      if(p.beschreibung)             push('Description', esc(p.beschreibung));
      if(p.anbindung)                push('Transit access', esc(p.anbindung));
      if(p.link)                     push('More', webLink(p.link));
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
    } else if(p.flaeche_ha || p.stadtteil || p.gruen_art){
      // Hamburg BOD (verzeichnis_oeffentlicher_gruenanlagen).
      const loc = [p.stadtteil, p.belegenheit].filter(x => x && String(x).trim()).join(' · ');
      if(loc)                        push('Location', esc(loc));
      if(p.flaeche_ha && String(p.flaeche_ha).trim()){
        const ha = parseFloat(String(p.flaeche_ha).replace(',', '.'));
        if(isFinite(ha))             push('Area', ha >= 1 ? `${ha.toFixed(2)} ha` : `${Math.round(ha * 10_000).toLocaleString('en-US')} m²`);
      }
      if(p.gruen_art)                push('Status', esc(p.gruen_art));
      if(p.verwaltungsvermoegen)     push('Managed by', esc(p.verwaltungsvermoegen));
      if(p.eigentum)                 push('Ownership', esc(p.eigentum));
      if(p.aktualitaet)              push('As of', esc(p.aktualitaet));
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
    if(it._address)                  push('Address', esc(it._address));
    if(it._zone)                     push('Zone', esc(it._zone));
    if(it._phone_bf && it._phone_bf !== '-')  push('Phone (Berufsfeuerwehr)', telLink(it._phone_bf));
    if(it._phone_ff && it._phone_ff !== '-')  push('Phone (Freiwillige)',     telLink(it._phone_ff));
    // Universal fire/rescue emergency number in DE (shown when per-station
    // phones aren't published — Hamburg's WFS carries no telefon field).
    if(!it._phone_bf && !it._phone_ff) push('Emergency', telLink('112'));
    const kind = it._type === 'BF' ? 'Professional (Berufsfeuerwehr)'
                : it._type === 'FF' ? 'Volunteer (Freiwillige Feuerwehr)'
                : (it.info || '');
    if(kind)                         push('Kind', esc(kind));
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
