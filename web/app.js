import { buildQuery, search, facets, fields, values, textValue, safeUrl, PAGE_SIZE, MAX_WINDOW } from './search.js';
import { geometryFor } from './geo.js';
const $ = id => document.getElementById(id);
const state = { query: '', field: 'Omschrijving', filters: {}, page: 0 };
let controller, needsFit = false;
const cards = new Map(), markers = new Map(), shapes = new Map();
const wide = window.matchMedia('(min-width: 1100px)');
// Leaflet komt van een CDN; zonder Leaflet werkt de demo verder zonder kaart.
const map = window.L ? L.map('map', { zoomControl: true }).setView([52.2, 5.3], 7) : null;
const markerLayer = map ? L.featureGroup().addTo(map) : null;
if (map) L.tileLayer('https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/standaard/EPSG:3857/{z}/{x}/{y}.png', { minZoom: 6, maxZoom: 19, attribution: 'Kaart: <a href="https://www.pdok.nl/" target="_blank" rel="noopener">PDOK</a> / Kadaster' }).addTo(map);
else $('map').append(el('p', 'De kaartbibliotheek kon niet worden geladen.', 'empty'));
const format = number => new Intl.NumberFormat('nl-NL').format(number);
// Sommige bronwaarden zijn dubbel gecodeerd (bijv. "K. &amp; J. Wilkensbrug"). Entiteiten worden als
// tekst gedecodeerd; er komt nooit HTML uit de bron in de pagina.
const decode = text => (/&[#\w]+;/.test(text) ? new DOMParser().parseFromString(text, 'text/html').body.textContent : text);
const show = value => decode(textValue(value));
function el(tag, text, className) { const node = document.createElement(tag); if (text != null) node.textContent = text; if (className) node.className = className; return node; }
function button(text, callback) { const node = el('button', text); node.type = 'button'; node.addEventListener('click', callback); return node; }
function link(text, url) { const node = el('a', text); node.href = url; node.target = '_blank'; node.rel = 'noopener noreferrer'; return node; }
function highlight(fragment) {
  const node = el('p', null, 'match');
  // Decode escaped source text, but only recreate the exact highlight delimiters.
  // No upstream HTML nodes or attributes are inserted into the live document.
  for (const [index, part] of fragment.split(/(<mark>.*?<\/mark>)/gs).entries()) {
    const marked = index % 2 === 1;
    const parsed = new DOMParser().parseFromString(marked ? part.slice(6, -7) : part, 'text/html');
    const text = decode(parsed.body.textContent);
    node.append(marked ? el('mark', text) : document.createTextNode(text));
  }
  return node;
}
function renderResults(hits) {
  $('results').replaceChildren(); cards.clear();
  if (!hits.length) { $('results').append(el('p', 'Geen monumenten gevonden. Pas je zoekvraag aan of verwijder een filter.', 'empty')); return; }
  for (const hit of hits) {
    const source = hit._source || {};
    const card = el('article'); card.dataset.id = hit._id; cards.set(hit._id, card);
    card.addEventListener('click', event => { if (!event.target.closest('a, button, summary, details')) select(hit._id, true); });
    card.append(el('p', `Rijksmonument ${textValue(source[fields.identifier]) || 'zonder nummer'}`, 'number'), el('h3', show(source[fields.name]) || 'Naam niet beschikbaar'));
    const metadata = el('dl', null, 'metadata');
    for (const [key, label] of Object.entries({ address: 'Adres', postalCode: 'Postcode', addressLocality: 'Plaats', addressRegion: 'Provincie/regio', category: 'Categorie', additionalType: 'Type' })) {
      const row = el('div'); row.append(el('dt', `${label}:`), el('dd', show(source[fields[key]]) || 'Niet vermeld')); metadata.append(row);
    }
    card.append(metadata);
    const fragments = Object.values(hit.highlight || {}).flat().slice(0, 3);
    if (fragments.length) fragments.forEach(fragment => card.append(highlight(fragment)));
    else card.append(el('p', 'Geen gematcht tekstfragment beschikbaar.', 'muted'));
    const descriptions = values(source[fields.description]).map(decode);
    if (descriptions.length) { const detail = el('details'); detail.append(el('summary', 'Volledige omschrijving')); descriptions.forEach(text => detail.append(el('p', text, 'description'))); card.append(detail); }
    const links = el('div', null, 'links');
    for (const raw of values(source['@id'])) { const url = safeUrl(raw); if (url) { links.append(link('Linked Data', url)); const uri = el('p', null, 'uri'); uri.append(link(raw, url)); card.append(uri); } }
    for (const raw of values(source[fields.sameAs])) { const url = safeUrl(raw); if (url && new URL(url).hostname === 'monumentenregister.cultureelerfgoed.nl') links.append(link('Monumentenregister', url)); }
    if (map && geometryFor(source)) links.append(button('Toon op kaart', () => select(hit._id, true)));
    card.append(links); $('results').append(card);
  }
}
function markerIcon(number, selected) {
  // Alleen het Rijksmonumentnummer als label, als tekst (geen HTML uit de bron).
  const label = el('span', number, selected ? 'selected' : null);
  return L.divIcon({ className: 'label-marker', html: label, iconSize: [0, 0] });
}
const shapeStyle = selected => ({ color: selected ? '#d18608' : '#075a85', weight: selected ? 3 : 2, fillOpacity: selected ? 0.35 : 0.2 });
function renderMap(hits) {
  if (!map) return 0;
  markerLayer.clearLayers(); markers.clear(); shapes.clear();
  const counts = { punt: 0, vlak: 0 };
  for (const hit of hits) {
    const geometry = geometryFor(hit._source);
    if (!geometry) continue;
    const number = textValue(hit._source?.[fields.identifier]) || '?';
    // Vlakken worden als vlak getekend; het label staat op het zwaartepunt van het (grootste) vlak.
    if (geometry.polygons) {
      const shape = L.polygon(geometry.polygons, shapeStyle(false)).on('click', () => select(hit._id, false));
      shapes.set(hit._id, shape); markerLayer.addLayer(shape);
    }
    const marker = L.marker([geometry.point.lat, geometry.point.lon], { icon: markerIcon(number, false), title: `Rijksmonument ${number}`, keyboard: true });
    marker.on('click', () => select(hit._id, false));
    marker.number = number;
    markers.set(hit._id, marker); markerLayer.addLayer(marker); counts[geometry.kind]++;
  }
  const total = counts.punt + counts.vlak;
  needsFit = total > 0; fitMarkers();
  $('map-info').textContent = hits.length ? `Op kaart: ${total} van ${hits.length} getoonde resultaten (${counts.punt} als punt, ${counts.vlak} als vlak met het nummer op het zwaartepunt).` : 'Geen resultaten om op de kaart te tonen.';
  return total;
}
// Een verborgen kaart heeft geen afmetingen; pas passend inzoomen zodra de kaart zichtbaar is.
function fitMarkers() {
  if (!needsFit || !$('map').offsetWidth) return;
  map.invalidateSize(); map.fitBounds(markerLayer.getBounds(), { padding: [30, 30], maxZoom: 15 }); needsFit = false;
}
function setView(view) {
  $('workspace').dataset.view = view;
  document.querySelectorAll('.view-toggle button').forEach(node => node.setAttribute('aria-pressed', String(node.dataset.view === view)));
  if (view === 'map' && map) { map.invalidateSize(); fitMarkers(); }
}
// Selecteer een resultaat: markeer de kaart en het resultaat; vanuit de lijst vliegt de kaart naar het monument.
function select(id, fromList) {
  for (const [key, card] of cards) card.classList.toggle('selected', key === id);
  for (const [key, marker] of markers) { marker.setIcon(markerIcon(marker.number, key === id)); marker.setZIndexOffset(key === id ? 1000 : 0); }
  for (const [key, shape] of shapes) { shape.setStyle(shapeStyle(key === id)); if (key === id) shape.bringToFront(); }
  const marker = markers.get(id);
  if (fromList) {
    if (!marker) return;
    if (!wide.matches) setView('map');
    needsFit = false;
    if (shapes.has(id)) map.flyToBounds(shapes.get(id).getBounds(), { padding: [40, 40], maxZoom: 18, duration: 0.8 });
    else map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 17), { duration: 0.8 });
  } else {
    if (!wide.matches) setView('list');
    cards.get(id)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}
function renderFilters(aggregations) {
  $('active-filters').replaceChildren();
  for (const [key, value] of Object.entries(state.filters)) {
    const chip = button(`${facets[key]}: ${decode(value)} ×`, () => { delete state.filters[key]; state.page = 0; run(); });
    chip.setAttribute('aria-label', `Verwijder filter ${facets[key]}: ${value}`); $('active-filters').append(chip);
  }
  if (Object.keys(state.filters).length) $('active-filters').append(button('Wis alle filters', () => { state.filters = {}; state.page = 0; run(); }));
  $('facets').replaceChildren();
  for (const [key, label] of Object.entries(facets)) {
    const group = el('details'); group.open = true; group.append(el('summary', label));
    const aggregation = aggregations[key];
    if (!aggregation) { group.append(el('p', 'Deze facet is niet beschikbaar.', 'hint')); $('facets').append(group); continue; }
    const list = el('ul', null, 'facet-list');
    for (const bucket of aggregation.buckets) {
      const item = el('li');
      const option = button('', () => { if (state.filters[key] === bucket.key) delete state.filters[key]; else state.filters[key] = bucket.key; state.page = 0; run(); });
      const approximate = bucket.doc_count_error_upper_bound > 0;
      option.append(el('span', decode(bucket.key)), el('span', `${approximate ? '≈ ' : ''}${format(bucket.doc_count)}`));
      option.setAttribute('aria-pressed', String(state.filters[key] === bucket.key)); item.append(option); list.append(item);
    }
    group.append(list);
    if (!aggregation.buckets.length) group.append(el('p', 'Geen waarden bij deze zoekvraag.', 'hint'));
    if (aggregation.sum_other_doc_count > 0) group.append(el('p', 'De 100 meest voorkomende waarden. Verfijn je zoekvraag voor andere waarden.', 'hint'));
    $('facets').append(group);
  }
}
async function run() {
  controller?.abort(); const current = new AbortController(); controller = current;
  let body;
  try { body = buildQuery(state); } catch (error) { $('error').textContent = error.message; $('error').hidden = false; return; }
  $('query-json').textContent = JSON.stringify(body, null, 2);
  $('error').hidden = true; $('status').textContent = 'Zoeken…'; $('workspace').setAttribute('aria-busy', 'true');
  $('results').replaceChildren(); renderMap([]); $('map-info').textContent = 'Zoeken…'; $('facets').replaceChildren(); $('active-filters').replaceChildren(); $('pagination').hidden = true; $('page-info').textContent = '';
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; current.abort(); }, 20000);
  try {
    const data = await search(body, current.signal);
    if (controller !== current) return;
    const total = typeof data.hits.total === 'number' ? data.hits.total : data.hits.total.value;
    const exact = typeof data.hits.total === 'number' || data.hits.total.relation === 'eq';
    const hits = data.hits.hits;
    renderResults(hits); renderFilters(data.aggregations);
    const onMap = renderMap(hits);
    $('status').textContent = `Totaal gevonden: ${exact ? '' : 'minimaal '}${format(total)} | Getoond: ${hits.length}${map ? ` | Op kaart: ${onMap}` : ''}`;
    $('page-info').textContent = hits.length ? `${format(state.page * PAGE_SIZE + 1)} tot ${format(state.page * PAGE_SIZE + hits.length)}` : '';
    $('pagination').hidden = total <= PAGE_SIZE;
    $('previous').disabled = state.page === 0;
    $('next').disabled = (state.page + 1) * PAGE_SIZE >= Math.min(total, MAX_WINDOW);
    $('page-number').textContent = `Pagina ${state.page + 1} van ${Math.max(1, Math.ceil(Math.min(total, MAX_WINDOW) / PAGE_SIZE))}`;
    if (total > MAX_WINDOW) $('results').append(el('p', 'Je kunt maximaal de eerste 10.000 resultaten bekijken. Verfijn je zoekvraag voor de overige resultaten.', 'hint'));
  } catch (error) {
    if (controller !== current) return;
    $('status').textContent = 'Zoeken niet gelukt.';
    $('error').textContent = timedOut ? 'De zoekopdracht duurde te lang. Verfijn je zoekvraag en probeer opnieuw.' : error instanceof TypeError ? 'De zoekservice is niet bereikbaar. Controleer je verbinding en probeer opnieuw.' : error.message;
    $('error').hidden = false;
    renderFilters({}); renderMap([]);
  } finally { clearTimeout(timer); if (controller === current) $('workspace').setAttribute('aria-busy', 'false'); }
}
$('search-form').addEventListener('submit', event => { event.preventDefault(); state.query = $('query').value; state.field = $('field').value; state.page = 0; run(); });
document.querySelectorAll('[data-example]').forEach(node => node.addEventListener('click', () => { $('help').close(); $('query').value = node.dataset.example; checkQuery(); $('search-form').requestSubmit(); }));
$('help-open').addEventListener('click', () => $('help').showModal());
$('help-close').addEventListener('click', () => $('help').close());
$('help').addEventListener('click', event => { if (event.target === $('help')) $('help').close(); });
// Tip bij operatoren in kleine letters of Nederlandse varianten: die worden als gewone zoekwoorden gezien.
function checkQuery() {
  const words = [...new Set(($('query').value.replace(/"[^"]*"/g, ' ').match(/(?<![\p{L}\d])(and|or|not|en|of|niet)(?![\p{L}\d])/gu) || []))];
  const operator = { and: 'AND', en: 'AND', or: 'OR', of: 'OR', not: 'NOT', niet: 'NOT' };
  $('query-tip').textContent = words.length ? `Tip: ${words.map(word => `“${word}”`).join(', ')} wordt als zoekwoord gezien. Bedoel je ${[...new Set(words.map(word => operator[word]))].join(' / ')}? Schrijf operatoren in hoofdletters.` : '';
  $('query-tip').hidden = !words.length;
}
$('query').addEventListener('input', checkQuery);

$('previous').addEventListener('click', () => { state.page--; run(); });
$('next').addEventListener('click', () => { state.page++; run(); });
document.querySelectorAll('.view-toggle button').forEach(node => node.addEventListener('click', () => setView(node.dataset.view)));
wide.addEventListener('change', () => { if (map) { map.invalidateSize(); fitMarkers(); } });
