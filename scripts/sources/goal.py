"""Press tables "all-time top scorers" (top 20, all competitions) published by
Goal.com for several clubs.  Used only as a cross-check for clubs without a
better second source; Goal tables are dated and contain occasional typos, so
rows that break the ranking order (goals higher than the row above, or a
"=" tie whose goals differ from the row above) are dropped and reported.

robots.txt of www.goal.com: "User-agent: * / Allow: /".

Run from repo root:  python3 scripts/sources/goal.py
"""
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from _common import Fetcher, clean, write_csv  # noqa: E402

SITE = "goal"
PAGES = [
    ("barcelona", "https://www.goal.com/en/news/barcelona-all-time-top-goal-scorers-lionel-messi/bltcff247c71b131113"),
    ("bayern-munich", "https://www.goal.com/en/news/bayern-munich-all-time-top-goal-scorers-gerd-muller/blt768730fa575d9d51"),
    ("real-madrid", "https://www.goal.com/en/news/real-madrid-all-time-top-scorers-cristiano-ronaldo-karim-benzema/blt433e4e61a1fc85ee"),
    ("manchester-city", "https://www.goal.com/en-us/news/manchester-city-all-time-top-goal-scorers-sergio-aguero/blt240b09520a843803"),
    ("borussia-dortmund", "https://www.goal.com/de/meldungen/bvb-meiste-tore-rekord-torj%C3%A4ger-borussia-dortmund/blt1749f64a3e7dad82"),
    ("arsenal", "https://www.goal.com/en/news/arsenal-all-time-top-scorers/blt2ae8970d08716275"),
    ("juventus", "https://www.goal.com/en/news/juventus-all-time-top-scorers-del-piero-dybala/blt36f785a86f706f6c"),
    ("psg", "https://www.goal.com/en/news/paris-saint-germain-all-time-top-scorers-cavani-mbappe/bltd18ad96d63de1edf"),
]
# Tables whose "Years" column is visibly misaligned in the source.
BAD_YEARS = {"arsenal"}
# Spelling fixes for obvious typos in Goal's tables: jugador gets the usual
# spelling, the source spelling is kept in alias.
FIX = {
    "Laszlo Kubasla": "László Kubala", "Cesar Rodriguez": "César Rodríguez", "Luis Suarez": "Luis Suárez",
    "Josep Escola": "Josep Escolà", "Paulino Alcantara": "Paulino Alcántara", "Mariano Martin": "Mariano Martín",
    "Estanisloa Basora Brunet": "Estanislau Basora", "Jose Zaldu": "José Antonio Zaldúa",
    "Eulogio Martinez": "Eulogio Martínez", "Juan Manuel Asensi": "Juan Manuel Asensi",
    "Gerd Muller": "Gerd Müller", "Thomas Muller": "Thomas Müller", "Karl-Heinz Rummenggie": "Karl-Heinz Rummenigge",
    "Raul Gonzalez": "Raúl", "Alfredo Di Stefano": "Alfredo Di Stéfano", "Ferenc Puskas": "Ferenc Puskás",
    "Hugo Sanchez": "Hugo Sánchez", "Francisco 'Paco' Gento": "Paco Gento", "Emilio Butragueno": "Emilio Butragueño",
    "Pahino": "Pahiño", "Sergio Aguero": "Sergio Agüero", "Billie Gillespie": "Billy Gillespie",
    "Kylian Mbappe": "Kylian Mbappé", "Zlatan Ibrahimovic": "Zlatan Ibrahimović", "Angel Di Maria": "Ángel Di María",
    "Safet Susic": "Safet Sušić", "David Heard": "David Herd", "Gonzalo Higuain": "Gonzalo Higuaín",
    "Ronaldo Nazario": "Ronaldo", "Ivan Zamorano": "Iván Zamorano", "Rai": "Raí", "Nene": "Nenê", "Omar Sivori": "Omar Sívori",
}


def main():
    f = Fetcher(SITE)
    rows, dropped = [], []
    for equipo, url in PAGES:
        raw = f.get(url)
        m = re.search(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})', raw) or \
            re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', raw)
        fecha = m.group(1) if m else ""
        soup = BeautifulSoup(raw, "lxml")
        table = soup.find("table")
        if table is None:
            raise SystemExit(f"no table in {url}")
        prev_goals, prev_pos = None, None
        for tr in table.find_all("tr"):
            tds = [clean(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
            if len(tds) < 4 or not tds[2].isdigit():
                continue
            pos, name, goals, apps = tds[0], tds[1], int(tds[2]), tds[3]
            years = tds[4] if len(tds) > 4 else ""
            posn = pos.lstrip("=")
            bad = prev_goals is not None and (goals > prev_goals or (pos.startswith("=") and posn == prev_pos and goals != prev_goals))
            if bad:
                dropped.append(f"{equipo}: {pos} {name} {goals} (row above: {prev_goals})")
                continue
            prev_goals, prev_pos = goals, posn
            if equipo in BAD_YEARS:
                years = "(columna de años de la fuente desalineada, omitida)"
            jugador = FIX.get(name, name)
            rows.append({
                "equipo_id": equipo, "jugador": jugador, "goles": goals,
                "alias": name if jugador != name else "", "fuente": url, "fecha_dato": fecha,
                "nota": f"tabla de prensa (Goal.com), top 20 histórico, todas las competiciones, {apps} partidos, {years}; puede contener erratas",
            })
    write_csv(SITE, rows)
    for d in dropped:
        print("dropped (inconsistent ranking):", d, file=sys.stderr)


if __name__ == "__main__":
    main()
