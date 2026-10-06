"""
Rijksmonumenten zoeken via Elasticsearch
=========================================

Voorbeelden zoekvragen:

    kasteel AND gracht
    ijzer OR staal
    kasteel AND NOT ruïne
    "Grote Scheer"
    (kasteel OR buitenplaats) AND gracht

Je kunt zoeken in:

    description
    name
    address
    place
    type
    all

Daarnaast kun je filteren op:

    plaats
    provincie/regio
    categorie
    type

Resultaten kunnen naar CSV worden weggeschreven.

Benodigd:

    pip install requests
"""

import csv
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
# ELASTICSEARCH-VELDEN
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


ZOEKVELDEN = {
    "description": [DESCRIPTION],
    "name": [NAME],
    "address": [ADDRESS],
    "place": [LOCALITY],
    "type": [ADDITIONAL_TYPE],
    "all": [
        NAME,
        DESCRIPTION,
        ADDRESS,
        LOCALITY,
        REGION,
        CATEGORY,
        ADDITIONAL_TYPE,
        IDENTIFIER,
    ],
}


# ============================================================
# HULPFUNCTIES
# ============================================================

def naar_lijst(waarde):
    if waarde is None:
        return []

    if isinstance(waarde, list):
        return waarde

    return [waarde]


def naar_tekst(waarde):
    return ", ".join(str(x) for x in naar_lijst(waarde))


def toon_veld(label, waarde):
    tekst = naar_tekst(waarde)

    if tekst:
        print(f"{label}: {tekst}")


def vraag(prompt):
    return input(prompt).strip()


def voeg_filter_toe(filters, veld, waarde):
    """
    Exact filter via het keyword-subveld.
    """

    if waarde:
        filters.append({
            "term": {
                f"{veld}.keyword": waarde
            }
        })


# ============================================================
# INVOER
# ============================================================

print()
print("Rijksmonumenten zoeken")
print("=" * 70)
print()

print("Voorbeelden:")
print("  kasteel AND gracht")
print("  ijzer OR staal")
print('  "Grote Scheer"')
print("  (kasteel OR buitenplaats) AND gracht")
print()

query = vraag("Zoekvraag: ")

if not query:
    raise SystemExit("Geen zoekvraag opgegeven.")

print()
print("Zoekveld:")
print("  1. description")
print("  2. name")
print("  3. address")
print("  4. place")
print("  5. type")
print("  6. all")

keuze = vraag("Keuze [1]: ") or "1"

veld_keuzes = {
    "1": "description",
    "2": "name",
    "3": "address",
    "4": "place",
    "5": "type",
    "6": "all",
}

zoekveld = veld_keuzes.get(keuze, "description")
velden = ZOEKVELDEN[zoekveld]


# ============================================================
# OPTIONELE FILTERS
# ============================================================

print()
print("Optionele filters. Enter = overslaan.")
print()

plaats = vraag("Plaats: ")
regio = vraag("Provincie/regio: ")
categorie = vraag("Categorie: ")
type_filter = vraag("Type: ")

filters = []

voeg_filter_toe(filters, LOCALITY, plaats)
voeg_filter_toe(filters, REGION, regio)
voeg_filter_toe(filters, CATEGORY, categorie)
voeg_filter_toe(filters, ADDITIONAL_TYPE, type_filter)


# ============================================================
# ELASTICSEARCH-QUERY
# ============================================================

query_string = {
    "query_string": {
        "query": query,
        "fields": velden,
    }
}

if filters:

    elastic_query = {
        "bool": {
            "must": query_string,
            "filter": filters,
        }
    }

else:

    elastic_query = query_string


body = {
    "size": MAX_RESULTATEN,

    # Zorg dat ook bij grote resultaatsets het echte aantal
    # wordt geteld.
    "track_total_hits": True,

    "query": elastic_query,

    # Alleen velden ophalen die we gebruiken.
    "_source": [
        "@id",
        IDENTIFIER,
        NAME,
        ADDRESS,
        POSTAL_CODE,
        LOCALITY,
        REGION,
        CATEGORY,
        ADDITIONAL_TYPE,
        SAME_AS,
        DESCRIPTION,
    ],

    "highlight": {
        "fields": {
            veld: {
                "fragment_size": 250,
                "number_of_fragments": 3,
            }
            for veld in velden
        },
        "pre_tags": ["<<<"],
        "post_tags": [">>>"],
    },
}


# ============================================================
# REQUEST
# ============================================================

try:

    response = requests.post(
        URL,
        json=body,
        timeout=60,
    )

    response.raise_for_status()

except requests.exceptions.RequestException as fout:

    print()
    print("Fout bij Elasticsearch:")
    print(fout)

    if "response" in locals():
        print(response.text)

    raise SystemExit


resultaat = response.json()


# ============================================================
# RESULTATEN
# ============================================================

hits_info = resultaat.get("hits", {})
hits = hits_info.get("hits", [])

totaal_info = hits_info.get("total", 0)

if isinstance(totaal_info, dict):
    totaal = totaal_info.get("value", 0)
else:
    totaal = totaal_info


print()
print("=" * 70)
print(f"Zoekvraag: {query}")
print(f"Zoekveld: {zoekveld}")
print(f"Totaal gevonden: {totaal}")
print(f"Opgehaald: {len(hits)}")
print("=" * 70)
print()


# ============================================================
# RESULTATEN OMZETTEN
# ============================================================

records = []


for nummer, hit in enumerate(hits, start=1):

    bron = hit.get("_source", {})

    record = {
        "rijksmonumentnummer": naar_tekst(bron.get(IDENTIFIER)),
        "naam": naar_tekst(bron.get(NAME)),
        "uri": naar_tekst(bron.get("@id")),
        "adres": naar_tekst(bron.get(ADDRESS)),
        "postcode": naar_tekst(bron.get(POSTAL_CODE)),
        "plaats": naar_tekst(bron.get(LOCALITY)),
        "regio": naar_tekst(bron.get(REGION)),
        "categorie": naar_tekst(bron.get(CATEGORY)),
        "type": naar_tekst(bron.get(ADDITIONAL_TYPE)),
        "monumentenregister": naar_tekst(bron.get(SAME_AS)),
        "description": naar_tekst(bron.get(DESCRIPTION)),
    }

    records.append(record)

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
        "Type",
        bron.get(ADDITIONAL_TYPE)
    )

    toon_veld(
        "Monumentenregister",
        bron.get(SAME_AS)
    )


    # --------------------------------------------------------
    # HIGHLIGHTS
    # --------------------------------------------------------

    highlights = hit.get("highlight", {})

    if highlights:

        print()
        print("MATCH:")

        for veld, fragmenten in highlights.items():

            for fragment in fragmenten:
                print(f"  {fragment}")


    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    descriptions = naar_lijst(bron.get(DESCRIPTION))

    if descriptions:

        print()
        print("DESCRIPTION:")

        for description in descriptions:
            print(description)

    print()
    print("=" * 70)
    print()


# ============================================================
# CSV EXPORT
# ============================================================

if records:

    export = vraag(
        "Resultaten naar CSV schrijven? [j/N]: "
    ).lower()

    if export in {"j", "ja", "y", "yes"}:

        bestandsnaam = vraag(
            "Bestandsnaam [rijksmonumenten.csv]: "
        )

        if not bestandsnaam:
            bestandsnaam = "rijksmonumenten.csv"

        if not bestandsnaam.lower().endswith(".csv"):
            bestandsnaam += ".csv"

        with open(
            bestandsnaam,
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as csvfile:

            writer = csv.DictWriter(
                csvfile,
                fieldnames=records[0].keys(),
                delimiter=";",
            )

            writer.writeheader()
            writer.writerows(records)

        print()
        print(
            f"{len(records)} resultaten geschreven naar "
            f"{bestandsnaam}"
        )