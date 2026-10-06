"""
RCE Rijksmonumentenzoeker
=========================

Demo om via Elasticsearch in de Rijksmonumentendata te zoeken.

Mogelijkheden
-------------

- zoeken met AND, OR, NOT, quotes en haakjes
- zoeken in:
    - omschrijving
    - naam
    - adres
    - plaats
    - type
    - alles
- filteren op:
    - plaats
    - provincie/regio
    - categorie
    - type
- exact totaal aantal resultaten via track_total_hits
- resultaten in een tabel
- volledige details per Rijksmonument
- Elasticsearch-highlights
- geo:asWKT tonen
- alle gevonden Rijksmonumenten tegelijk op een kaart
- klikken op een resultaat zoomt naar het monument
- klikken op een kaartmarker selecteert het resultaat
- CSV-export

Zoekvoorbeelden
---------------

    kasteel AND gracht

    ijzer OR staal

    kasteel AND NOT ruïne

    "Grote Scheer"

    (kasteel OR buitenplaats) AND gracht


Installatie
-----------

    pip install requests tkintermapview


LET OP
------

Dit is een demo.

Bouw hier geen applicaties of andere afhankelijkheden op.
De scripts, index en service kunnen wijzigen of verdwijnen.
"""

import csv
import html
import re
import threading
import tkinter as tk

from tkinter import ttk, filedialog, messagebox

import requests
import tkintermapview


# ============================================================
# INSTELLINGEN
# ============================================================

URL = (
    "https://api.linkeddata.cultureelerfgoed.nl/"
    "datasets/rce/Rijksmonumenten-sdo/"
    "services/Rijksmonumenten-sdo-elas/_search"
)

DEFAULT_MAX_RESULTATEN = 100

# Midden van Nederland als beginpositie
DEFAULT_LAT = 52.15
DEFAULT_LON = 5.30
DEFAULT_ZOOM = 7


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

WKT = "http://www opengis net/ont/geosparql#asWKT"

# Deze velden komen volgens de Elasticsearch-mapping
# ook rechtstreeks in de index voor.
GEOPOINT = "geoPoint"
GEOSHAPE = "geoShape"


ZOEKVELDEN = {
    "Omschrijving": [
        DESCRIPTION
    ],

    "Naam": [
        NAME
    ],

    "Adres": [
        ADDRESS
    ],

    "Plaats": [
        LOCALITY
    ],

    "Type": [
        ADDITIONAL_TYPE
    ],

    "Alles": [
        NAME,
        DESCRIPTION,
        ADDRESS,
        POSTAL_CODE,
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
    return ", ".join(
        str(item)
        for item in naar_lijst(waarde)
    )


def verwijder_highlight_tags(tekst):
    tekst = tekst.replace("<<<", "")
    tekst = tekst.replace(">>>", "")

    return html.unescape(tekst)


def voeg_exact_filter_toe(filters, veld, waarde):
    """
    Exact Elasticsearch-filter via het keyword-subveld.
    """

    waarde = waarde.strip()

    if waarde:
        filters.append(
            {
                "term": {
                    f"{veld}.keyword": waarde
                }
            }
        )


# ============================================================
# GEO
# ============================================================

def lees_geopoint(waarde):
    """
    Probeert verschillende mogelijke Elasticsearch-vormen
    van een geo_point te lezen.

    Mogelijke voorbeelden:

        {"lat": 52.1, "lon": 5.2}

        "52.1,5.2"

        [5.2, 52.1]

    Geeft terug:

        (latitude, longitude)

    of None.
    """

    if waarde is None:
        return None

    if isinstance(waarde, list):

        # GeoJSON/Elasticsearch array:
        # [longitude, latitude]
        if (
            len(waarde) == 2
            and isinstance(waarde[0], (int, float))
            and isinstance(waarde[1], (int, float))
        ):
            lon = float(waarde[0])
            lat = float(waarde[1])

            return lat, lon

        # Soms zit één object in een lijst
        for item in waarde:
            resultaat = lees_geopoint(item)

            if resultaat:
                return resultaat

        return None

    if isinstance(waarde, dict):

        if "lat" in waarde and "lon" in waarde:
            return (
                float(waarde["lat"]),
                float(waarde["lon"]),
            )

        if "lat" in waarde and "lng" in waarde:
            return (
                float(waarde["lat"]),
                float(waarde["lng"]),
            )

        return None

    if isinstance(waarde, str):

        # Bijvoorbeeld:
        # 52.1234,5.1234

        match = re.match(
            r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*"
            r"(-?\d+(?:\.\d+)?)\s*$",
            waarde
        )

        if match:
            lat = float(match.group(1))
            lon = float(match.group(2))

            return lat, lon

    return None


def lees_wkt_point(wkt):
    """
    Leest een POINT uit GeoSPARQL WKT.

    Ondersteunt bijvoorbeeld:

        POINT(5.123 52.123)

    en:

        <http://www.opengis.net/def/crs/EPSG/0/4326>
        POINT(5.123 52.123)

    WKT gebruikt:

        longitude latitude

    De kaart gebruikt:

        latitude longitude
    """

    if not wkt:
        return None

    if isinstance(wkt, list):

        for item in wkt:
            resultaat = lees_wkt_point(item)

            if resultaat:
                return resultaat

        return None

    tekst = str(wkt)

    match = re.search(
        r"POINT"
        r"(?:\s+Z|\s+M|\s+ZM)?"
        r"\s*\(\s*"
        r"(-?\d+(?:\.\d+)?)"
        r"\s+"
        r"(-?\d+(?:\.\d+)?)"
        r"(?:\s+[-\d.]+)?"
        r"\s*\)",
        tekst,
        re.IGNORECASE
    )

    if not match:
        return None

    lon = float(match.group(1))
    lat = float(match.group(2))

    # Alleen aannemelijke WGS84-coördinaten gebruiken.
    if not (-90 <= lat <= 90):
        return None

    if not (-180 <= lon <= 180):
        return None

    return lat, lon


def haal_coordinaten(bron):
    """
    Eerst geoPoint proberen.

    Als dat ontbreekt of niet leesbaar is:
    fallback naar geo:asWKT.
    """

    coords = lees_geopoint(
        bron.get(GEOPOINT)
    )

    if coords:
        return coords, "geoPoint"

    coords = lees_wkt_point(
        bron.get(WKT)
    )

    if coords:
        return coords, "geo:asWKT"

    return None, None


# ============================================================
# APPLICATIE
# ============================================================

class RijksmonumentenZoeker(tk.Tk):

    def __init__(self):

        super().__init__()

        self.title(
            "RCE Rijksmonumentenzoeker"
        )

        self.geometry(
            "1600x900"
        )

        self.minsize(
            1100,
            700
        )

        self.records = []
        self.hits = []

        self.markers = []

        self.maak_interface()


    # ========================================================
    # INTERFACE
    # ========================================================

    def maak_interface(self):

        hoofd = ttk.Frame(
            self,
            padding=10
        )

        hoofd.pack(
            fill="both",
            expand=True
        )


        # ----------------------------------------------------
        # ZOEKGEDEELTE
        # ----------------------------------------------------

        zoekframe = ttk.LabelFrame(
            hoofd,
            text="Zoeken",
            padding=10
        )

        zoekframe.pack(
            fill="x"
        )


        # ----------------------------------------------------
        # RIJ 1
        # ----------------------------------------------------

        ttk.Label(
            zoekframe,
            text="Zoekvraag:"
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=4
        )


        self.query_var = tk.StringVar()

        self.query_entry = ttk.Entry(
            zoekframe,
            textvariable=self.query_var
        )

        self.query_entry.grid(
            row=0,
            column=1,
            sticky="ew",
            pady=4
        )

        self.query_entry.bind(
            "<Return>",
            lambda event:
                self.start_zoeken()
        )


        ttk.Label(
            zoekframe,
            text="Zoekveld:"
        ).grid(
            row=0,
            column=2,
            sticky="w",
            padx=(15, 8)
        )


        self.zoekveld_var = tk.StringVar(
            value="Omschrijving"
        )

        self.zoekveld_combo = ttk.Combobox(
            zoekframe,
            textvariable=self.zoekveld_var,
            values=list(
                ZOEKVELDEN.keys()
            ),
            state="readonly",
            width=18
        )

        self.zoekveld_combo.grid(
            row=0,
            column=3,
            sticky="ew"
        )


        # ----------------------------------------------------
        # RIJ 2
        # ----------------------------------------------------

        ttk.Label(
            zoekframe,
            text="Plaats:"
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=4
        )

        self.plaats_var = tk.StringVar()

        ttk.Entry(
            zoekframe,
            textvariable=self.plaats_var
        ).grid(
            row=1,
            column=1,
            sticky="ew",
            pady=4
        )


        ttk.Label(
            zoekframe,
            text="Provincie/regio:"
        ).grid(
            row=1,
            column=2,
            sticky="w",
            padx=(15, 8)
        )

        self.regio_var = tk.StringVar()

        ttk.Entry(
            zoekframe,
            textvariable=self.regio_var
        ).grid(
            row=1,
            column=3,
            sticky="ew"
        )


        # ----------------------------------------------------
        # RIJ 3
        # ----------------------------------------------------

        ttk.Label(
            zoekframe,
            text="Categorie:"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=4
        )

        self.categorie_var = tk.StringVar()

        ttk.Entry(
            zoekframe,
            textvariable=self.categorie_var
        ).grid(
            row=2,
            column=1,
            sticky="ew"
        )


        ttk.Label(
            zoekframe,
            text="Type:"
        ).grid(
            row=2,
            column=2,
            sticky="w",
            padx=(15, 8)
        )

        self.type_var = tk.StringVar()

        ttk.Entry(
            zoekframe,
            textvariable=self.type_var
        ).grid(
            row=2,
            column=3,
            sticky="ew"
        )


        # ----------------------------------------------------
        # RIJ 4
        # ----------------------------------------------------

        ttk.Label(
            zoekframe,
            text="Max. resultaten:"
        ).grid(
            row=3,
            column=0,
            sticky="w",
            pady=(8, 4)
        )

        self.max_var = tk.StringVar(
            value=str(
                DEFAULT_MAX_RESULTATEN
            )
        )

        ttk.Entry(
            zoekframe,
            textvariable=self.max_var,
            width=10
        ).grid(
            row=3,
            column=1,
            sticky="w"
        )


        # ----------------------------------------------------
        # KNOPPEN
        # ----------------------------------------------------

        knoppen = ttk.Frame(
            zoekframe
        )

        knoppen.grid(
            row=3,
            column=2,
            columnspan=2,
            sticky="e",
            pady=(8, 0)
        )


        self.zoekknop = ttk.Button(
            knoppen,
            text="Zoeken",
            command=self.start_zoeken
        )

        self.zoekknop.pack(
            side="left",
            padx=4
        )


        ttk.Button(
            knoppen,
            text="Alle op kaart",
            command=self.toon_alle_op_kaart
        ).pack(
            side="left",
            padx=4
        )


        ttk.Button(
            knoppen,
            text="Wissen",
            command=self.wissen
        ).pack(
            side="left",
            padx=4
        )


        self.export_knop = ttk.Button(
            knoppen,
            text="CSV exporteren",
            command=self.exporteer_csv,
            state="disabled"
        )

        self.export_knop.pack(
            side="left",
            padx=4
        )


        zoekframe.columnconfigure(
            1,
            weight=1
        )

        zoekframe.columnconfigure(
            3,
            weight=1
        )


        # ----------------------------------------------------
        # HULPREGEL
        # ----------------------------------------------------

        ttk.Label(
            hoofd,
            text=(
                'Voorbeeld: '
                'kasteel AND gracht   |   '
                'ijzer OR staal   |   '
                '"Grote Scheer"   |   '
                '(kasteel OR buitenplaats) AND gracht'
            )
        ).pack(
            anchor="w",
            pady=(5, 6)
        )


        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status_var = tk.StringVar(
            value=(
                "Nog geen zoekopdracht uitgevoerd."
            )
        )

        ttk.Label(
            hoofd,
            textvariable=self.status_var
        ).pack(
            anchor="w",
            pady=(0, 8)
        )


        # ====================================================
        # HOOFDDEEL
        # ====================================================

        hoofd_pane = ttk.Panedwindow(
            hoofd,
            orient="horizontal"
        )

        hoofd_pane.pack(
            fill="both",
            expand=True
        )


        # ====================================================
        # LINKS
        # ====================================================

        links = ttk.Panedwindow(
            hoofd_pane,
            orient="vertical"
        )

        hoofd_pane.add(
            links,
            weight=1
        )


        # ----------------------------------------------------
        # RESULTATENTABEL
        # ----------------------------------------------------

        resultaat_frame = ttk.LabelFrame(
            links,
            text="Resultaten",
            padding=5
        )

        links.add(
            resultaat_frame,
            weight=2
        )


        kolommen = (
            "nummer",
            "naam",
            "plaats",
            "type",
            "adres"
        )


        self.tabel = ttk.Treeview(
            resultaat_frame,
            columns=kolommen,
            show="headings",
            selectmode="browse"
        )


        self.tabel.heading(
            "nummer",
            text="Rijksmonument"
        )

        self.tabel.heading(
            "naam",
            text="Naam"
        )

        self.tabel.heading(
            "plaats",
            text="Plaats"
        )

        self.tabel.heading(
            "type",
            text="Type"
        )

        self.tabel.heading(
            "adres",
            text="Adres"
        )


        self.tabel.column(
            "nummer",
            width=100,
            anchor="w"
        )

        self.tabel.column(
            "naam",
            width=230
        )

        self.tabel.column(
            "plaats",
            width=140
        )

        self.tabel.column(
            "type",
            width=170
        )

        self.tabel.column(
            "adres",
            width=220
        )


        tabel_scroll_y = ttk.Scrollbar(
            resultaat_frame,
            orient="vertical",
            command=self.tabel.yview
        )

        tabel_scroll_x = ttk.Scrollbar(
            resultaat_frame,
            orient="horizontal",
            command=self.tabel.xview
        )


        self.tabel.configure(
            yscrollcommand=
                tabel_scroll_y.set,

            xscrollcommand=
                tabel_scroll_x.set
        )


        self.tabel.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        tabel_scroll_y.grid(
            row=0,
            column=1,
            sticky="ns"
        )

        tabel_scroll_x.grid(
            row=1,
            column=0,
            sticky="ew"
        )


        resultaat_frame.rowconfigure(
            0,
            weight=1
        )

        resultaat_frame.columnconfigure(
            0,
            weight=1
        )


        self.tabel.bind(
            "<<TreeviewSelect>>",
            self.toon_details
        )


        # ----------------------------------------------------
        # DETAILS
        # ----------------------------------------------------

        detail_frame = ttk.LabelFrame(
            links,
            text="Details",
            padding=5
        )

        links.add(
            detail_frame,
            weight=1
        )


        self.details = tk.Text(
            detail_frame,
            wrap="word",
            height=14
        )

        detail_scroll = ttk.Scrollbar(
            detail_frame,
            orient="vertical",
            command=self.details.yview
        )

        self.details.configure(
            yscrollcommand=
                detail_scroll.set
        )


        self.details.pack(
            side="left",
            fill="both",
            expand=True
        )

        detail_scroll.pack(
            side="right",
            fill="y"
        )


        # ====================================================
        # RECHTS: KAART
        # ====================================================

        kaart_frame = ttk.LabelFrame(
            hoofd_pane,
            text="Kaart",
            padding=5
        )

        hoofd_pane.add(
            kaart_frame,
            weight=1
        )


        self.kaart = (
            tkintermapview.TkinterMapView(
                kaart_frame,
                corner_radius=0
            )
        )

        self.kaart.pack(
            fill="both",
            expand=True
        )


        self.kaart.set_position(
            DEFAULT_LAT,
            DEFAULT_LON
        )

        self.kaart.set_zoom(
            DEFAULT_ZOOM
        )


        self.query_entry.focus_set()


    # ========================================================
    # ZOEKEN STARTEN
    # ========================================================

    def start_zoeken(self):

        query = (
            self.query_var
            .get()
            .strip()
        )

        # Lege zoekvraag betekent:
        # alles zoeken.
        if not query:
            query = "*"


        try:

            max_resultaten = int(
                self.max_var.get()
            )

            if max_resultaten < 1:
                raise ValueError

        except ValueError:

            messagebox.showwarning(
                "Ongeldig aantal",
                (
                    "Max. resultaten moet "
                    "een positief getal zijn."
                )
            )

            return


        # Alle Tkinter-waarden hier ophalen.
        # De worker-thread hoeft dan niet
        # aan Tkinter-variabelen te komen.

        instellingen = {

            "query":
                query,

            "zoekveld":
                self.zoekveld_var.get(),

            "plaats":
                self.plaats_var.get(),

            "regio":
                self.regio_var.get(),

            "categorie":
                self.categorie_var.get(),

            "type":
                self.type_var.get(),

            "max":
                max_resultaten,
        }


        self.zoekknop.configure(
            state="disabled"
        )

        self.export_knop.configure(
            state="disabled"
        )

        self.status_var.set(
            "Zoeken..."
        )


        thread = threading.Thread(
            target=self.zoek,
            args=(instellingen,),
            daemon=True
        )

        thread.start()


    # ========================================================
    # ELASTICSEARCH
    # ========================================================

    def zoek(self, instellingen):

        try:

            query = instellingen[
                "query"
            ]

            zoekveld = instellingen[
                "zoekveld"
            ]

            max_resultaten = instellingen[
                "max"
            ]


            velden = ZOEKVELDEN[
                zoekveld
            ]


            filters = []


            voeg_exact_filter_toe(
                filters,
                LOCALITY,
                instellingen["plaats"]
            )

            voeg_exact_filter_toe(
                filters,
                REGION,
                instellingen["regio"]
            )

            voeg_exact_filter_toe(
                filters,
                CATEGORY,
                instellingen["categorie"]
            )

            voeg_exact_filter_toe(
                filters,
                ADDITIONAL_TYPE,
                instellingen["type"]
            )


            tekst_query = {
                "query_string": {
                    "query": query,
                    "fields": velden
                }
            }


            if filters:

                elastic_query = {
                    "bool": {

                        "must": [
                            tekst_query
                        ],

                        "filter":
                            filters
                    }
                }

            else:

                elastic_query = (
                    tekst_query
                )


            body = {

                "size":
                    max_resultaten,

                "track_total_hits":
                    True,

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
                    WKT,
                    GEOPOINT,
                    GEOSHAPE,
                ],

                "query":
                    elastic_query,

                "highlight": {

                    "fields": {
                        veld: {
                            "fragment_size": 300,
                            "number_of_fragments": 3
                        }
                        for veld in velden
                    },

                    "pre_tags": [
                        "<<<"
                    ],

                    "post_tags": [
                        ">>>"
                    ]
                }
            }


            response = requests.post(
                URL,
                json=body,
                timeout=60
            )

            response.raise_for_status()

            resultaat = (
                response.json()
            )


            self.after(
                0,
                self.verwerk_resultaten,
                resultaat
            )


        except requests.RequestException as fout:

            self.after(
                0,
                self.toon_fout,
                str(fout)
            )


        except Exception as fout:

            self.after(
                0,
                self.toon_fout,
                str(fout)
            )


    # ========================================================
    # RESULTATEN VERWERKEN
    # ========================================================

    def verwerk_resultaten(
        self,
        resultaat
    ):

        self.zoekknop.configure(
            state="normal"
        )


        self.tabel.delete(
            *self.tabel.get_children()
        )


        self.details.delete(
            "1.0",
            "end"
        )


        self.verwijder_markers()


        hits_info = resultaat.get(
            "hits",
            {}
        )


        self.hits = hits_info.get(
            "hits",
            []
        )


        totaal_info = hits_info.get(
            "total",
            0
        )


        if isinstance(
            totaal_info,
            dict
        ):

            totaal = (
                totaal_info.get(
                    "value",
                    0
                )
            )

        else:

            totaal = totaal_info


        self.records = []


        # ----------------------------------------------------
        # RECORDS MAKEN
        # ----------------------------------------------------

        for index, hit in enumerate(
            self.hits
        ):

            bron = hit.get(
                "_source",
                {}
            )


            coords, geo_bron = (
                haal_coordinaten(
                    bron
                )
            )


            record = {

                "rijksmonumentnummer":
                    naar_tekst(
                        bron.get(
                            IDENTIFIER
                        )
                    ),

                "naam":
                    naar_tekst(
                        bron.get(
                            NAME
                        )
                    ),

                "uri":
                    naar_tekst(
                        bron.get(
                            "@id"
                        )
                    ),

                "adres":
                    naar_tekst(
                        bron.get(
                            ADDRESS
                        )
                    ),

                "postcode":
                    naar_tekst(
                        bron.get(
                            POSTAL_CODE
                        )
                    ),

                "plaats":
                    naar_tekst(
                        bron.get(
                            LOCALITY
                        )
                    ),

                "regio":
                    naar_tekst(
                        bron.get(
                            REGION
                        )
                    ),

                "categorie":
                    naar_tekst(
                        bron.get(
                            CATEGORY
                        )
                    ),

                "type":
                    naar_tekst(
                        bron.get(
                            ADDITIONAL_TYPE
                        )
                    ),

                "monumentenregister":
                    naar_tekst(
                        bron.get(
                            SAME_AS
                        )
                    ),

                "description":
                    naar_tekst(
                        bron.get(
                            DESCRIPTION
                        )
                    ),

                "wkt":
                    naar_tekst(
                        bron.get(
                            WKT
                        )
                    ),

                "coords":
                    coords,

                "geo_bron":
                    geo_bron,
            }


            # -----------------------------------------------
            # HIGHLIGHTS
            # -----------------------------------------------

            highlights = []


            for fragmenten in (
                hit
                .get(
                    "highlight",
                    {}
                )
                .values()
            ):

                for fragment in fragmenten:

                    highlights.append(
                        verwijder_highlight_tags(
                            fragment
                        )
                    )


            record["match"] = (
                "\n\n".join(
                    highlights
                )
            )


            self.records.append(
                record
            )


            self.tabel.insert(
                "",
                "end",
                iid=str(index),
                values=(

                    record[
                        "rijksmonumentnummer"
                    ],

                    record[
                        "naam"
                    ],

                    record[
                        "plaats"
                    ],

                    record[
                        "type"
                    ],

                    record[
                        "adres"
                    ]
                )
            )


        # ----------------------------------------------------
        # KAART
        # ----------------------------------------------------

        aantal_op_kaart = (
            self.plaats_markers()
        )


        self.status_var.set(
            f"Totaal gevonden: {totaal}"
            f"   |   "
            f"Opgehaald: "
            f"{len(self.records)}"
            f"   |   "
            f"Op kaart: "
            f"{aantal_op_kaart}"
        )


        if self.records:

            self.export_knop.configure(
                state="normal"
            )


            eerste = (
                self.tabel
                .get_children()[0]
            )

            self.tabel.selection_set(
                eerste
            )

            self.tabel.focus(
                eerste
            )

            self.toon_details()

            self.toon_alle_op_kaart()


        else:

            self.status_var.set(
                "Geen resultaten gevonden."
            )


    # ========================================================
    # MARKERS
    # ========================================================

    def verwijder_markers(self):

        self.kaart.delete_all_marker()

        self.markers = []


    def plaats_markers(self):

        self.verwijder_markers()

        aantal = 0


        for index, record in enumerate(
            self.records
        ):

            coords = record[
                "coords"
            ]

            if not coords:
                continue


            lat, lon = coords


            naam = (
                record["naam"]
                or "Rijksmonument"
            )

            nummer = (
                record[
                    "rijksmonumentnummer"
                ]
            )


            if nummer:
                label = (
                    f"{nummer} - {naam}"
                )
            else:
                label = naam


            marker = (
                self.kaart.set_marker(
                    lat,
                    lon,
                    text=label,
                    command=
                        self.marker_geklikt
                )
            )


            # Eigen koppeling tussen
            # kaartmarker en tabelrecord.
            marker.data = index


            self.markers.append(
                marker
            )

            aantal += 1


        return aantal


    def marker_geklikt(
        self,
        marker
    ):

        try:
            index = marker.data

        except AttributeError:
            return


        iid = str(index)


        if iid not in (
            self.tabel
            .get_children()
        ):
            return


        self.tabel.selection_set(
            iid
        )

        self.tabel.focus(
            iid
        )

        self.tabel.see(
            iid
        )

        self.toon_details(
            zoom_naar_resultaat=False
        )


    # ========================================================
    # ALLE RESULTATEN OP KAART
    # ========================================================

    def toon_alle_op_kaart(self):

        coordinaten = [
            record["coords"]
            for record
            in self.records
            if record["coords"]
        ]


        if not coordinaten:

            self.kaart.set_position(
                DEFAULT_LAT,
                DEFAULT_LON
            )

            self.kaart.set_zoom(
                DEFAULT_ZOOM
            )

            return


        if len(coordinaten) == 1:

            lat, lon = (
                coordinaten[0]
            )

            self.kaart.set_position(
                lat,
                lon
            )

            self.kaart.set_zoom(
                17
            )

            return


        latitudes = [
            coord[0]
            for coord in coordinaten
        ]

        longitudes = [
            coord[1]
            for coord in coordinaten
        ]


        noord = max(
            latitudes
        )

        zuid = min(
            latitudes
        )

        west = min(
            longitudes
        )

        oost = max(
            longitudes
        )


        # TkinterMapView verwacht:
        #
        # top-left:
        #     noord, west
        #
        # bottom-right:
        #     zuid, oost

        self.kaart.fit_bounding_box(
            (noord, west),
            (zuid, oost)
        )


    # ========================================================
    # DETAILS
    # ========================================================

    def toon_details(
        self,
        event=None,
        zoom_naar_resultaat=True
    ):

        selectie = (
            self.tabel.selection()
        )

        if not selectie:
            return


        index = int(
            selectie[0]
        )


        record = (
            self.records[index]
        )


        regels = []


        velden = [

            (
                "Rijksmonumentnummer",
                record[
                    "rijksmonumentnummer"
                ]
            ),

            (
                "Naam",
                record[
                    "naam"
                ]
            ),

            (
                "URI",
                record[
                    "uri"
                ]
            ),

            (
                "Adres",
                record[
                    "adres"
                ]
            ),

            (
                "Postcode",
                record[
                    "postcode"
                ]
            ),

            (
                "Plaats",
                record[
                    "plaats"
                ]
            ),

            (
                "Regio",
                record[
                    "regio"
                ]
            ),

            (
                "Categorie",
                record[
                    "categorie"
                ]
            ),

            (
                "Type",
                record[
                    "type"
                ]
            ),

            (
                "Monumentenregister",
                record[
                    "monumentenregister"
                ]
            )
        ]


        for label, waarde in velden:

            if waarde:

                regels.append(
                    f"{label}: {waarde}"
                )


        # ----------------------------------------------------
        # GEO
        # ----------------------------------------------------

        if record["coords"]:

            lat, lon = (
                record["coords"]
            )

            regels.append("")

            regels.append(
                f"Latitude: {lat}"
            )

            regels.append(
                f"Longitude: {lon}"
            )

            regels.append(
                "Kaartbron geometrie: "
                f"{record['geo_bron']}"
            )


        if record["wkt"]:

            regels.append("")

            regels.append(
                "geo:asWKT:"
            )

            regels.append(
                record["wkt"]
            )


        # ----------------------------------------------------
        # MATCH
        # ----------------------------------------------------

        if record["match"]:

            regels.append("")

            regels.append(
                "MATCH:"
            )

            regels.append(
                record["match"]
            )


        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        if record["description"]:

            regels.append("")

            regels.append(
                "DESCRIPTION:"
            )

            regels.append(
                record[
                    "description"
                ]
            )


        self.details.delete(
            "1.0",
            "end"
        )

        self.details.insert(
            "1.0",
            "\n".join(
                regels
            )
        )


        # ----------------------------------------------------
        # KAART NAAR GESELECTEERD RESULTAAT
        # ----------------------------------------------------

        if (
            zoom_naar_resultaat
            and record["coords"]
        ):

            lat, lon = (
                record["coords"]
            )

            self.kaart.set_position(
                lat,
                lon
            )

            self.kaart.set_zoom(
                17
            )


    # ========================================================
    # CSV EXPORT
    # ========================================================

    def exporteer_csv(self):

        if not self.records:
            return


        bestandsnaam = (
            filedialog
            .asksaveasfilename(

                title=(
                    "Resultaten opslaan"
                ),

                defaultextension=(
                    ".csv"
                ),

                filetypes=[
                    (
                        "CSV-bestand",
                        "*.csv"
                    )
                ],

                initialfile=(
                    "rijksmonumenten.csv"
                )
            )
        )


        if not bestandsnaam:
            return


        try:

            with open(
                bestandsnaam,
                "w",
                newline="",
                encoding="utf-8-sig"
            ) as csvfile:


                fieldnames = [

                    "rijksmonumentnummer",
                    "naam",
                    "uri",
                    "adres",
                    "postcode",
                    "plaats",
                    "regio",
                    "categorie",
                    "type",
                    "monumentenregister",
                    "latitude",
                    "longitude",
                    "geo_bron",
                    "wkt",
                    "match",
                    "description",
                ]


                writer = csv.DictWriter(
                    csvfile,
                    fieldnames=fieldnames,
                    delimiter=";"
                )


                writer.writeheader()


                for record in (
                    self.records
                ):

                    coords = (
                        record["coords"]
                    )


                    if coords:

                        latitude = (
                            coords[0]
                        )

                        longitude = (
                            coords[1]
                        )

                    else:

                        latitude = ""
                        longitude = ""


                    writer.writerow(
                        {

                            "rijksmonumentnummer":
                                record[
                                    "rijksmonumentnummer"
                                ],

                            "naam":
                                record[
                                    "naam"
                                ],

                            "uri":
                                record[
                                    "uri"
                                ],

                            "adres":
                                record[
                                    "adres"
                                ],

                            "postcode":
                                record[
                                    "postcode"
                                ],

                            "plaats":
                                record[
                                    "plaats"
                                ],

                            "regio":
                                record[
                                    "regio"
                                ],

                            "categorie":
                                record[
                                    "categorie"
                                ],

                            "type":
                                record[
                                    "type"
                                ],

                            "monumentenregister":
                                record[
                                    "monumentenregister"
                                ],

                            "latitude":
                                latitude,

                            "longitude":
                                longitude,

                            "geo_bron":
                                record[
                                    "geo_bron"
                                ],

                            "wkt":
                                record[
                                    "wkt"
                                ],

                            "match":
                                record[
                                    "match"
                                ],

                            "description":
                                record[
                                    "description"
                                ],
                        }
                    )


            messagebox.showinfo(
                "CSV opgeslagen",
                (
                    f"{len(self.records)} "
                    "resultaten opgeslagen."
                )
            )


        except OSError as fout:

            messagebox.showerror(
                "Fout bij opslaan",
                str(fout)
            )


    # ========================================================
    # WISSEN
    # ========================================================

    def wissen(self):

        self.query_var.set(
            ""
        )

        self.plaats_var.set(
            ""
        )

        self.regio_var.set(
            ""
        )

        self.categorie_var.set(
            ""
        )

        self.type_var.set(
            ""
        )

        self.zoekveld_var.set(
            "Omschrijving"
        )

        self.max_var.set(
            str(
                DEFAULT_MAX_RESULTATEN
            )
        )


        self.records = []
        self.hits = []


        self.tabel.delete(
            *self.tabel.get_children()
        )


        self.details.delete(
            "1.0",
            "end"
        )


        self.verwijder_markers()


        self.kaart.set_position(
            DEFAULT_LAT,
            DEFAULT_LON
        )

        self.kaart.set_zoom(
            DEFAULT_ZOOM
        )


        self.status_var.set(
            "Nog geen zoekopdracht uitgevoerd."
        )


        self.export_knop.configure(
            state="disabled"
        )


        self.query_entry.focus_set()


    # ========================================================
    # FOUT
    # ========================================================

    def toon_fout(
        self,
        fout
    ):

        self.zoekknop.configure(
            state="normal"
        )

        self.status_var.set(
            "Zoeken mislukt."
        )

        messagebox.showerror(
            "Fout",
            fout
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    app = RijksmonumentenZoeker()

    app.mainloop()