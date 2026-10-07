import { WKT_FIELD } from './geo.js';
export const ENDPOINT = 'https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/Rijksmonumenten-sdo/services/Rijksmonumenten-sdo-elas/_search';
export const PAGE_SIZE = 25;
export const MAX_WINDOW = 10000;
export const fields = Object.fromEntries(['description', 'name', 'address', 'postalCode', 'addressLocality', 'addressRegion', 'category', 'additionalType', 'identifier', 'sameAs'].map(key => [key, `https://schema org/${key}`]));
export const searchFields = {
  Omschrijving: [fields.description], Naam: [fields.name], Adres: [fields.address],
  Plaats: [fields.addressLocality], Type: [fields.additionalType],
  Alles: ['name', 'description', 'address', 'postalCode', 'addressLocality', 'addressRegion', 'category', 'additionalType', 'identifier'].map(key => fields[key])
};
export const facets = { addressRegion: 'Provincie/regio', addressLocality: 'Plaats', category: 'Categorie', additionalType: 'Type' };
export function buildQuery({ query = '', field = 'Omschrijving', filters = {}, page = 0 } = {}) {
  if (!Object.hasOwn(searchFields, field)) throw new Error('Onbekend zoekveld.');
  if (!Number.isInteger(page) || page < 0 || (page + 1) * PAGE_SIZE > MAX_WINDOW) throw new Error('Verfijn je zoekvraag om meer resultaten te bekijken.');
  if (query.length > 500) throw new Error('Gebruik maximaal 500 tekens in je zoekvraag.');
  const filter = Object.entries(filters).map(([key, value]) => {
    if (!Object.hasOwn(facets, key) || typeof value !== 'string') throw new Error('Ongeldig filter.');
    return { term: { [`${fields[key]}.keyword`]: value } };
  });
  return {
    from: page * PAGE_SIZE, size: PAGE_SIZE, track_total_hits: true, timeout: '15s',
    _source: ['@id', ...Object.values(fields), 'geoPoint', WKT_FIELD],
    query: { bool: { must: [query.trim() ? { query_string: { query: query.trim(), fields: searchFields[field], allow_leading_wildcard: false } } : { match_all: {} }], filter } },
    highlight: { fields: Object.fromEntries(searchFields[field].map(key => [key, { fragment_size: 275, number_of_fragments: 3 }])), pre_tags: ['<mark>'], post_tags: ['</mark>'], encoder: 'html' },
    aggs: Object.fromEntries(Object.keys(facets).map(key => [key, { terms: { field: `${fields[key]}.keyword`, size: 100, show_term_doc_count_error: true } }]))
  };
}
export const values = value => (Array.isArray(value) ? value : value == null ? [] : [value]).filter(value => typeof value === 'string' || typeof value === 'number').map(String);
export const textValue = value => values(value).join(', ');
export function safeUrl(value) {
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; }
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
  if (!result.hits || !result.aggregations) throw new Error('De zoekservice gaf geen volledige resultaten en facetten terug.');
  return result;
}
