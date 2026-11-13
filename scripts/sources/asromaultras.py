"""AS Roma: appearances and goals of every first-team player, all official
competitions, from the fan archive asromaultras.org ("Uomini" A-Z pages).

Pages: https://www.asromaultras.org/<L>_Uomini.html  (L = A..Z)
Cell "PRESENZE E RETI" holds one "apps (goals)" pair per spell at the club;
spells are summed. Rows where a spell has no goal figure are skipped (the
total would be incomplete). '*' = "Dati aggiornati all'ultima stagione conclusa".
robots.txt: none (404) -> no restrictions.

Run from repo root:  python3 scripts/sources/asromaultras.py
"""
import datetime
import os
import re
import string
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from _common import Fetcher, clean, write_csv  # noqa: E402

SITE = "asromaultras"
BASE = "https://www.asromaultras.org/{}_Uomini.html"
PAIR = re.compile(r"(\d+)\s*\(\s*(\d+)\s*\)")


def split_name(cell):
    """The site writes 'Surname Firstname'; a line break, when present,
    separates surname from first name(s)."""
    for br in cell.find_all("br"):
        br.replace_with("\n")
    parts = [clean(p) for p in cell.get_text("").split("\n") if clean(p)]
    raw = clean(" ".join(parts))
    if len(parts) >= 2:
        surname, first = parts[0], " ".join(parts[1:])
    else:
        toks = raw.split(" ")
        if len(toks) < 2:
            return raw, raw
        surname, first = " ".join(toks[:-1]), toks[-1]
    return clean(f"{first} {surname}"), raw


def main():
    f = Fetcher(SITE)
    today = datetime.date.today().isoformat()
    rows, skipped = [], []
    for letter in string.ascii_uppercase:
        url = BASE.format(letter)
        html = f.get(url, encoding="cp1252")
        soup = BeautifulSoup(html, "lxml")
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 7:
                continue
            if not tds[0].find("a") and clean(tds[0].get_text()).upper() == "NOME":
                continue
            for br in tds[-1].find_all("br"):
                br.replace_with(" ")
            # get_text("") so that digits split across inline tags stay together
            stats = clean(tds[-1].get_text(""))
            role = clean(tds[-4].get_text(" ")) if len(tds) >= 7 else ""
            if not re.search(r"\d", stats):
                continue  # staff / no appearances
            name, raw = split_name(tds[0])
            coach_note = ""
            if "allenatore" in role.lower():
                # player-coaches: a trailing bare number is matches as coach
                m = re.match(r"^(.*\))\s*(\d+)\*?$", stats)
                if m:
                    stats, coach_note = m.group(1), f", se ignoran {m.group(2)} partidos como entrenador"
            pairs = PAIR.findall(stats)
            bare = re.findall(r"\d+", PAIR.sub(" ", stats))
            if not pairs or bare:
                skipped.append(f"{raw}: '{stats}'")
                continue
            goals = sum(int(g) for _, g in pairs)
            apps = sum(int(a) for a, _ in pairs)
            if goals <= 0:
                continue
            nota = f"todas las competiciones oficiales, {apps} partidos"
            if len(pairs) > 1:
                nota += f", suma de {len(pairs)} etapas ({' + '.join(f'{a} ({g})' for a, g in pairs)})"
            if "*" in stats:
                nota += ", '*' = datos actualizados a la última temporada concluida"
            nota += coach_note + f", consultado {today}"
            rows.append({
                "equipo_id": "roma", "jugador": name, "goles": goals,
                "alias": raw, "fuente": url, "fecha_dato": "", "nota": nota,
            })
    rows.sort(key=lambda r: -r["goles"])
    write_csv(SITE, rows)
    print(f"skipped {len(skipped)} rows with incomplete figures", file=sys.stderr)
    for s in skipped:
        print("  skip:", s, file=sys.stderr)


if __name__ == "__main__":
    main()
