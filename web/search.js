import { WKT_FIELD } from './geo.js';
export const ENDPOINT = 'https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/Rijksmonumenten-sdo/services/Rijksmonumenten-sdo-elas/_search';
export const PAGE_SIZE = 25;
export const MAX_WINDOW = 10000;
export const EXPORT_MAX = 1000;
const MAX_VALUES = 20;
export const fields = Object.fromEntries(['description', 'name', 'address', 'postalCode', 'addressLocality', 'addressRegion', 'category', 'additionalType', 'identifier', 'sameAs'].map(key => [key, `https://schema org/${key}`]));
export const searchFields = {
  Omschrijving: [fields.description], Naam: [fields.name], Adres: [fields.address],
  Plaats: [fields.addressLocality], Type: [fields.additionalType],
  Alles: ['name', 'description', 'address', 'postalCode', 'addressLocality', 'addressRegion', 'category', 'additionalType', 'identifier'].map(key => fields[key])
};
export const facets = { addressRegion: 'Provincie/regio', addressLocality: 'Plaats', category: 'Categorie', additionalType: 'Type' };
// Sorteren op Rijksmonumentnummer kan niet: het nummer staat als tekst in de index (5 komt dan na 10040) en scripts zijn uitgeschakeld.
export const sorts = {
  relevantie: { label: 'Relevantie', sort: null },
  naam: { label: 'Naam (A–Z)', sort: [{ [`${fields.name}.keyword`]: { order: 'asc', missing: '_last' } }, '_score'] },
  plaats: { label: 'Plaats (A–Z)', sort: [{ [`${fields.addressLocality}.keyword`]: { order: 'asc', missing: '_last' } }, { [`${fields.name}.keyword`]: { order: 'asc', missing: '_last' } }] }
};
// Filters zijn { facet: [waarden] }: binnen één facet OF, tussen facetten EN.
function filterClauses(filters, skip) {
  return Object.entries(filters).filter(([key, list]) => key !== skip && list.length).map(([key, list]) => ({ terms: { [`${fields[key]}.keyword`]: list } }));
}
function validate({ query = '', field = 'Omschrijving', filters = {}, page = 0, sort = 'relevantie' }) {
  if (!Object.hasOwn(searchFields, field)) throw new Error('Onbekend zoekveld.');
  if (!Object.hasOwn(sorts, sort)) throw new Error('Onbekende sortering.');
  if (!Number.isInteger(page) || page < 0 || (page + 1) * PAGE_SIZE > MAX_WINDOW) throw new Error('Verfijn je zoekvraag om meer resultaten te bekijken.');
  if (typeof query !== 'string' || query.length > 500) throw new Error('Gebruik maximaal 500 tekens in je zoekvraag.');
  const clean = {};
  for (const [key, value] of Object.entries(filters)) {
    const list = Array.isArray(value) ? value : [value];
    if (!Object.hasOwn(facets, key) || list.length > MAX_VALUES || !list.every(item => typeof item === 'string' && item.length <= 300)) throw new Error('Ongeldig filter.');
    if (list.length) clean[key] = [...new Set(list)];
  }
  const search = query.trim() ? { query_string: { query: query.trim(), fields: searchFields[field], allow_leading_wildcard: false } } : { match_all: {} };
  return { search, filters: clean, field, page, sort };
}
// Zoeken (query) en filteren (post_filter) blijven gescheiden. Elke facet telt met de filters van de andere
// facetten, zodat je binnen een facet meerdere waarden kunt aanvinken (bijv. Gelderland én Utrecht).
export function buildQuery(state = {}) {
  const { search, filters, field, page, sort } = validate(state);
  return {
    from: page * PAGE_SIZE, size: PAGE_SIZE, track_total_hits: true, timeout: '15s',
    _source: ['@id', ...Object.values(fields), 'geoPoint', WKT_FIELD],
    query: search,
    post_filter: { bool: { filter: filterClauses(filters) } },
    ...(sorts[sort].sort ? { sort: sorts[sort].sort } : {}),
    highlight: { fields: Object.fromEntries(searchFields[field].map(key => [key, { fragment_size: 275, number_of_fragments: 3 }])), pre_tags: ['<mark>'], post_tags: ['</mark>'], encoder: 'html' },
    aggs: Object.fromEntries(Object.keys(facets).map(key => [key, {
      filter: { bool: { filter: filterClauses(filters, key) } },
      aggs: { values: { terms: { field: `${fields[key]}.keyword`, size: 100, show_term_doc_count_error: true } } }
    }]))
  };
}
// Export: dezelfde zoekvraag, filters en sortering, maximaal EXPORT_MAX resultaten, zonder geometrie, facets en highlights.
export function buildExportQuery(state = {}) {
  const { search, filters, sort } = validate({ ...state, page: 0 });
  return {
    from: 0, size: EXPORT_MAX, track_total_hits: true, timeout: '20s',
    _source: ['@id', ...Object.values(fields)],
    query: { bool: { must: [search], filter: filterClauses(filters) } },
    ...(sorts[sort].sort ? { sort: sorts[sort].sort } : {})
  };
}
export const values = value => (Array.isArray(value) ? value : value == null ? [] : [value]).filter(value => typeof value === 'string' || typeof value === 'number').map(String);
export const textValue = value => values(value).join(', ');
export function safeUrl(value) {
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; }
}
// Deelbare URL: ?q=…&veld=…&provincie=…&provincie=…&sorteer=…&pagina=…
const params = { addressRegion: 'provincie', addressLocality: 'plaats', category: 'categorie', additionalType: 'type' };
export function toParams({ query = '', field = 'Omschrijving', filters = {}, page = 0, sort = 'relevantie' }) {
  const result = new URLSearchParams();
  if (query.trim()) result.set('q', query.trim());
  if (field !== 'Omschrijving') result.set('veld', field);
  for (const [key, list] of Object.entries(filters)) for (const value of list) result.append(params[key], value);
  if (sort !== 'relevantie') result.set('sorteer', sort);
  if (page > 0) result.set('pagina', String(page + 1));
  return result;
}
export function fromParams(search) {
  const input = new URLSearchParams(search);
  const filters = {};
  for (const [key, name] of Object.entries(params)) { const list = input.getAll(name).filter(Boolean).slice(0, MAX_VALUES); if (list.length) filters[key] = list; }
  const page = Number.parseInt(input.get('pagina') ?? '1', 10);
  const state = {
    query: (input.get('q') ?? '').slice(0, 500),
    field: Object.hasOwn(searchFields, input.get('veld')) ? input.get('veld') : 'Omschrijving',
    filters,
    sort: Object.hasOwn(sorts, input.get('sorteer')) ? input.get('sorteer') : 'relevantie',
    page: Number.isInteger(page) && page >= 1 && page * PAGE_SIZE <= MAX_WINDOW ? page - 1 : 0
  };
  return { state, active: [...input.keys()].some(key => ['q', ...Object.values(params)].includes(key)) };
}
// Uitleg van de zoekactie in gewone taal.
const fieldText = { Omschrijving: 'in de omschrijving', Naam: 'in de naam', Adres: 'in het adres', Plaats: 'in de plaatsnaam', Type: 'in het type', Alles: 'in alle tekstvelden' };
export function describe({ query = '', field = 'Omschrijving', filters = {}, page = 0, sort = 'relevantie' }) {
  const lines = [];
  const trimmed = query.trim();
  if (!trimmed) lines.push('Toont alle monumenten (geen zoekvraag).');
  else {
    const readable = trimmed.split(/("[^"]*"(?:~\d+)?)/).map((part, index) => index % 2 ? part : part.replace(/\bAND\b|&&/g, 'én').replace(/\bOR\b|\|\|/g, 'of').replace(/\bNOT\b/g, 'niet')).join('');
    lines.push(`Zoekt ${fieldText[field]} naar: ${readable}`);
    const words = trimmed.replace(/"[^"]*"(~\d+)?/g, ' x ').replace(/[()]/g, ' ').split(/\s+/).filter(Boolean);
    if (words.length > 1 && !words.some(word => /^(AND|OR|NOT|&&|\|\|)$/.test(word) || /^[+-]/.test(word))) lines.push('Zonder AND/OR/NOT is het genoeg als één van de woorden voorkomt.');
  }
  const active = Object.entries(filters).filter(([, list]) => list.length);
  if (active.length) lines.push(`Alleen monumenten met ${active.map(([key, list]) => `${facets[key].toLowerCase()} ${list.map(value => `“${value}”`).join(' of ')}`).join(', en ')}.`);
  lines.push(`Gesorteerd op ${sort === 'relevantie' ? 'relevantie (best passend eerst)' : sorts[sort].label.toLowerCase()}; resultaten ${page * PAGE_SIZE + 1} tot ${(page + 1) * PAGE_SIZE}.`);
  return lines;
}
// CSV met puntkomma (opent direct goed in Nederlandse Excel) en BOM voor UTF-8.
export function toCsv(hits, decode = text => text) {
  const columns = [['Rijksmonumentnummer', 'identifier'], ['Naam', 'name'], ['Adres', 'address'], ['Postcode', 'postalCode'], ['Plaats', 'addressLocality'], ['Provincie/regio', 'addressRegion'], ['Categorie', 'category'], ['Type', 'additionalType'], ['Linked Data', '@id'], ['Monumentenregister', 'sameAs'], ['Omschrijving', 'description']];
  const cell = text => {
    const value = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text; // voorkom formule-injectie in spreadsheets
    return /[";\n\r]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
  };
  const rows = hits.map(hit => columns.map(([, key]) => cell(decode(values(hit._source?.[key === '@id' ? '@id' : fields[key]]).join(' | ')))).join(';'));
  return `﻿${columns.map(([label]) => label).join(';')}\r\n${rows.join('\r\n')}\r\n`;
}
export async function search(body, signal) {
  const response = await fetch(ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal, credentials: 'omit' });
  if (!response.ok) {
    const detail = await response.text();
    console.error('Elasticsearch', response.status, detail);
    if (response.status === 400 && /parsing_exception|parse_exception|query_shard_exception/.test(detail)) throw new Error('Controleer je zoeksyntax: gebruik bijvoorbeeld kasteel AND gracht en sluit quotes en haakjes.');
    if (response.status === 400 && /aggregat|fielddata/.test(detail)) throw new Error('De facetquery werkt niet. Probeer het later opnieuw.');
    throw new Error('De zoekservice kan je vraag nu niet verwerken. Probeer het opnieuw.');
  }
  const result = await response.json();
  if (result.timed_out || result._shards?.failed) throw new Error('De zoekservice gaf een onvolledig antwoord. Verfijn je zoekvraag en probeer opnieuw.');
  if (!result.hits || (body.aggs && !result.aggregations)) throw new Error('De zoekservice gaf geen volledige resultaten en facetten terug.');
  return result;
}
