"""All-time top ~10 goalscorers per club (competitive fixtures only, i.e. all
official competitions) from footballfacts.co.uk club pages.  The site covers
English, Italian and (some) Spanish clubs only, and states it compiles data
from Transfermarkt, ENFA, Premier League, calcio-seriea.net and club fan
archives (e.g. Magliarossonera, AS Roma Ultras), so it is NOT independent of
those sources; it is used only as an extra cross-check for clubs whose other
second sources are partial.

robots.txt: "User-agent: *" with no Disallow.

Run from repo root:  python3 scripts/sources/footballfacts.py
"""
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from _common import Fetcher, clean, write_csv  # noqa: E402

SITE = "footballfacts"
BASE = "https://footballfacts.co.uk/clubs/{}.php"
CLUBS = {
    "barcelona": "spain/barcelona/barcelona",
    "real-madrid": "spain/real-madrid/real-madrid",
    "atletico-madrid": "spain/atletico-madrid/atletico-madrid",
    "manchester-city": "england/manchester-city/manchester-city",
    "arsenal": "england/arsenal/arsenal",
    "chelsea": "england/chelsea/chelsea",
    "juventus": "italy/juventus/juventus",
    "inter": "italy/internazionale/internazionale",
}
ABOUT = "https://footballfacts.co.uk/about.php"


def main():
    f = Fetcher(SITE)
    about = clean(BeautifulSoup(f.get(ABOUT), "lxml").get_text(" "))
    assert "Club statistics are for competitive fixtures only" in about, "about page changed"
    m = re.search(r"Last updated:\s*(\d{1,2}) (\w+) (\d{4})", about)
    months = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
              "october", "november", "december"]
    fecha = f"{m.group(3)}-{months.index(m.group(2).lower()) + 1:02d}-{int(m.group(1)):02d}" if m else ""
    rows = []
    for equipo, path in CLUBS.items():
        url = BASE.format(path)
        soup = BeautifulSoup(f.get(url), "lxml")
        table = next((t for t in soup.find_all("table")
                      if clean(t.find("tr").get_text(" ")).startswith("All-time Goalscorers")), None)
        if table is None:
            raise SystemExit(f"no goalscorers table in {url}")
        for tr in table.find_all("tr"):
            tds = [clean(td.get_text(" ")) for td in tr.find_all("td")]
            # rank | (flag) | player | years | apps | goals | gpg
            if len(tds) < 6 or not tds[5].isdigit() or not tds[4].isdigit():
                continue
            rows.append({
                "equipo_id": equipo, "jugador": tds[2], "goles": int(tds[5]), "alias": "",
                "fuente": url, "fecha_dato": fecha,
                "nota": f"top ~10 histórico, partidos oficiales (competitive fixtures), {tds[4]} partidos, {tds[3]}; fecha = 'Last updated' del sitio; recopila de Transfermarkt y otros",
            })
    write_csv(SITE, rows)


if __name__ == "__main__":
    main()
