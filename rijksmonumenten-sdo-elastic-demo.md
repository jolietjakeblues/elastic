# Rijksmonumenten SDO/Elastic demo

## Doel

Een kleine webdemo maken die laat zien wat er **meer kan met de SDO/Elasticsearch-publicatie van Rijksmonumenten** dan alleen een klassieke zoekinterface.

De demo is nadrukkelijk **geen vervanging van het Monumentenregister** en geen productieapplicatie. Het doel is om de mogelijkheden van de publicatielaag zichtbaar te maken:

- fulltext zoeken;
- Booleaans zoeken;
- zoeken in meerdere velden;
- filteren en facetteren;
- resultaten op een kaart tonen;
- zoekmatches zichtbaar maken;
- direct doorklikken naar de Linked Data-URI;
- direct doorklikken naar het Monumentenregister;
- laten zien hoe Elasticsearch bovenop de Linked Data-publicatie gebruikt kan worden.

## Belangrijk uitgangspunt

> ## Dit is een demo
>
> Deze demo is bedoeld om te experimenteren met zoeken in de Rijksmonumentendata via Elasticsearch.
>
> Bouw hier geen applicaties of andere afhankelijkheden op. De scripts, index en service kunnen zonder aankondiging wijzigen of verdwijnen.

De demo moet dus ook eenvoudig weer weggegooid kunnen worden.

---

# Elasticsearch-service

We gebruiken de Elasticsearch-service van de dataset `Rijksmonumenten-sdo`:

```text
https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/Rijksmonumenten-sdo/services/Rijksmonumenten-sdo-elas/_search
```

Zoeken gebeurt met een HTTP `POST` met een JSON-body.

Voorbeeld:

```json
{
  "query": {
    "query_string": {
      "query": "kasteel AND gracht",
      "fields": [
        "https://schema org/description"
      ]
    }
  }
}
```

## Waarom `query_string`

In een eerste versie gebruikten we `simple_query_string`. Daarbij werken de woorden `AND`, `OR` en `NOT` niet als de normale Booleaanse operatoren.

Daarom gebruiken de scripts nu `query_string`.

Hiermee werkt dit zoals je verwacht:

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

```text
(kasteel OR buitenplaats) AND gracht
```

---

# Relevante velden

De huidige Elasticsearch-mapping bevat onder andere:

```text
@id
geoPoint
geoShape
http://www opengis net/ont/geosparql#asWKT
http://www w3 org/1999/02/22-rdf-syntax-ns#type
https://linkeddata cultureelerfgoed nl/def/ceo#msp_indicatie
https://schema org/additionalType
https://schema org/address
https://schema org/addressLocality
https://schema org/addressRegion
https://schema org/category
https://schema org/description
https://schema org/identifier
https://schema org/name
https://schema org/postalCode
https://schema org/sameAs
```

Let op dat de veldnamen in de Elasticsearch-index spaties bevatten waar in de oorspronkelijke URI punten staan, bijvoorbeeld:

```text
https://schema org/description
```

en niet:

```text
https://schema.org/description
```

---

# Wat we al hebben gemaakt

Er zijn drie Python-varianten bedacht.

## 1. `simple.py`

Eenvoudige commandline-versie.

Zoekt alleen in:

```text
schema:description
```

Ondersteunt onder andere:

- `AND`
- `OR`
- `NOT`
- exacte frases met `"..."`;
- haakjes.

Geeft per resultaat terug:

- Rijksmonumentnummer;
- naam;
- URI;
- adres;
- postcode;
- plaats;
- provincie/regio;
- categorie;
- type;
- link naar het Monumentenregister;
- description;
- tekstfragment waarop de zoekopdracht matcht.

Daarnaast:

- exact totaal aantal gevonden resultaten;
- aantal daadwerkelijk opgehaalde resultaten.

## 2. `uitgebreid.py`

Uitgebreide commandline-versie.

Kan zoeken in:

- description;
- name;
- address;
- place;
- type;
- alle zoekvelden tegelijk.

Kan daarnaast filteren op:

- plaats;
- provincie/regio;
- categorie;
- type.

Heeft CSV-export.

Gebruikt:

```python
"track_total_hits": True
```

zodat het totale aantal matches exact wordt teruggegeven.

## 3. `rijksmonumentenzoeker.py`

Grafische Tkinter-versie.

Bevat:

- zoekveld;
- keuze van zoekveld;
- filters;
- resultatenlijst;
- detailweergave;
- highlights;
- exacte aantallen;
- CSV-export;
- kaartweergave.

Voor de kaart is `tkintermapview` gebruikt.

Installatie:

```bash
pip install requests tkintermapview
```

---

# Geo en kaart

De Elasticsearch-index bevat:

```text
geoPoint
geoShape
http://www opengis net/ont/geosparql#asWKT
```

Voor de eerste kaartdemo gebruiken we bij voorkeur:

1. `geoPoint`;
2. als fallback `geo:asWKT` wanneer daarin een `POINT` staat.

Belangrijk bij WKT:

```text
POINT(longitude latitude)
```

Een kaartbibliotheek verwacht meestal:

```text
latitude, longitude
```

Dus die volgorde moet worden omgedraaid.

## Huidige kaartgedachte

Alle opgehaalde zoekresultaten met een bruikbare puntgeometrie tegelijk op de kaart tonen.

Bijvoorbeeld:

```text
Totaal gevonden: 213 | Opgehaald: 100 | Op kaart: 97
```

Gedrag:

- na zoeken worden alle beschikbare punten getoond;
- klikken op een zoekresultaat zoomt naar dat monument;
- klikken op een kaartmarker selecteert het zoekresultaat;
- op de kaart staat als label alleen het Rijksmonumentnummer, bijvoorbeeld:

```text
452714
```

en niet:

```text
452714 - Parkflat Marlot
```

## Polygonen

`POLYGON` en `MULTIPOLYGON` zijn besproken, maar nog niet uitgewerkt in de huidige versie.

Dat kan later.

Eerst controleren welke geometrieën daadwerkelijk in `geoPoint`, `geoShape` en `geo:asWKT` voorkomen en in welk CRS ze staan.

Voor nu: puntgeometrieën zijn voldoende voor de demo.

---

# Idee voor de webdemo

De webdemo moet niet proberen het bestaande Monumentenregister na te bouwen.

Het interessante verhaal is:

> Wat kun je doen als je Rijksmonumentendata publiceert als SDO/Linked Data en daar een Elasticsearch-index bovenop zet?

Daarom ligt de nadruk op functies die de publicatielaag zichtbaar maken.

## Functies

### Zoeken

- fulltext in `description`;
- zoeken in `name`;
- zoeken in adres;
- zoeken in plaats;
- zoeken in type;
- zoeken in meerdere velden tegelijk;
- Booleaanse zoekvragen.

Voorbeelden:

```text
kasteel AND gracht
```

```text
ijzer OR staal
```

```text
(kasteel OR buitenplaats) AND gracht
```

```text
"gesmeed ijzer"
```

### Filters

Onder andere:

- provincie;
- plaats;
- categorie;
- additionalType/type.

Zoeken en filteren blijven conceptueel gescheiden.

Bijvoorbeeld:

```text
Zoekvraag:
kasteel AND gracht

Filter:
Provincie = Gelderland
```

### Facets

Dit is een belangrijk onderdeel van de demo.

Bijvoorbeeld bij:

```text
kasteel OR buitenplaats
```

zou je aantallen kunnen tonen zoals:

```text
Provincie

Gelderland      214
Utrecht          87
Limburg          74
```

en:

```text
Type

Kasteel         163
Buitenplaats    121
Landhuis         48
```

Facets laten goed zien wat Elasticsearch bovenop de Linked Data-publicatie toevoegt.

### Resultaten

Per resultaat bijvoorbeeld:

- Rijksmonumentnummer;
- naam;
- plaats;
- adres;
- type;
- categorie;
- gematcht tekstfragment;
- description;
- URI;
- link naar het Monumentenregister.

### Kaart

Mogelijkheden:

- alle gevonden resultaten tegelijk;
- lijst/kaart-weergave;
- marker met Rijksmonumentnummer;
- klikken op kaart koppelen aan resultaat;
- klikken op resultaat koppelen aan kaart;
- later eventueel polygonen.

### Linked Data zichtbaar maken

Directe URI tonen, bijvoorbeeld:

```text
https://linkeddata.cultureelerfgoed.nl/cho-kennis/id/rijksmonument/79296
```

Daarnaast kan de link naar het Monumentenregister zichtbaar blijven:

```text
https://monumentenregister.cultureelerfgoed.nl/monumenten/452714
```

Zo wordt de relatie tussen:

```text
zoekindex
→ SDO-document
→ Linked Data URI
→ bron / verdere relaties
```

zichtbaar.

### Zoekmatch/highlighting

Elasticsearch-highlighting gebruiken om te laten zien waarom een resultaat gevonden is.

Bijvoorbeeld:

```text
...omgeven door een gracht en behorend bij het kasteel...
```

Dit is vooral nuttig bij fulltextzoekvragen.

### Eventueel later

- sorteren op relevantie;
- sorteren op naam;
- sorteren op Rijksmonumentnummer;
- URL met zoekparameters zodat een zoekopdracht deelbaar wordt;
- knop `toon Elasticsearch-query`;
- eenvoudige uitleg van de onderliggende query;
- aggregaties/facets uitbreiden;
- polygonen;
- geografisch filteren op kaartgebied;
- download/export.

---

# Naam

Werknaam:

```text
Rijksmonumenten SDO/Elastic demo
```

Die naam maakt duidelijk dat het om een technische demonstrator gaat en niet om een nieuw Monumentenregister.

---

# Webtechniek

Voor de webdemo is Python niet nodig.

Python was handig om de API en queries snel te verkennen.

Voor de website ligt JavaScript meer voor de hand.

## Voorgestelde architectuur

Eerste eenvoudige variant:

```text
Browser
   |
   v
HTML / CSS / JavaScript
   |
   v
RCE Elasticsearch API
```

Hosting kan bijvoorbeeld via Cloudflare.

Als rechtstreeks vanuit de browser zoeken goed werkt en CORS geen probleem vormt, is dit voor een wegwerpbare demo voldoende.

## Eventuele Worker ertussen

Als we meer controle willen:

```text
Browser
   |
   v
Frontend
   |
   v
Cloudflare Worker
   |
   v
RCE Elasticsearch API
```

Een Worker is nuttig om:

- toegestane velden te begrenzen;
- zoekinvoer te valideren;
- maximale `size` af te dwingen;
- Elasticsearch-queries centraal te beheren;
- CORS-problemen af te vangen;
- caching toe te voegen;
- de frontend los te koppelen van de precieze indexstructuur.

Voor een eerste demo kunnen we simpel beginnen en alleen een Worker toevoegen als daar een reden voor is.

---

# Voorgestelde interface

Globaal:

```text
+-------------------------------------------------------------+
| Rijksmonumenten SDO/Elastic demo                            |
|                                                             |
| [ zoekvraag...................................... ] [Zoek]   |
|                                                             |
| Zoek in: [Omschrijving v]                                   |
+----------------------+--------------------------------------+
| FILTERS / FACETS     | RESULTATEN                            |
|                      |                                      |
| Provincie            | 452714 Parkflat Marlot               |
| Gelderland (214)     | 's-Gravenhage                        |
| Utrecht (87)         | ...match uit description...          |
| Limburg (74)         |                                      |
|                      | [Linked Data] [Monumentenregister]    |
| Type                 |                                      |
| Kasteel (163)        | ...                                  |
| Buitenplaats (121)   |                                      |
+----------------------+--------------------------------------+
|                  KAART / LIJST                              |
+-------------------------------------------------------------+
```

Mogelijk een schakelaar:

```text
[ Lijst ] [ Kaart ]
```

of lijst en kaart naast elkaar op brede schermen.

---

# Technisch interessante Elasticsearch-functionaliteit

Voor de demo zijn vooral deze onderdelen relevant:

## `query_string`

Voor Booleaanse fulltextzoekvragen.

## `track_total_hits`

```json
"track_total_hits": true
```

Voor exacte aantallen.

## `_source`

Alleen de velden terugvragen die in de UI nodig zijn.

## `highlight`

Voor de gematchte stukken tekst.

## `term` filters op `.keyword`

Voor exacte filters op bijvoorbeeld:

- plaats;
- provincie;
- categorie;
- type.

## aggregations

Nog te bouwen.

Deze zijn nodig voor facets met aantallen.

Bijvoorbeeld conceptueel:

```json
"aggs": {
  "provincies": {
    "terms": {
      "field": "https://schema org/addressRegion.keyword"
    }
  }
}
```

Dit moeten we morgen testen tegen de echte index.

---

# Eerste werk voor morgen

## Stap 1

Kleine HTML/JS-demo maken met:

- zoekveld;
- `query_string`;
- zoeken in `description`;
- totaal aantal;
- eerste resultaten;
- Rijksmonumentnummer;
- naam;
- plaats;
- description;
- Linked Data-URI;
- link Monumentenregister;
- highlighting.

## Stap 2

Zoekveldkeuze toevoegen:

- description;
- name;
- address;
- place;
- type;
- alles.

## Stap 3

Facets testen met Elasticsearch aggregations:

- provincie;
- plaats;
- categorie;
- additionalType.

Eerst vaststellen dat de `.keyword`-velden en aggregaties zich gedragen zoals verwacht.

## Stap 4

Filters koppelen aan facets.

Een klik op bijvoorbeeld:

```text
Gelderland (214)
```

voegt een exact filter toe.

## Stap 5

Kaart toevoegen.

Eerst alleen:

```text
geoPoint
```

en eventueel `POINT` uit `geo:asWKT` als fallback.

Alle opgehaalde resultaten tegelijk tonen.

Markertekst:

```text
Rijksmonumentnummer
```

## Stap 6

Beslissen of een Cloudflare Worker nodig is.

Eerst testen:

- kan browser rechtstreeks POST'en naar de Elasticsearch-service?
- staat CORS dit toe?
- willen we de Elasticsearch-query rechtstreeks vanuit de browser zichtbaar maken?

Als rechtstreeks werkt en het alleen een demo blijft, kan de frontend rechtstreeks tegen Elasticsearch praten.

Anders:

```text
frontend → Worker → Elasticsearch
```

---

# Ontwerpprincipe

Hou het klein.

De waarde van deze demo zit niet in een grote applicatie, maar in het zichtbaar maken van:

```text
Linked Data
+
SDO-publicatie
+
Elasticsearch
=
zoeken, combineren, filteren, facetteren en geografisch verkennen
```

De demo moet makkelijk te begrijpen, aan te passen en weer weg te gooien zijn.
