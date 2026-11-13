"""FC Barcelona: official goal totals (official competitions) quoted in
articles on the club's own website (fcbarcelona.com / fcbarcelona.es).

The club's full player database (players.fcbarcelona.com) was unreachable
when this was built, and the "legendary player" cards on fcbarcelona.com mix
official and friendly matches for older players (e.g. Zaldúa 178, Tejada 137),
so they are NOT used.  Instead this script reads a curated list of club
articles that state "<player> ... N goals" in official matches and extracts N
with a regex; every pattern must match the downloaded text or the script
fails (nothing is typed in by hand).  When a player appears in several
articles, the most recent article wins.

robots.txt of www.fcbarcelona.com: "User-agent: *" with no Disallow.

Run from repo root:  python3 scripts/sources/fcbarcelona.py
"""
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from _common import Fetcher, clean, write_csv  # noqa: E402

SITE = "fcbarcelona"
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
          "oct": 10, "nov": 11, "dec": 12, "ene": 1, "abr": 4, "ago": 8, "set": 9, "dic": 12}

A_TOP50 = "https://www.fcbarcelona.com/en/football/first-team/news/4431501/raphinha-enters-top-50-fc-barcelona-goalscorers-of-all-time"
A_FERRAN = "https://www.fcbarcelona.es/es/futbol/primer-equipo/noticias/4486156/ferran-torres-entre-los-50-maximos-goleadores-de-la-historia-del-barca"
A_LEWY20 = "https://www.fcbarcelona.es/es/noticias/4371577/lewandowski-entra-en-el-top-20-de-maximos-goleadores-historicos"
A_LEWY15 = "https://www.fcbarcelona.es/es/futbol/primer-equipo/noticias/4446254/lewandowski-entra-en-el-top-15-de-maximos-goleadores-de-la-historia-del-fc-barcelona"
A_TARGETS = "https://www.fcbarcelona.com/en/news/4581966/upcoming-targets-for-raphinha"
A_NEWCASTLE = "https://www.fcbarcelona.com/en/news/4472335/robert-lewandowski-among-fc-barcelonas-all-time-greatest-goalscorers"
A_TRIPLE = "https://www.fcbarcelona.es/es/futbol/primer-equipo/noticias/4603997/triple-record-para-raphinha"
A_TOP15_2017 = "https://www.fcbarcelona.com/en/football/first-team/news/763978/luis-suarez-approaching-stoichkov-kluivert-and-reixach-goal-hauls"
A_AROCHA = "https://www.fcbarcelona.com/en/news/728494/luis-suarez-10th-on-the-all-time-scoring-list"
C_LEWY = "https://www.fcbarcelona.com/en/card/4526738/robert-lewandowski"
A_ALEXIA = "https://www.fcbarcelona.es/es/noticias/4143132/alexia-iguala-los-194-goles-de-kubala-y-tiene-a-suarez-en-el-punto-de-mira"

# (url, jugador, alias, regex with one group = goals, extra note)
FACTS = [
    (A_TOP50, "Lionel Messi", "Leo Messi", r"Leo Messi, with (\d+) goals in 778 appearances", ""),
    (A_TOP50, "Marcial Pina", "Marcial", r"Marcial’s mark of (\d+) goals", ""),
    (A_TOP50, "Lamine Yamal", "", r"Lamine Yamal \(91st, (\d+) goals", "en activo"),
    (A_TOP50, "Pedri", "", r"Pedri \(102nd, (\d+) goals", "en activo"),
    (A_TOP50, "Fermín López", "", r"Fermín López \(104th, (\d+) goals", "en activo"),
    (A_FERRAN, "Ferran Torres", "", r"Con sus (\d+) goles en 201 partidos oficiales", "en activo"),
    (A_FERRAN, "Johan Cruyff", "Cruyff", r"Johan Cruyff \((\d+) goles en 180 partidos\)", ""),
    (A_FERRAN, "José Bravo", "", r"José Bravo \((\d+) goles en 139 partidos\)", ""),
    (A_FERRAN, "Martí Vantolrà", "", r"Martí Vantolrà \((\d+) goles en 124 partidos\)", ""),
    (A_FERRAN, "Marcial Pina", "Marcial", r"Marcial Pina \((\d+) goles en 276 partidos\)", ""),
    (A_FERRAN, "Javier Saviola", "Saviola", r"Javier Saviola, con (\d+) goles", ""),
    (A_LEWY20, "Neymar", "Neymar Jr", r"un total de (\d+) goles, igualando los registros de Neymar Jr", "igualado con Lewandowski en esa fecha"),
    (A_LEWY20, "Evaristo", "Evaristo de Macedo", r"un total de (\d+) goles, igualando los registros de Neymar Jr, Evaristo", "igualado con Lewandowski en esa fecha"),
    (A_LEWY20, "José Antonio Zaldúa", "Zaldúa|Zaldua", r"un total de (\d+) goles, igualando los registros de Neymar Jr, Evaristo y Zaldúa", "igualado con Lewandowski en esa fecha"),
    (A_LEWY15, "Estanislau Basora", "Basora", r"alcanzar los (\d+) goles con el FC Barcelona.{0,400}?igualado con Estanislau Basora", "igualado con Lewandowski en esa fecha"),
    (A_TARGETS, "Bernd Schuster", "Schuster", r"Bernd Schuster, who is in 27th place with (\d+) goals", ""),
    (A_TARGETS, "Ronaldinho", "", r"Ronaldinho and Bakero with (\d+) goals", ""),
    (A_TARGETS, "José Mari Bakero", "Bakero", r"Ronaldinho and Bakero with (\d+) goals", ""),
    (A_TARGETS, "Justo Tejada", "Tejada", r"Tejada with (\d+) is in 26th place", ""),
    (A_TARGETS, "Rivaldo", "", r"and Rivaldo \((\d+)\)", ""),
    (A_TARGETS, "Neymar", "Neymar Jr", r"Neymar \((\d+)\)", ""),
    (A_TARGETS, "Evaristo", "Evaristo de Macedo", r"Evaristo \((\d+)\)", ""),
    (A_NEWCASTLE, "Hristo Stoichkov", "Stoichkov|Stoitxkov", r"He now has (\d+) goals in just three seasons, drawing level with Hristo Stoichkov", "igualado con Lewandowski en esa fecha"),
    (A_NEWCASTLE, "Patrick Kluivert", "Kluivert", r"Patrick Kluivert \((\d+)\) next in his sights", ""),
    (A_TRIPLE, "Raphinha", "Raphael Dias Belloli", r"ha escalado hasta los (\d+) goles", "en activo"),
    (C_LEWY, "Robert Lewandowski", "Lewandowski", r"Goals scored: (\d+)", "ficha oficial, etapa 2022-2026 terminada"),
    (A_ALEXIA, "Luis Suárez", "Suárez", r"son los (\d+) goles que marcó el uruguayo Luis Suárez", ""),
    (A_ALEXIA, "Ladislao Kubala", "László Kubala|Kubala", r"igualó los (\d+) goles que marcó Ladislao Kubala", ""),
    (A_ALEXIA, "César Rodríguez", "César|Cesar Rodriguez", r"César Rodríguez \((\d+)\)", ""),
    (A_AROCHA, "Àngel Arocha", "Ángel Arocha|Arocha", r"total of \((\d+)\) goals in just 165 matches, equalling the current tenth place of Àngel Arocha", "igualado con Suárez (127) en esa fecha"),
]
# 2017 official top-15 table ("Ranking Player Goals Matches ...")
TABLE_2017 = [
    ("César Rodríguez", "César|Cesar Rodriguez"), ("Ladislao Kubala", "László Kubala|Kubala"),
    ("Josep Samitier", "Samitier"), ("Josep Escolà", "Escolà|Escola"), ("Paulino Alcántara", "Alcántara"),
    ("Samuel Eto'o", "Eto'o"), ("Rivaldo", ""), ("Mariano Martín", ""), ("Ángel Arocha", "Àngel Arocha|Arocha"),
    ("Carles Rexach", "Carles Reixach|Rexach"), ("Patrick Kluivert", "Kluivert"),
    ("Hristo Stóitxkov", "Hristo Stoichkov|Stoichkov"), ("Estanislau Basora", "Basora"),
]
CANON = {"Hristo Stóitxkov": "Hristo Stoichkov", "Ángel Arocha": "Àngel Arocha"}


def article(f, url):
    soup = BeautifulSoup(f.get(url), "lxml")
    for x in soup(["script", "style", "nav", "footer", "header"]):
        x.decompose()
    text = clean(soup.get_text(" "))
    text = re.sub(r"\s+([,.;:)’])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    fecha = ""
    m = re.search(r"(?:Published date|Fecha de publicación)\s+(\d{1,2}) (\w+) (\d{2})\b", text)
    if m and m.group(2).lower()[:3] in MONTHS:
        mon = MONTHS[m.group(2).lower()[:3]]
        fecha = f"20{m.group(3)}-{mon:02d}-{int(m.group(1)):02d}"
    return text, fecha


def main():
    f = Fetcher(SITE)
    best = {}

    def add(jugador, alias, goals, url, fecha, extra):
        nota = "web oficial del club (artículo), partidos oficiales"
        if extra:
            nota += f", {extra}"
        prev = best.get(jugador)
        if prev is None or (fecha or "0") > (prev["fecha_dato"] or "0"):
            best[jugador] = {"equipo_id": "barcelona", "jugador": jugador, "goles": goals, "alias": alias,
                             "fuente": url, "fecha_dato": fecha, "nota": nota}

    for url, jugador, alias, pat, extra in FACTS:
        text, fecha = article(f, url)
        if url == C_LEWY:
            fecha = ""  # the card's "published" date is not the date of the figure
        m = re.search(pat, text)
        if not m:
            raise SystemExit(f"pattern not found for {jugador} in {url}")
        add(jugador, alias, int(m.group(1)), url, fecha, extra)

    text, fecha = article(f, A_TOP15_2017)
    seg = text[text.find("Ranking Player Goals Matches"):]
    for name, alias in TABLE_2017:
        m = re.search(r"\b\d{1,2} " + re.escape(name) + r" (\d+) (\d+)\b", seg)
        if not m:
            raise SystemExit(f"2017 table: {name} not found")
        add(CANON.get(name, name), alias, int(m.group(1)), A_TOP15_2017, fecha,
            f"tabla oficial top 15 de 2017 ({m.group(2)} partidos), cifras de jugadores antiguos revisadas después por el club en algunos casos")

    rows = sorted(best.values(), key=lambda r: -r["goles"])
    write_csv(SITE, rows)


if __name__ == "__main__":
    main()
