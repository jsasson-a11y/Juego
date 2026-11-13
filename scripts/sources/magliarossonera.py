"""AC Milan: every player of official first-team matches with official
appearances and goals (all official competitions), from Magliarossonera.it.

Pages: https://www.magliarossonera.it/protagonisti/Gioc_<L>.html
Column "Presenze ufficiali e reti" = "apps (goals)" in official competitions
(see https://www.magliarossonera.it/Prot-Gioc-precisazioni.html).
Goalkeepers are often listed with appearances only (no goal figure): skipped.
robots.txt: "User-agent: *" with no Disallow.

Run from repo root:  python3 scripts/sources/magliarossonera.py
"""
import datetime
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from _common import Fetcher, clean, write_csv  # noqa: E402

SITE = "magliarossonera"
BASE = "https://www.magliarossonera.it/protagonisti/Gioc_{}.html"
LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "IJK", "L", "M", "N", "O",
           "P", "Q", "R", "S", "T", "U", "V", "WXY", "Z"]


def main():
    f = Fetcher(SITE)
    today = datetime.date.today().isoformat()
    rows = []
    for letter in LETTERS:
        url = BASE.format(letter)
        soup = BeautifulSoup(f.get(url), "lxml")
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) != 8:
                continue
            cognome = clean(tds[0].get_text(" ")).replace("- ", "-")
            nome = clean(tds[1].get_text(" "))
            stats = clean(tds[7].get_text(" "))
            if cognome == "Cognome":
                continue
            m = re.fullmatch(r"(\d+)\s*\(\s*(\d+)\s*\)", stats)
            if not m:
                continue  # GK without goal figure, "solo amichevoli", etc.
            apps, goals = int(m.group(1)), int(m.group(2))
            if goals <= 0:
                continue
            raw = clean(f"{cognome} {nome}")
            # "(I)", "(II)"... distinguish namesakes/brothers; "(detto Gianni)" = nickname
            sur = clean(re.sub(r"\((?:I|II|III|IV|V)\)", "", cognome))
            detto = re.search(r"\(detto ([^)]+)\)", nome)
            first = clean(detto.group(1)) if detto else clean(re.sub(r"\([^)]*\)", "", nome))
            jugador = clean(f"{first} {sur}")
            alias = "|".join(dict.fromkeys(a for a in [sur, raw] if a and a != jugador))
            rows.append({
                "equipo_id": "milan", "jugador": jugador, "goles": goals, "alias": alias,
                "fuente": url, "fecha_dato": "",
                "nota": f"partidos oficiales (todas las competiciones), {apps} partidos, temporadas {clean(tds[6].get_text(' '))}, nombre = Nome + Cognome del sitio (alias = forma original), consultado {today}",
            })
    rows.sort(key=lambda r: -r["goles"])
    write_csv(SITE, rows)


if __name__ == "__main__":
    main()
