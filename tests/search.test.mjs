import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildQuery, buildExportQuery, fields, safeUrl, toParams, fromParams, describe, toCsv, EXPORT_MAX } from '../web/search.js';
const region = `${fields.addressRegion}.keyword`, type = `${fields.additionalType}.keyword`;
test('Zoeken (query) en filteren (post_filter) blijven gescheiden; facets tellen zonder hun eigen filter', () => {
  const body = buildQuery({ query: '(kasteel OR buitenplaats) AND gracht', filters: { addressRegion: ['Gelderland', 'Utrecht'], additionalType: 'Kasteel' }, page: 1 });
  assert.equal(body.query.query_string.query, '(kasteel OR buitenplaats) AND gracht');
  assert.deepEqual(body.post_filter.bool.filter, [{ terms: { [region]: ['Gelderland', 'Utrecht'] } }, { terms: { [type]: ['Kasteel'] } }]);
  assert.deepEqual(body.aggs.addressRegion.filter.bool.filter, [{ terms: { [type]: ['Kasteel'] } }]);
  assert.deepEqual(body.aggs.additionalType.filter.bool.filter, [{ terms: { [region]: ['Gelderland', 'Utrecht'] } }]);
  assert.equal(body.aggs.category.filter.bool.filter.length, 2);
  assert.equal(body.from, 25); assert.equal(body.size, 25); assert.equal(body.track_total_hits, true);
  assert.equal(body.sort, undefined);
  assert.ok(buildQuery({ sort: 'naam' }).sort[0][`${fields.name}.keyword`]);
});
test('Veldkeuze, filters, sortering, querylengte en resultaatvenster zijn begrensd', () => {
  assert.throws(() => buildQuery({ field: 'arbitrary' }));
  assert.throws(() => buildQuery({ filters: { arbitrary: ['value'] } }));
  assert.throws(() => buildQuery({ filters: { addressRegion: Array.from({ length: 21 }, (_, i) => `p${i}`) } }));
  assert.throws(() => buildQuery({ sort: 'script' }));
  assert.throws(() => buildQuery({ page: -1 }));
  assert.throws(() => buildQuery({ page: 400 }));
  assert.throws(() => buildQuery({ query: 'a'.repeat(501) }));
  assert.equal(buildQuery({ field: 'Alles' }).highlight.fields[fields.identifier].number_of_fragments, 3);
  assert.deepEqual(buildQuery().query, { match_all: {} });
  const exported = buildExportQuery({ query: 'molen', filters: { addressRegion: ['Utrecht'] }, page: 7 });
  assert.equal(exported.size, EXPORT_MAX); assert.equal(exported.from, 0); assert.equal(exported.aggs, undefined);
  assert.deepEqual(exported.query.bool.filter, [{ terms: { [region]: ['Utrecht'] } }]);
});
test('Deelbare URL: heen en terug, onbekende waarden worden genegeerd', () => {
  const state = { query: 'kasteel AND gracht', field: 'Naam', filters: { addressRegion: ['Gelderland', 'Utrecht'], category: ['onroerend gebouwd'] }, page: 2, sort: 'naam' };
  const search = toParams(state).toString();
  assert.equal(search, 'q=kasteel+AND+gracht&veld=Naam&provincie=Gelderland&provincie=Utrecht&categorie=onroerend+gebouwd&sorteer=naam&pagina=3');
  assert.deepEqual(fromParams(`?${search}`), { state, active: true });
  const bad = fromParams('?veld=__proto__&sorteer=x&pagina=-4&onbekend=1');
  assert.deepEqual(bad.state, { query: '', field: 'Omschrijving', filters: {}, sort: 'relevantie', page: 0 });
  assert.equal(bad.active, false);
  assert.equal(toParams({}).toString(), '');
});
test('Uitleg in gewone taal', () => {
  const lines = describe({ query: 'kasteel AND NOT "Grote AND Scheer"', filters: { addressRegion: ['Gelderland', 'Utrecht'] } });
  assert.equal(lines[0], 'Zoekt in de omschrijving naar: kasteel én niet "Grote AND Scheer"');
  assert.match(lines[1], /provincie\/regio “Gelderland” of “Utrecht”/);
  assert.match(describe({ query: 'kasteel gracht' })[1], /één van de woorden/);
  assert.match(describe({})[0], /alle monumenten/);
});
test('CSV: puntkomma, quotes, meerdere waarden en geen formules', () => {
  const csv = toCsv([{ _source: { '@id': 'https://example.org/1', [fields.identifier]: ['1'], [fields.name]: ['=SOM(A1)'], [fields.description]: ['regel 1\nmet "quote"; en meer'], [fields.addressLocality]: ['A', 'B'] } }]);
  const [header, row] = csv.slice(1).split('\r\n');
  assert.ok(csv.startsWith('﻿Rijksmonumentnummer;Naam;'));
  assert.equal(header.split(';').length, 11);
  assert.match(row, /^1;'=SOM\(A1\);;;A \| B;/);
  assert.match(csv, /"regel 1\nmet ""quote""; en meer"/);
});
test('Bronlinks accepteren alleen HTTP en HTTPS', () => {
  assert.equal(safeUrl('javascript:alert(1)'), null);
  assert.equal(safeUrl('data:text/html,test'), null);
  assert.equal(safeUrl('https://example.org/id/1'), 'https://example.org/id/1');
});
test('Kaart: geoPoint, dan WKT POINT (lon lat), dan WKT-vlak met label op het zwaartepunt', async () => {
  const { geometryFor, WKT_FIELD } = await import('../web/geo.js');
  assert.deepEqual(geometryFor({ geoPoint: '52.1,5.2', [WKT_FIELD]: ['POINT(4 51)'] }), { kind: 'punt', point: { lat: 52.1, lon: 5.2 } });
  assert.deepEqual(geometryFor({ [WKT_FIELD]: ['Point (5.12 52.09)'] }).point, { lat: 52.09, lon: 5.12 });
  assert.deepEqual(geometryFor({ [WKT_FIELD]: ['<http://www.opengis.net/def/crs/OGC/1.3/CRS84> POINT(5 52)'] }).point, { lat: 52, lon: 5 });
  assert.equal(geometryFor({ [WKT_FIELD]: ['<http://www.opengis.net/def/crs/EPSG/0/28992> POINT(155000 463000)'] }), null);
  const square = geometryFor({ [WKT_FIELD]: ['Polygon ((5 52, 6 52, 6 53, 5 53, 5 52))'] });
  assert.equal(square.kind, 'vlak'); assert.deepEqual(square.polygons[0][0][1], [52, 6]);
  assert.ok(Math.abs(square.point.lat - 52.5) < 1e-9 && Math.abs(square.point.lon - 5.5) < 1e-9);
  const multi = geometryFor({ [WKT_FIELD]: ['MultiPolygon (((5 52, 5.1 52, 5.1 52.1, 5 52)), ((6 52, 7 52, 7 53, 6 53, 6 52), (6.2 52.2, 6.3 52.2, 6.3 52.3, 6.2 52.2)))'] });
  assert.equal(multi.polygons.length, 2); assert.equal(multi.polygons[1].length, 2);
  assert.ok(Math.abs(multi.point.lon - 6.5) < 1e-9, 'label op het grootste vlak');
  assert.ok(buildQuery()._source.includes(WKT_FIELD));
});
