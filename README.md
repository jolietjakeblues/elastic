# Rijksmonumenten zoeken via Elasticsearch

In deze map staan drie Python-scripts waarmee je via de Elasticsearch-service van de RCE kunt zoeken in de Rijksmonumentendata.

De drie scripts lopen op in mogelijkheden:

- `simple.py` voor snel zoeken in de omschrijving
- `uitgebreid.py` voor zoeken in meerdere velden, filters en CSV-export
- `rijksmonumentenzoeker.py` voor dezelfde functionaliteit via een grafische interface

## 1. simple.py

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
python simple.py
```

---

## 2. uitgebreid.py

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
python uitgebreid.py
```

---

## 3. rijksmonumentenzoeker.py

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
python rijksmonumentenzoeker.py
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

`rijksmonumentenzoeker.py` gebruikt daarnaast `tkinter`. Dat zit bij een normale Windows-installatie van Python meestal al inbegrepen.

## Elasticsearch-service

De scripts zoeken in de Elasticsearch-service van de dataset `Rijksmonumenten-sdo`:

```text
https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/Rijksmonumenten-sdo/services/Rijksmonumenten-sdo-elas/_search
```

De scripts wijzigen geen data. Ze voeren alleen zoekopdrachten uit op de Elasticsearch-index.
