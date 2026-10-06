"""
Rijksmonumenten zoeken in de Elasticsearch-index van de RCE.

HULP
===============

Dit script zoekt in de omschrijving (schema:description)
van Rijksmonumenten.

Je typt bij "Zoekvraag" zelf de zoekopdracht.

Voorbeelden:

    ijzer OR staal

    ijzer AND staal

    ijzer NOT staal

    kasteel AND gracht

    (ijzer OR staal) AND brug

    "gietijzer"

    "gesmeed ijzer" OR gietijzer

    (kasteel OR buitenplaats) AND gracht


BETEKENIS

AND
    Beide voorwaarden moeten voorkomen.

    kasteel AND gracht


OR
    Minimaal één van de voorwaarden moet voorkomen.

    ijzer OR staal


NOT
    Sluit een term uit.

    kasteel AND NOT ruïne


"..."
    Zoek een exacte woordcombinatie.

    "Grote Scheer"


(...)
    Gebruik haakjes om voorwaarden te combineren.

    (ijzer OR staal) AND brug


Het script toont:

- totaal aantal gevonden Rijksmonumenten
- aantal opgehaalde resultaten
- Rijksmonumentnummer
- naam
- URI
- adres
- postcode
- plaats
- regio/provincie
- categorie
- additionalType
- sameAs
- omschrijving
- het tekstfragment waarop de zoekterm matcht

Standaard worden maximaal 100 resultaten opgehaald.

Benodigd:

    pip install requests
"""

import requests


# ============================================================
# INSTELLINGEN
# ============================================================

URL = (
    "https://api.linkeddata.cultureelerfgoed.nl/"
    "datasets/rce/Rijksmonumenten-sdo/"
    "services/Rijksmonumenten-sdo-elas/_search"
)

MAX_RESULTATEN = 100


# ============================================================
# VELDEN IN DE ELASTICSEARCH-INDEX
# ============================================================

DESCRIPTION = "https://schema org/description"
IDENTIFIER = "https://schema org/identifier"
NAME = "https://schema org/name"
ADDRESS = "https://schema org/address"
POSTAL_CODE = "https://schema org/postalCode"
LOCALITY = "https://schema org/addressLocality"
REGION = "https://schema org/addressRegion"
CATEGORY = "https://schema org/category"
ADDITIONAL_TYPE = "https://schema org/additionalType"
SAME_AS = "https://schema org/sameAs"


# ============================================================
# HULPFUNCTIES
# ============================================================

def naar_tekst(waarde):
    """
    Zet een Elasticsearch-waarde om naar leesbare tekst.
    """

    if waarde is None:
        return ""

    if isinstance(waarde, list):
        return ", ".join(str(item) for item in waarde)

    return str(waarde)


def toon_veld(label, waarde):
    """
    Toon een veld alleen wanneer het een waarde bevat.
    """

    tekst = naar_tekst(waarde)

    if tekst:
        print(f"{label}: {tekst}")


def haal_totaal_op(resultaat):
    """
    Elasticsearch kan hits.total als object teruggeven:

        {
            "value": 123,
            "relation": "eq"
        }

    Deze functie verwerkt beide vormen.
    """

    totaal_info = resultaat.get("hits", {}).get("total", 0)

    if isinstance(totaal_info, dict):
        return (
            totaal_info.get("value", 0),
            totaal_info.get("relation", "eq")
        )

    return totaal_info, "eq"


# ============================================================
# START
# ============================================================

print()
print("Rijksmonumenten zoeken")
print("=" * 70)
print()
print("Er wordt gezocht in schema:description.")
print()
print("Voorbeelden:")
print("  ijzer OR staal")
print("  ijzer AND staal")
print("  kasteel AND gracht")
print("  (ijzer OR staal) AND brug")
print('  "Grote Scheer"')
print()

query = input("Zoekvraag: ").strip()

if not query:
    print()
    print("Geen zoekvraag opgegeven.")
    raise SystemExit


# ============================================================
# ELASTICSEARCH QUERY
# ============================================================

body = {
    "size": MAX_RESULTATEN,

    "query": {
        "query_string": {
            "query": query,
            "fields": [
                DESCRIPTION
            ]
        }
    },

    "highlight": {
        "fields": {
            DESCRIPTION: {
                "fragment_size": 300,
                "number_of_fragments": 3
            }
        },
        "pre_tags": ["<<<"],
        "post_tags": [">>>"]
    }
}


# ============================================================
# REQUEST UITVOEREN
# ============================================================

try:

    response = requests.post(
        URL,
        json=body,
        timeout=60
    )

    response.raise_for_status()

except requests.exceptions.Timeout:

    print()
    print("De zoekopdracht duurde te lang.")
    raise SystemExit

except requests.exceptions.HTTPError as fout:

    print()
    print("Elasticsearch gaf een fout terug.")
    print()
    print(f"HTTP-status: {response.status_code}")

    try:
        print(response.json())
    except ValueError:
        print(response.text)

    raise SystemExit

except requests.exceptions.RequestException as fout:

    print()
    print("Fout bij het uitvoeren van de zoekopdracht:")
    print(fout)

    raise SystemExit


# ============================================================
# RESULTAAT VERWERKEN
# ============================================================

try:

    resultaat = response.json()

except ValueError:

    print()
    print("De server gaf geen geldige JSON terug.")
    print(response.text)

    raise SystemExit


hits = resultaat.get("hits", {}).get("hits", [])

totaal, relatie = haal_totaal_op(resultaat)


# ============================================================
# AANTALLEN TONEN
# ============================================================

print()
print("=" * 70)

if relatie == "gte":
    print(f"Totaal gevonden: minimaal {totaal}")
else:
    print(f"Totaal gevonden: {totaal}")

print(f"Opgehaald: {len(hits)}")

if totaal > len(hits):
    print(
        f"Let op: alleen de eerste {MAX_RESULTATEN} "
        f"resultaten worden getoond."
    )

print("=" * 70)
print()


# ============================================================
# GEEN RESULTATEN
# ============================================================

if not hits:

    print("Geen Rijksmonumenten gevonden.")
    raise SystemExit


# ============================================================
# RESULTATEN TONEN
# ============================================================

for nummer, hit in enumerate(hits, start=1):

    bron = hit.get("_source", {})

    print(f"RESULTAAT {nummer}")
    print("-" * 70)

    toon_veld(
        "Rijksmonumentnummer",
        bron.get(IDENTIFIER)
    )

    toon_veld(
        "Naam",
        bron.get(NAME)
    )

    toon_veld(
        "URI",
        bron.get("@id")
    )

    toon_veld(
        "Adres",
        bron.get(ADDRESS)
    )

    toon_veld(
        "Postcode",
        bron.get(POSTAL_CODE)
    )

    toon_veld(
        "Plaats",
        bron.get(LOCALITY)
    )

    toon_veld(
        "Regio",
        bron.get(REGION)
    )

    toon_veld(
        "Categorie",
        bron.get(CATEGORY)
    )

    toon_veld(
        "Additional type",
        bron.get(ADDITIONAL_TYPE)
    )

    toon_veld(
        "SameAs",
        bron.get(SAME_AS)
    )

    print()

    # --------------------------------------------------------
    # MATCH TONEN
    # --------------------------------------------------------

    highlights = (
        hit
        .get("highlight", {})
        .get(DESCRIPTION, [])
    )

    if highlights:

        print("MATCH:")
        print()

        for fragment in highlights:
            print(fragment)
            print()

    # --------------------------------------------------------
    # VOLLEDIGE DESCRIPTION TONEN
    # --------------------------------------------------------

    descriptions = bron.get(DESCRIPTION)

    if descriptions:

        print("DESCRIPTION:")
        print()

        if isinstance(descriptions, list):

            for description in descriptions:
                print(description)
                print()

        else:
            print(descriptions)
            print()

    print("=" * 70)
    print()