## Zoeken in Rijksmonumenten via Elasticsearch

In deze map staat een eenvoudig Python-script waarmee je via de Elasticsearch-service van de RCE kunt zoeken in de Rijksmonumentendata.

Voor nu zoekt het script alleen in `schema:description`.

### Voorbeelden

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
"gesmeed ijzer"
```

Je kunt ook voorwaarden combineren:

```text
(kasteel OR buitenplaats) AND gracht
```

### Wat krijg je terug?

Per resultaat toont het script onder andere:

- Rijksmonumentnummer
- naam
- URI
- adres
- postcode
- plaats
- provincie/regio
- categorie
- type
- link naar het Monumentenregister
- description
- het tekstfragment waarin de zoekterm is gevonden

Bovenaan zie je ook hoeveel resultaten Elasticsearch in totaal heeft gevonden en hoeveel daarvan zijn opgehaald.

### Gebruik

Installeer eerst `requests` als dat nog niet aanwezig is:

```bash
pip install requests
```

Start daarna het script:

```bash
python zoeken.py
```

Vul vervolgens je zoekvraag in, bijvoorbeeld:

```text
ijzer AND brug
```

### Elasticsearch

Het script gebruikt de Elasticsearch-service van de dataset `Rijksmonumenten-sdo`:

```text
https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/Rijksmonumenten-sdo/services/Rijksmonumenten-sdo-elas/_search
```

De zoekopdracht gebruikt een `query_string` query. Daardoor kun je gewone Booleaanse operatoren gebruiken zoals `AND`, `OR` en `NOT`.
