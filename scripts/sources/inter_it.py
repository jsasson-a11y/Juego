"""Inter: official all-time top scorers (official competitions) from the club
site inter.it -- top 10 only.

Source: https://www.inter.it/it/notizie/classifica-marcatori-inter
("I MIGLIORI MARCATORI DELLA STORIA DELL'INTER", "ultimo aggiornamento: <date>")
robots.txt: "User-agent: * / Disallow:" (everything allowed).

Run from repo root:  python3 scripts/sources/inter_it.py
"""
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from _common import Fetcher, clean, write_csv  # noqa: E402

SITE = "inter_it"
URL = "https://www.inter.it/it/notizie/classifica-marcatori-inter"
MESI = {m: i + 1 for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
                                         "agosto", "settembre", "ottobre", "novembre", "dicembre"])}
# Alternative spellings (added by us, not from the source).
ALIASES = {"Luigi Cevenini III": "Luigi Cevenini III|Cevenini III", "Istvan Nyers": "István Nyers|Stefano Nyers",
           "Lautaro Martinez": "Lautaro Martínez|Lautaro"}


def main():
    f = Fetcher(SITE)
    soup = BeautifulSoup(f.get(URL), "lxml")
    text = clean(soup.get_text(" "))
    fecha = ""
    m = re.search(r"ultimo aggiornamento:?\s*(\d{1,2})\s+(\w+)\s+(\d{4})", text, re.I)
    if m and m.group(2).lower() in MESI:
        fecha = f"{m.group(3)}-{MESI[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    table = soup.find("table")
    rows = []
    for tr in table.find_all("tr"):
        tds = [clean(td.get_text(" ")) for td in tr.find_all("td")]
        if len(tds) < 3 or not tds[1].isdigit():
            continue
        name = clean(re.sub(r"^\d+\.\s*", "", tds[0]))
        jugador = re.sub(r"\s+III$", "", name)
        rows.append({
            "equipo_id": "inter", "jugador": jugador, "goles": int(tds[1]),
            "alias": ALIASES.get(name, ""), "fuente": URL, "fecha_dato": fecha,
            "nota": f"web oficial del club, top 10 histórico, competiciones oficiales (excluye Trofeo Picchi y Coppa Anglo-Italiana), {tds[2]} partidos",
        })
    write_csv(SITE, rows)


if __name__ == "__main__":
    main()
