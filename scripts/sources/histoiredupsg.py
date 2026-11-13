"""Paris Saint-Germain: all-time ranking of ALL goalscorers in official
matches since 1970, from the fan archive Histoire du PSG (histoiredupsg.fr),
"mis à jour après chaque rencontre" (page cites RTL as source).

Source: https://histoiredupsg.fr/classement-historique-buteurs-psg/
Format: "12e – Carlos BIANCHI 71 buts", several names per rank when tied.
robots.txt: only WordPress admin/system paths are disallowed.

Run from repo root:  python3 scripts/sources/histoiredupsg.py
"""
import datetime
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from _common import Fetcher, clean, write_csv  # noqa: E402

SITE = "histoiredupsg"
URL = "https://histoiredupsg.fr/classement-historique-buteurs-psg/"
BLOCKS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "div", "br", "tr"]


def nice(name):
    """'Kylian MBAPPE' -> 'Kylian Mbappe'; 'François M’PELE' -> 'François M’Pele'.
    Only ALL-CAPS words are re-cased; accents are kept as written by the source."""
    def fix(word):
        if not any(c.isalpha() for c in word) or word != word.upper():
            return word
        return re.sub(r"(^|[-’'])(\w)(\w*)", lambda m: m.group(1) + m.group(2).upper() + m.group(3).lower(), word)
    return " ".join(fix(w) for w in name.split())


def main():
    f = Fetcher(SITE)
    today = datetime.date.today().isoformat()
    soup = BeautifulSoup(f.get(URL), "lxml")
    body = soup.find(class_=re.compile(r"entry-content|post-content")) or soup.body
    for tag in body.find_all(BLOCKS):
        tag.append("\n")
    text = body.get_text("").replace("\xa0", " ")
    assert "matchs officiels depuis la création du PSG" in clean(soup.get_text(" ")), "unexpected page"
    rows = []
    for m in re.finditer(r"(\d+)(?:er|e)\s*–\s*(.*?)\s*(\d+)\s*buts?\b", text, re.S):
        rank, names, goals = m.group(1), m.group(2), int(m.group(3))
        for raw in re.split(r",|\n", names):
            raw = clean(raw).strip(",").strip()
            if not raw or not re.search(r"[A-Za-z]", raw):
                continue
            jugador = nice(raw)
            rows.append({
                "equipo_id": "psg", "jugador": jugador, "goles": goals,
                "alias": raw if raw != jugador else "", "fuente": URL, "fecha_dato": "",
                "nota": f"partidos oficiales desde 1970 (todas las competiciones), puesto {rank}, la página se actualiza tras cada partido, consultado {today}",
            })
    assert len(rows) > 200, "page layout changed"
    write_csv(SITE, rows)


if __name__ == "__main__":
    main()
