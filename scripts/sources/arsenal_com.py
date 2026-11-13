"""Arsenal: official list of players with 100+ goals for the club (all
competitive matches), from the club site arsenal.com.

Source: https://www.arsenal.com/feature/goalscorers-a9glp8a4jbYr
(table "Name | Total Goals | Total Games | 100th Goal Game", published 2020-11-01)
robots.txt: allows everything except user-profile/auth/search URLs.
Note: arsenal.com answered HTTP 503 (Akamai) to some requests; just re-run later.

Run from repo root:  python3 scripts/sources/arsenal_com.py
"""
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from _common import Fetcher, clean, write_csv  # noqa: E402

SITE = "arsenal_com"
URL = "https://www.arsenal.com/feature/goalscorers-a9glp8a4jbYr"


def main():
    f = Fetcher(SITE)
    raw = f.get(URL)
    m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', raw)
    fecha = m.group(1) if m else ""
    soup = BeautifulSoup(raw, "lxml")
    table = next(t for t in soup.find_all("table") if "Total Goals" in t.get_text())
    rows = []
    for tr in table.find_all("tr"):
        tds = [clean(td.get_text(" ")).replace("​", "").strip() for td in tr.find_all("td")]
        nums = [x for x in tds[1:] if x.isdigit()]
        if not tds or not nums or len(nums) < 2:
            continue
        rows.append({
            "equipo_id": "arsenal", "jugador": tds[0], "goles": int(nums[0]), "alias": "",
            "fuente": URL, "fecha_dato": fecha,
            "nota": f"web oficial del club, solo jugadores con 100+ goles, todas las competiciones oficiales, {nums[1]} partidos",
        })
    assert len(rows) >= 15, "page layout changed"
    write_csv(SITE, rows)


if __name__ == "__main__":
    main()
