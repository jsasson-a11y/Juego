"""Liverpool FC all-time goalscorers, all competitions, from LFChistory.net.

Source: https://www.lfchistory.net/stats/player-goalscorers (paginated, 50/page)
robots.txt: allows everything except /players/random and /games/random.

Run from repo root:  python3 scripts/sources/lfchistory.py
"""
import datetime
import os
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from _common import Fetcher, clean, write_csv  # noqa: E402

SITE = "lfchistory"
BASE = "https://www.lfchistory.net/stats/player-goalscorers"


def main():
    f = Fetcher(SITE)
    today = datetime.date.today().isoformat()
    rows = []
    seen = set()
    page = 1
    while True:
        url = BASE if page == 1 else f"{BASE}?page={page}"
        soup = BeautifulSoup(f.get(url), "lxml")
        title = clean(soup.get_text(" "))
        assert "All Competitions" in title, "unexpected page (not the all-competitions list)"
        new = 0
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            a = tds[1].find("a")
            name = clean(tds[1].get_text())
            goals = clean(tds[2].get_text())
            if not goals.isdigit():
                continue
            pid = a["href"] if a and a.has_attr("href") else name
            if pid in seen:
                continue
            seen.add(pid)
            new += 1
            if int(goals) <= 0:
                continue
            rows.append({
                "equipo_id": "liverpool",
                "jugador": name,
                "goles": int(goals),
                "alias": "",
                "fuente": url,
                "fecha_dato": "",
                "nota": f"todas las competiciones (liga, FA Cup, League Cup, Europa, otras), {clean(tds[3].get_text())} partidos, consultado {today}",
            })
        if new == 0:
            break
        page += 1
        if page > 200:
            break
    rows.sort(key=lambda r: -r["goles"])
    write_csv(SITE, rows)


if __name__ == "__main__":
    main()
