# Rijksmonumenten SDO/Elastic demo

> **Dit is een demo.** Bouw hier geen applicaties of andere afhankelijkheden op. De scripts, index en service kunnen zonder aankondiging wijzigen of verdwijnen.

Een kleine webdemo die laat zien wat Elasticsearch bovenop de SDO/Linked Data-publicatie van de RCE-dataset `Rijksmonumenten-sdo` mogelijk maakt: fulltext en Booleaans zoeken, filteren, facetten met aantallen, highlighting, een kaart en directe links naar Linked Data en het Monumentenregister.

De demo is **geen vervanging van het Monumentenregister** en geen productieapplicatie.

**Online:** <https://rijksmonumenten-sdo-elastic-demo.jolietjakeblues64.workers.dev/>

Voorbeeld van een deelbare zoekactie: [kasteel AND gracht in Gelderland of Utrecht, op naam gesorteerd](https://rijksmonumenten-sdo-elastic-demo.jolietjakeblues64.workers.dev/?q=kasteel+AND+gracht&provincie=Gelderland&provincie=Utrecht&sorteer=naam)

```text
Linked Data + SDO-publicatie + Elasticsearch = zoeken, filteren, facetteren en geografisch verkennen
```

## Elasticsearch-service

```text
POST https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/Rijksmonumenten-sdo/services/Rijksmonumenten-sdo-elas/_search
```

De browser praat rechtstreeks met deze service. Getest: de service staat CORS toe (`Access-Control-Allow-Origin: *`, `POST`, `content-type`). Er is daarom **geen Cloudflare Worker** nodig.

## Lokaal starten

Vereist Node.js 18 of nieuwer. Er zijn geen npm-dependencies.

```bash
npm start
```

Open daarna `http://127.0.0.1:4173`. Een andere poort kan met de omgevingsvariabele `PORT`.

`server.mjs` is alleen een minimale statische fileserver voor lokaal gebruik. De demo zelf staat volledig in `web/` en draait in de browser.

Tests:

```bash
npm test
```

```bash
npm run test:live
```

`npm test` test de queryopbouw en geometrieverwerking zonder netwerk. `npm run test:live` test CORS, totalen, highlighting, facets, filteren, pagination en geometrie tegen de echte service.

## Deployment

De demo draait als Cloudflare Worker die alleen de statische bestanden uit `web/` serveert (Workers static assets, zonder Worker-script). De configuratie staat in `wrangler.jsonc`.

Automatisch: de GitHub-repository is gekoppeld via Workers Builds. Elke push naar `main` wordt automatisch gepubliceerd; pushes naar andere branches en pull requests krijgen een eigen preview-URL.

Handmatig (alleen nodig zonder koppeling):

```bash
npx wrangler deploy
```

## Architectuur

```text
Browser (web/index.html, app.js, search.js, geo.js)
   |
   |  POST JSON (query_string + filters + aggs + highlight)
   v
RCE Elasticsearch API
```

| Bestand | Rol |
|---|---|
| `web/search.js` | Veld-whitelist, queryopbouw, begrenzing, deelbare URL, uitleg in gewone taal, CSV, aanroep van de service en foutvertaling |
| `web/geo.js` | Geometrie uit `geoPoint` en `geo:asWKT` omzetten naar kaartcoördinaten |
| `web/app.js` | Interface: resultaten, facets, actieve filters, sorteren, export, pagination, kaart |
| `web/style.css` | RCE-huisstijl en layout: filters, resultaten en kaart naast elkaar op brede schermen, Lijst/Kaart-schakelaar op smalle schermen |

Externe onderdelen die in de browser worden geladen: Leaflet 1.9.4 (via unpkg, met SRI-hash) en de PDOK BRT-achtergrondkaart.

## Zoeksyntax

De demo gebruikt een Elasticsearch `query_string` query, zodat Booleaanse operatoren werken:

| Syntax | Betekenis | Voorbeeld |
|---|---|---|
| `AND` | beide voorwaarden | `kasteel AND gracht` |
| `OR` | minimaal één voorwaarde | `ijzer OR staal` |
| `NOT` | sluit uit | `kasteel AND NOT ruïne` |
| `"..."` | exacte woordcombinatie | `"gesmeed ijzer"` |
| `( ... )` | groeperen | `(kasteel OR buitenplaats) AND gracht` |
| `+` / `-` | moet / mag niet | `+kasteel -ruïne` |
| `"..."~5` | woorden binnen 5 posities | `"kasteel gracht"~5` |
| `*` / `?` | jokertekens (niet aan het begin) | `molen*`, `kast?el` |
| `~` | vergelijkbare spelling | `kasteeel~` |
| `~1` / `~2` | maximaal 1 of 2 tikfouten | `kastel~1` |
| `/…/` | patroon (reguliere expressie) | `/mol[ae]n/` |
| `^3` | zwaarder laten wegen (alleen volgorde) | `kasteel^3 OR gracht` |
| `_exists_:"…"` | veld wel/niet gevuld | `molen AND NOT _exists_:"https://schema org/name"` |

Nabijheid: er is geen `NEAR`/`ADJ`. `"a b"` betekent naast elkaar in deze volgorde, `"a b"~N` binnen N stappen (een woord ertussen kost 1, de volgorde omdraaien kost 2). "a vóór b binnen N woorden" en nabijheid met alternatieven (`(a OR b) NEAR c`) kunnen niet met `query_string`. Daarvoor zijn `intervals`- of `span_near`-queries nodig. Jokertekens werken niet binnen quotes.

Let op: operatoren alleen in hoofdletters (`and`, `en` en `of` zijn gewone zoekwoorden); zonder operator betekent een spatie `OR`; accenten tellen mee (`ruïne` ≠ `ruine`). De knop **Zoekhulp** in de demo legt dit uit met klikbare voorbeelden, en onder de zoekbalk verschijnt een tip als iemand `en`/`of`/`and` in kleine letters typt.

Een lege zoekvraag toont alle monumenten (`match_all`). Zo kun je ook alleen met facets verkennen.

## Gebruikte velden

Let op: in deze index staat in veldnamen een **spatie in plaats van een punt** in domeinnamen, dus `https://schema org/description` en niet `https://schema.org/description`.

| Keuze "Zoek in" | Elasticsearch-veld(en) |
|---|---|
| Omschrijving | `https://schema org/description` |
| Naam | `https://schema org/name` |
| Adres | `https://schema org/address` |
| Plaats | `https://schema org/addressLocality` |
| Type | `https://schema org/additionalType` |
| Alles | name, description, address, postalCode, addressLocality, addressRegion, category, additionalType, identifier |

Per resultaat: `identifier` (Rijksmonumentnummer), `name`, `address`, `postalCode`, `addressLocality`, `addressRegion`, `category`, `additionalType`, highlights (3 fragmenten van ca. 275 tekens), `@id` (Linked Data-URI) en `sameAs` (link naar het Monumentenregister). Voor de kaart: `geoPoint` en `http://www opengis net/ont/geosparql#asWKT`.

De query is altijd in te zien via **Toon Elasticsearch-query** onderaan de pagina.

## Facets

Facets zijn `terms`-aggregations op de `.keyword`-velden, in dezelfde request als de zoekopdracht:

| Facet | Veld |
|---|---|
| Provincie/regio | `https://schema org/addressRegion.keyword` |
| Plaats | `https://schema org/addressLocality.keyword` |
| Categorie | `https://schema org/category.keyword` |
| Type | `https://schema org/additionalType.keyword` |

Getest tegen de echte index: `kasteel AND gracht` geeft 124 resultaten, waarvan 29 in Gelderland. Na klikken op Gelderland is het totaal exact 29.

Facetwaarden zijn aan te vinken, ook meerdere binnen één facet. Binnen een facet geldt **of**, tussen facetten **en**. Zoeken (`query`) en filteren (`post_filter` met `terms`-clauses) zijn gescheiden:

```json
"query": { "query_string": { "query": "kasteel AND gracht", "fields": ["https://schema org/description"] } },
"post_filter": { "bool": { "filter": [
  { "terms": { "https://schema org/addressRegion.keyword": ["Gelderland", "Utrecht"] } }
] } },
"aggs": { "addressRegion": {
  "filter": { "bool": { "filter": [ /* filters van de andere facetten */ ] } },
  "aggs": { "values": { "terms": { "field": "https://schema org/addressRegion.keyword", "size": 100 } } }
} }
```

Elke facet telt met de filters van de *andere* facetten. Daardoor blijven na het aanvinken van Gelderland de andere provincies met hun aantallen zichtbaar, zodat je Utrecht erbij kunt kiezen (Gelderland 29 + Utrecht 14 = 43 resultaten). Per facet worden de 100 meest voorkomende waarden getoond; gekozen waarden blijven altijd zichtbaar. Actieve filters staan boven de resultaten en zijn los of allemaal tegelijk te verwijderen.

## Sorteren

| Keuze | Elasticsearch |
|---|---|
| Relevantie | standaard (`_score`) |
| Naam (A–Z) | `https://schema org/name.keyword` oplopend, zonder naam achteraan |
| Plaats (A–Z) | `https://schema org/addressLocality.keyword`, daarbinnen op naam |

Sorteren op Rijksmonumentnummer zit er bewust niet in: `identifier` staat als tekst in de index (dan komt 5 na 10040) en scripts zijn op de service uitgeschakeld.

## Deelbare URL

De URL bevat altijd de huidige zoekactie, bijvoorbeeld:

```text
?q=kasteel+AND+gracht&veld=Omschrijving&provincie=Gelderland&provincie=Utrecht&sorteer=naam&pagina=2
```

Parameters: `q`, `veld` (Omschrijving, Naam, Adres, Plaats, Type, Alles), `provincie`, `plaats`, `categorie`, `type` (herhaalbaar), `sorteer` (`naam`, `plaats`) en `pagina`. Onbekende waarden worden genegeerd. De knop **Kopieer link** zet de URL op het klembord. Terug en vooruit in de browser werken.

## Export naar CSV

**Download CSV** exporteert de huidige zoekactie (zoekvraag, filters en sortering) met maximaal 1.000 rijen: nummer, naam, adres, postcode, plaats, provincie/regio, categorie, type, Linked Data-URI, Monumentenregister-link en omschrijving. Het bestand gebruikt puntkomma's en UTF-8 met BOM, zodat het direct goed opent in een Nederlandse Excel. Waarden die met `=`, `+`, `-` of `@` beginnen krijgen een `'` ervoor, zodat een spreadsheet ze niet als formule uitvoert.

## Uitleg in gewone taal

Onder het totaal staat wat er gezocht wordt, bijvoorbeeld *"Zoekt in de omschrijving naar: kasteel én gracht · Alleen monumenten met provincie/regio “Gelderland” of “Utrecht”."* Onder **Toon Elasticsearch-query** staat dezelfde uitleg met sortering en pagina, naast de JSON.

## Huisstijl

De opmaak volgt de RCE Web Stijlgids en de rijkshuisstijl, met het Monumentenregister als voorbeeld: RCE-donkergeel `#ffb612` in een balk van 75px boven (kruimelpad) en onder (demo-waarschuwing), een grijze zoekband, zwarte tekst van 18px met regelhoogte 29.25px in RO Sans (met fallback Calibri, Verdana), donkerblauw `#01689b` voor links en knoppen, en geen uppercase of afwijkende tekstkleuren. Het rijkslogo/beeldmerk is bewust niet opgenomen: dit is een demo en geen officiële RCE-dienst. RO Sans wordt niet meegeleverd; staat het font niet op de computer, dan valt de pagina terug op Calibri of Verdana.

## Kaart

De kaart toont alle resultaten van de huidige pagina die een geometrie hebben, in deze volgorde:

1. `geoPoint`;
2. een `POINT` uit `geo:asWKT`;
3. een `POLYGON` of `MULTIPOLYGON` uit `geo:asWKT`. Het vlak wordt **als vlak getekend**. Het label met het Rijksmonumentnummer staat op het zwaartepunt van het grootste deelvlak.

WKT gebruikt `POINT(longitude latitude)`, Leaflet `[latitude, longitude]`. `geo.js` draait de volgorde om. WKT met een ander CRS dan WGS84/CRS84 (bijvoorbeeld RD, EPSG:28992) wordt overgeslagen.

Stand van de index bij het bouwen (oktober 2026): `geoPoint` en `geoShape` zijn bij **0** documenten gevuld. `geo:asWKT` is bij 63.084 van de 63.426 documenten gevuld, grotendeels met polygonen. Bij `kasteel AND gracht` staan op de eerste pagina 5 punten en 20 vlakken.

Gedrag:

- marker-labels tonen alleen het Rijksmonumentnummer;
- klikken op een marker of vlak selecteert het resultaat in de lijst;
- klikken op een resultaat (of "Toon op kaart") zoomt naar het punt of naar het hele vlak.

## Begrenzing en veiligheid

- maximaal 25 resultaten per pagina, met `from`/`size`; doorbladeren tot maximaal 10.000 resultaten; export maximaal 1.000 rijen;
- maximaal 20 gekozen waarden per facet;
- `track_total_hits: true` voor exacte totalen;
- zoekvelden en filtervelden komen uit een vaste whitelist; gebruikers kunnen geen veldnamen invoeren;
- zoekvraag maximaal 500 tekens, `allow_leading_wildcard: false`, servertimeout 15 s, clienttimeout 20 s;
- `_source` vraagt alleen de velden op die de interface gebruikt;
- links worden alleen getoond als ze `http(s)` zijn. De Monumentenregister-link alleen als het domein `monumentenregister.cultureelerfgoed.nl` is;
- brontekst en highlights worden als tekst in de pagina gezet, niet als HTML.

## Foutmeldingen

Gebruikers zien een korte melding bij: geen resultaten, ongeldige zoeksyntax (bijvoorbeeld een niet-gesloten haakje), service niet bereikbaar, timeout, onvolledig antwoord en een fout in de facetquery. Technische details staan in de browserconsole.

## Bekende beperkingen

- De kaart toont alleen de resultaten van de huidige pagina (25), niet alle treffers.
- Bij ver uitzoomen overlappen de nummerlabels.
- Monumenten zonder geometrie staan niet op de kaart. De teller "Op kaart" laat zien hoeveel er wel op staan.
- Sorteren op Rijksmonumentnummer kan niet (zie Sorteren).
- De CSV-export bevat maximaal 1.000 rijen.
- Leaflet en de achtergrondkaart komen van externe diensten (unpkg, PDOK).

## Cloudflare Worker

Niet gebouwd, want niet nodig: CORS werkt en de begrenzing zit in de frontend. Een Worker wordt pas zinvol als de service afgeschermd moet worden, als begrenzing server-side afgedwongen moet worden, of als caching nodig is.

## Demo verwijderen

1. Verwijder de Worker in het Cloudflare-dashboard (Workers & Pages → `rijksmonumenten-sdo-elastic-demo` → Settings → Delete) of met `npx wrangler delete`. Daarmee verdwijnt ook de Git-koppeling.
2. Verwijder uit deze repository `web/`, `tests/`, `server.mjs`, `package.json`, `wrangler.jsonc` en `.claude/launch.json`, en dit webdemo-gedeelte van de README.

Er is geen database, account, Worker of andere infrastructuur die opgeruimd moet worden.

---

# Python-verkenningsscripts

De Python-scripts hieronder zijn gebruikt om de Elasticsearch-service en de zoekmogelijkheden te verkennen. Ze zijn geen onderdeel van de webdemo.

In deze map staan vier Python-scripts waarmee je via de Elasticsearch-service van de RCE kunt zoeken in de Rijksmonumentendata.

De scripts lopen op in mogelijkheden:

- `elastic_triply_description.py` voor snel zoeken in de omschrijving
- `elastic_triply_uitgebreid.py` voor zoeken in meerdere velden, filters en CSV-export
- `rijksmonumenten_zoeker.py` voor dezelfde functionaliteit via een grafische interface
- `rijksmonumenten_zoeker_met_kaart.py` als grafische versie met kaart

## 1. elastic_triply_description.py

De eenvoudige versie.

Deze zoekt alleen in `schema:description`.

Voorbeelden:

```text
kasteel AND gracht
```

```text
ijzer OR staal
```

```text
kasteel AND NOT ruïne
```

```text
"Grote Scheer"
```

Je krijgt per resultaat onder andere:

- Rijksmonumentnummer
- naam
- URI
- adres
- postcode
- plaats
- regio
- categorie
- type
- link naar het Monumentenregister
- description
- het tekstfragment waarop de zoekopdracht matcht

Het script toont ook:

- het totale aantal gevonden resultaten
- het aantal daadwerkelijk opgehaalde resultaten

Starten:

```bash
python elastic_triply_description.py
```

---

## 2. elastic_triply_uitgebreid.py

De uitgebreide commandline-versie.

Naast zoeken in de omschrijving kun je kiezen uit:

- omschrijving
- naam
- adres
- plaats
- type
- alle beschikbare zoekvelden tegelijk

Je kunt daarnaast filteren op:

- plaats
- provincie/regio
- categorie
- type

Een zoekopdracht kan bijvoorbeeld zijn:

```text
(kasteel OR buitenplaats) AND gracht
```

met daarnaast als filter:

```text
Provincie/regio: Gelderland
```

Zoeken en filteren blijven daarmee gescheiden.

Het script gebruikt `track_total_hits`, zodat Elasticsearch het exacte totale aantal resultaten teruggeeft.

Na het zoeken kun je de opgehaalde resultaten exporteren naar CSV.

Starten:

```bash
python elastic_triply_uitgebreid.py
```

---

## 3. rijksmonumenten_zoeker.py

De grafische versie.

Deze gebruikt dezelfde Elasticsearch-service, maar je hoeft geen vragen meer in de terminal te beantwoorden.

Je krijgt een venster waarin je kunt:

- een zoekvraag invoeren
- een zoekveld kiezen
- filteren op plaats
- filteren op provincie/regio
- filteren op categorie
- filteren op type
- het maximum aantal op te halen resultaten instellen
- resultaten in een tabel bekijken
- de details van een monument bekijken
- resultaten naar CSV exporteren

Voorbeeld:

```text
Zoekvraag: kasteel AND gracht
Zoekveld: Omschrijving
Provincie/regio: Gelderland
```

Boven de resultaten zie je bijvoorbeeld:

```text
Totaal gevonden: 83 | Opgehaald: 83
```

Klik op een resultaat om onder andere de URI, locatiegegevens, description en het gematchte tekstfragment te bekijken.

Starten:

```bash
python rijksmonumenten_zoeker.py
```

## 4. rijksmonumenten_zoeker_met_kaart.py

Dezelfde grafische versie als `rijksmonumenten_zoeker.py`, met daarnaast een kaartweergave van de gevonden monumenten via `tkintermapview`.

Installatie en starten:

```bash
pip install requests tkintermapview
```

```bash
python rijksmonumenten_zoeker_met_kaart.py
```

## Zoeksyntax

De scripts gebruiken een Elasticsearch `query_string` query.

Daardoor kun je onder andere deze operatoren gebruiken:

| Syntax | Betekenis |
|---|---|
| `AND` | beide voorwaarden moeten voorkomen |
| `OR` | minimaal één voorwaarde moet voorkomen |
| `NOT` | sluit een voorwaarde uit |
| `"..."` | zoek een exacte woordcombinatie |
| `( ... )` | combineer voorwaarden |

Voorbeelden:

```text
ijzer AND brug
```

```text
ijzer OR staal
```

```text
kasteel AND NOT ruïne
```

```text
"gesmeed ijzer"
```

```text
(kasteel OR buitenplaats) AND gracht
```

## Installatie

De scripts gebruiken `requests`.

Installeer dit eenmalig met:

```bash
pip install requests
```

`rijksmonumenten_zoeker.py` gebruikt daarnaast `tkinter`. Dat zit bij een normale Windows-installatie van Python meestal al inbegrepen.

## Elasticsearch-service

De scripts zoeken in de Elasticsearch-service van de dataset `Rijksmonumenten-sdo`:

```text
https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/Rijksmonumenten-sdo/services/Rijksmonumenten-sdo-elas/_search
```

De scripts wijzigen geen data. Ze voeren alleen zoekopdrachten uit op de Elasticsearch-index.

## Dit is een demo
Deze scripts zijn bedoeld om te experimenteren met zoeken in de Rijksmonumentendata via Elasticsearch.
Bouw hier geen applicaties of andere afhankelijkheden op. De scripts, index en service kunnen zonder aankondiging wijzigen of verdwijnen.
