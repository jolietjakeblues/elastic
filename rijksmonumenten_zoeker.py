"""
Rijksmonumentenzoeker
=====================

Eenvoudige grafische zoekinterface voor de Elasticsearch-index
Rijksmonumenten-sdo van de RCE.

Mogelijkheden:
- zoeken met AND, OR, NOT, quotes en haakjes
- kiezen in welk veld gezocht wordt
- filteren op plaats, provincie/regio, categorie en type
- exact totaal aantal resultaten tonen
- resultaten in een tabel bekijken
- volledige gegevens van een geselecteerd monument bekijken
- resultaten exporteren naar CSV

Voorbeelden:

    kasteel AND gracht

    ijzer OR staal

    kasteel AND NOT ruïne

    "Grote Scheer"

    (kasteel OR buitenplaats) AND gracht

Benodigd:

    pip install requests
"""

import csv
import html
import re
import threading
import tkinter as tk

from tkinter import ttk, filedialog, messagebox

import requests


# ============================================================
# INSTELLINGEN
# ============================================================

URL = (
    "https://api.linkeddata.cultureelerfgoed.nl/"
    "datasets/rce/Rijksmonumenten-sdo/"
    "services/Rijksmonumenten-sdo-elas/_search"
)

DEFAULT_MAX_RESULTATEN = 100


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
    "Omschrijving": [DESCRIPTION],
    "Naam": [NAME],
    "Adres": [ADDRESS],
    "Plaats": [LOCALITY],
    "Type": [ADDITIONAL_TYPE],

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
    return ", ".join(str(x) for x in naar_lijst(waarde))


def verwijder_highlight_tags(tekst):
    """
    Verwijdert de <<< >>> markers uit Elasticsearch-highlights.
    """
    tekst = tekst.replace("<<<", "")
    tekst = tekst.replace(">>>", "")
    return html.unescape(tekst)


def voeg_exact_filter_toe(filters, veld, waarde):
    """
    Exact filter op het keyword-subveld.
    """
    waarde = waarde.strip()

    if waarde:
        filters.append({
            "term": {
                f"{veld}.keyword": waarde
            }
        })


# ============================================================
# APPLICATIE
# ============================================================

class RijksmonumentenZoeker(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("RCE Rijksmonumentenzoeker")
        self.geometry("1250x850")
        self.minsize(950, 650)

        self.records = []
        self.hits = []

        self.maak_interface()


    # ========================================================
    # INTERFACE
    # ========================================================

    def maak_interface(self):

        hoofd = ttk.Frame(self, padding=12)
        hoofd.pack(fill="both", expand=True)

        # ----------------------------------------------------
        # ZOEKGEDEELTE
        # ----------------------------------------------------

        zoekframe = ttk.LabelFrame(
            hoofd,
            text="Zoeken",
            padding=10
        )

        zoekframe.pack(fill="x")

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
            lambda event: self.start_zoeken()
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
            values=list(ZOEKVELDEN.keys()),
            state="readonly",
            width=16
        )

        self.zoekveld_combo.grid(
            row=0,
            column=3,
            sticky="w"
        )


        # ----------------------------------------------------
        # FILTERS
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
            sticky="ew",
            pady=4
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
        # MAXIMUM
        # ----------------------------------------------------

        ttk.Label(
            zoekframe,
            text="Max. resultaten:"
        ).grid(
            row=3,
            column=0,
            sticky="w",
            pady=4
        )

        self.max_var = tk.StringVar(
            value=str(DEFAULT_MAX_RESULTATEN)
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

        knoppen = ttk.Frame(zoekframe)

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
        # VOORBEELD
        # ----------------------------------------------------

        ttk.Label(
            hoofd,
            text=(
                'Voorbeeld: kasteel AND gracht   |   '
                'ijzer OR staal   |   '
                '"Grote Scheer"   |   '
                '(kasteel OR buitenplaats) AND gracht'
            )
        ).pack(
            anchor="w",
            pady=(5, 8)
        )


        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status_var = tk.StringVar(
            value="Nog geen zoekopdracht uitgevoerd."
        )

        ttk.Label(
            hoofd,
            textvariable=self.status_var
        ).pack(
            anchor="w",
            pady=(0, 8)
        )


        # ----------------------------------------------------
        # RESULTATENTABEL
        # ----------------------------------------------------

        resultaat_frame = ttk.LabelFrame(
            hoofd,
            text="Resultaten",
            padding=5
        )

        resultaat_frame.pack(
            fill="both",
            expand=True
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
            width=110,
            anchor="w"
        )

        self.tabel.column(
            "naam",
            width=260
        )

        self.tabel.column(
            "plaats",
            width=160
        )

        self.tabel.column(
            "type",
            width=180
        )

        self.tabel.column(
            "adres",
            width=250
        )


        scrollbar_y = ttk.Scrollbar(
            resultaat_frame,
            orient="vertical",
            command=self.tabel.yview
        )

        scrollbar_x = ttk.Scrollbar(
            resultaat_frame,
            orient="horizontal",
            command=self.tabel.xview
        )

        self.tabel.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set
        )


        self.tabel.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        scrollbar_y.grid(
            row=0,
            column=1,
            sticky="ns"
        )

        scrollbar_x.grid(
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
            hoofd,
            text="Details",
            padding=5
        )

        detail_frame.pack(
            fill="both",
            expand=True,
            pady=(10, 0)
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
            yscrollcommand=detail_scroll.set
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


        self.query_entry.focus_set()


    # ========================================================
    # ZOEKEN
    # ========================================================

    def start_zoeken(self):

        query = self.query_var.get().strip()

        if not query:

            messagebox.showwarning(
                "Geen zoekvraag",
                "Vul eerst een zoekvraag in."
            )

            return


        try:
            max_resultaten = int(
                self.max_var.get()
            )

            if max_resultaten < 1:
                raise ValueError

        except ValueError:

            messagebox.showwarning(
                "Ongeldig aantal",
                "Max. resultaten moet een positief getal zijn."
            )

            return


        self.zoekknop.configure(
            state="disabled"
        )

        self.export_knop.configure(
            state="disabled"
        )

        self.status_var.set(
            "Zoeken..."
        )

        self.update_idletasks()


        thread = threading.Thread(
            target=self.zoek,
            args=(query, max_resultaten),
            daemon=True
        )

        thread.start()


    def zoek(self, query, max_resultaten):

        try:

            zoekveld = self.zoekveld_var.get()

            velden = ZOEKVELDEN[
                zoekveld
            ]


            filters = []

            voeg_exact_filter_toe(
                filters,
                LOCALITY,
                self.plaats_var.get()
            )

            voeg_exact_filter_toe(
                filters,
                REGION,
                self.regio_var.get()
            )

            voeg_exact_filter_toe(
                filters,
                CATEGORY,
                self.categorie_var.get()
            )

            voeg_exact_filter_toe(
                filters,
                ADDITIONAL_TYPE,
                self.type_var.get()
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
                        "filter": filters
                    }
                }

            else:

                elastic_query = tekst_query


            body = {

                "size": max_resultaten,

                "track_total_hits": True,

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
                    DESCRIPTION
                ],

                "query": elastic_query,

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

            resultaat = response.json()


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

    def verwerk_resultaten(self, resultaat):

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

            totaal = totaal_info.get(
                "value",
                0
            )

        else:

            totaal = totaal_info


        self.records = []


        for index, hit in enumerate(
            self.hits
        ):

            bron = hit.get(
                "_source",
                {}
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
                    )
            }


            highlights = []

            for fragmenten in (
                hit
                .get("highlight", {})
                .values()
            ):

                for fragment in fragmenten:

                    highlights.append(
                        verwijder_highlight_tags(
                            fragment
                        )
                    )


            record["match"] = "\n".join(
                highlights
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


        self.status_var.set(
            f"Totaal gevonden: {totaal}   |   "
            f"Opgehaald: {len(self.records)}"
        )


        if self.records:

            self.export_knop.configure(
                state="normal"
            )

            eerste = self.tabel.get_children()[0]

            self.tabel.selection_set(
                eerste
            )

            self.tabel.focus(
                eerste
            )

            self.toon_details()

        else:

            self.status_var.set(
                "Geen resultaten gevonden."
            )


    # ========================================================
    # DETAILS
    # ========================================================

    def toon_details(self, event=None):

        selectie = self.tabel.selection()

        if not selectie:
            return


        index = int(
            selectie[0]
        )

        record = self.records[
            index
        ]


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


        if record["match"]:

            regels.append("")
            regels.append("MATCH:")
            regels.append(
                record["match"]
            )


        if record["description"]:

            regels.append("")
            regels.append("DESCRIPTION:")
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
            "\n".join(regels)
        )


    # ========================================================
    # CSV EXPORT
    # ========================================================

    def exporteer_csv(self):

        if not self.records:
            return


        bestandsnaam = filedialog.asksaveasfilename(

            title="Resultaten opslaan",

            defaultextension=".csv",

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


        if not bestandsnaam:
            return


        try:

            with open(
                bestandsnaam,
                "w",
                newline="",
                encoding="utf-8-sig"
            ) as csvfile:

                writer = csv.DictWriter(

                    csvfile,

                    fieldnames=[
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
                        "match",
                        "description"
                    ],

                    delimiter=";"
                )

                writer.writeheader()

                writer.writerows(
                    self.records
                )


            messagebox.showinfo(
                "CSV opgeslagen",
                f"{len(self.records)} resultaten opgeslagen."
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

        self.query_var.set("")
        self.plaats_var.set("")
        self.regio_var.set("")
        self.categorie_var.set("")
        self.type_var.set("")

        self.zoekveld_var.set(
            "Omschrijving"
        )

        self.max_var.set(
            str(DEFAULT_MAX_RESULTATEN)
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

    def toon_fout(self, fout):

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
# START PROGRAMMA
# ============================================================

if __name__ == "__main__":

    app = RijksmonumentenZoeker()
    app.mainloop()