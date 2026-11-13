"""Chelsea: official top-20 all-time goalscorers (all competitive matches)
from the club site chelseafc.com.

Source: https://www.chelseafc.com/en/news/article/chelsea-fcs-all-time-record-goalscorers
Headings "Player – N goals"; fecha_dato = article's content_publish_date.
robots.txt: "User-agent: * / Allow: /".

Run from repo root:  python3 scripts/sources/chelseafc.py
"""
import html as htmllib
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from _common import Fetcher, write_csv  # noqa: E402

SITE = "chelseafc"
URL = "https://www.chelseafc.com/en/news/article/chelsea-fcs-all-time-record-goalscorers"
ALIASES = {"Eidur Gudjohnsen": "Eiður Guðjohnsen"}


def main():
    f = Fetcher(SITE)
    raw = f.get(URL)
    m = re.search(r'"content_publish_date"\s*:\s*"(\d{4}-\d{2}-\d{2})', htmllib.unescape(raw))
    fecha = m.group(1) if m else ""
    soup = BeautifulSoup(raw, "lxml")
    for x in soup(["script", "style"]):
        x.decompose()
    text = soup.get_text("\n", strip=True)
    rows = []
    for name, goals in re.findall(r"^(.{3,40}?)\s+[–-]\s+(\d+) goals$", text, re.M):
        rows.append({
            "equipo_id": "chelsea", "jugador": name, "goles": int(goals), "alias": ALIASES.get(name, ""),
            "fuente": URL, "fecha_dato": fecha,
            "nota": "web oficial del club, top 20 histórico, todas las competiciones oficiales",
        })
    assert len(rows) >= 10, "page layout changed"
    write_csv(SITE, rows)


if __name__ == "__main__":
    main()
