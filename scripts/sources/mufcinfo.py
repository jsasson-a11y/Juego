"""Manchester United (incl. Newton Heath) all-time goalscorers, all competitive
matches, from MUFCInfo.com.

Source: https://www.mufcinfo.com/manupag/all_players_all_goals/all_players_all_goals.html
robots.txt: allows this page (only some per-player sub-pages are disallowed).

Run from repo root:  python3 scripts/sources/mufcinfo.py
"""
import datetime
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from _common import Fetcher, clean, write_csv  # noqa: E402

SITE = "mufcinfo"
URL = "https://www.mufcinfo.com/manupag/all_players_all_goals/all_players_all_goals.html"


def flip(name):
    """'Rooney, Wayne' -> 'Wayne Rooney'."""
    if "," in name:
        last, first = [p.strip() for p in name.split(",", 1)]
        return clean(f"{first} {last}") if first else last
    return name


def main():
    f = Fetcher(SITE)
    today = datetime.date.today().isoformat()
    soup = BeautifulSoup(f.get(URL), "lxml")
    rows = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 8 or not re.fullmatch(r"\d+\.", clean(tds[0].get_text())):
            continue
        raw = clean(tds[1].get_text())
        apps, goals = clean(tds[5].get_text()), clean(tds[6].get_text())
        if not goals.isdigit() or int(goals) <= 0:
            continue
        name = flip(raw)
        rows.append({
            "equipo_id": "manchester-united",
            "jugador": name,
            "goles": int(goals),
            "alias": raw if raw != name else "",
            "fuente": URL,
            "fecha_dato": "",
            "nota": f"todos los partidos oficiales (incl. Newton Heath), {apps} partidos, años {clean(tds[3].get_text())}, consultado {today}",
        })
    write_csv(SITE, rows)


if __name__ == "__main__":
    main()
