import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildQuery, fields, safeUrl } from '../web/search.js';
test('Booleaanse vraag, exacte filters en paginering blijven gescheiden', () => {
  const body = buildQuery({ query: '(kasteel OR buitenplaats) AND gracht', filters: { addressRegion: 'Gelderland' }, page: 1 });
  assert.equal(body.query.bool.must[0].query_string.query, '(kasteel OR buitenplaats) AND gracht');
  assert.deepEqual(body.query.bool.filter, [{ term: { [`${fields.addressRegion}.keyword`]: 'Gelderland' } }]);
  assert.equal(body.from, 25); assert.equal(body.size, 25); assert.equal(body.track_total_hits, true);
  assert.equal(Object.keys(body.aggs).length, 4);
});
test('Veldkeuze, querylengte en resultaatvenster zijn begrensd', () => {
  assert.throws(() => buildQuery({ field: 'arbitrary' }));
  assert.throws(() => buildQuery({ filters: { arbitrary: 'value' } }));
  assert.throws(() => buildQuery({ page: -1 }));
  assert.throws(() => buildQuery({ page: 400 }));
  assert.throws(() => buildQuery({ query: 'a'.repeat(501) }));
  assert.equal(buildQuery({ field: 'Alles' }).highlight.fields[fields.identifier].number_of_fragments, 3);
  assert.deepEqual(buildQuery().query.bool.must, [{ match_all: {} }]);
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
