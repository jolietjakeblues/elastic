import assert from 'node:assert/strict';
import { buildQuery, buildExportQuery, search, toCsv, ENDPOINT, fields, facets } from '../web/search.js';
import { geometryFor } from '../web/geo.js';
const timeout = () => AbortSignal.timeout(30000);
const preflight = await fetch(ENDPOINT, { method: 'OPTIONS', headers: { Origin: 'http://127.0.0.1:4173', 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type' } });
assert.ok(preflight.ok);
assert.equal(preflight.headers.get('access-control-allow-origin'), '*');
assert.match(preflight.headers.get('access-control-allow-methods'), /POST/);
assert.match(preflight.headers.get('access-control-allow-headers'), /content-type/i);
const base = { query: 'kasteel AND gracht', field: 'Omschrijving' };
const result = await search(buildQuery(base), timeout());
const buckets = (data, key) => data.aggregations[key].values.buckets;
const count = (data, key, value) => buckets(data, key).find(bucket => bucket.key === value)?.doc_count ?? 0;
assert.equal(result.hits.total.relation, 'eq');
assert.ok(result.hits.hits.some(hit => hit.highlight?.[fields.description]?.length));
for (const key of Object.keys(facets)) assert.ok(buckets(result, key).length, `Facet ${key}`);
const gelderland = count(result, 'addressRegion', 'Gelderland'), utrecht = count(result, 'addressRegion', 'Utrecht');
assert.ok(gelderland && utrecht);
// Eén provincie: totaal klopt met de facet; de provinciefacet blijft alle provincies tonen (om er meer te kunnen kiezen).
const filtered = await search(buildQuery({ ...base, filters: { addressRegion: ['Gelderland'] } }), timeout());
assert.equal(filtered.hits.total.value, gelderland);
assert.ok(filtered.hits.hits.every(hit => hit._source[fields.addressRegion].includes('Gelderland')));
assert.equal(count(filtered, 'addressRegion', 'Utrecht'), utrecht);
assert.ok(buckets(filtered, 'additionalType').reduce((sum, bucket) => sum + bucket.doc_count, 0) <= gelderland + 50);
// Twee provincies: OF binnen de facet.
const both = await search(buildQuery({ ...base, filters: { addressRegion: ['Gelderland', 'Utrecht'] } }), timeout());
assert.equal(both.hits.total.value, gelderland + utrecht);
// Sorteren op naam.
const sorted = await search(buildQuery({ ...base, sort: 'naam' }), timeout());
const names = sorted.hits.hits.map(hit => hit._source[fields.name]?.[0]).filter(Boolean);
assert.deepEqual(names, [...names].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0)));
// Paginering.
const page2 = await search(buildQuery({ ...base, page: 1 }), timeout());
assert.equal(page2.hits.total.value, result.hits.total.value);
assert.notEqual(page2.hits.hits[0]._id, result.hits.hits[0]._id);
// Export.
const exported = await search(buildExportQuery({ ...base, filters: { addressRegion: ['Gelderland', 'Utrecht'] } }), timeout());
const csv = toCsv(exported.hits.hits);
assert.equal(exported.hits.hits.length, gelderland + utrecht);
assert.ok(csv.startsWith('﻿Rijksmonumentnummer;'));
const geometries = result.hits.hits.map(hit => geometryFor(hit._source)?.kind ?? 'geen');
assert.ok(geometries.some(kind => kind !== 'geen'), 'Geometrie op de kaart');
console.log(JSON.stringify({
  cors: 'OK', total: result.hits.total.value, gelderland: filtered.hits.total.value, gelderlandOfUtrecht: both.hits.total.value,
  facets: Object.fromEntries(Object.keys(facets).map(key => [key, buckets(result, key).length])),
  geometrie: Object.fromEntries(['punt', 'vlak', 'geen'].map(kind => [kind, geometries.filter(k => k === kind).length])),
  csvRecords: exported.hits.hits.length, highlighting: 'OK', sorteren: 'OK', pagination: 'OK'
}, null, 2));
