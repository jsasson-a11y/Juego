"""Máximos goleadores de Racing Club según Racingpedia (https://racingpedia.com.ar/maximos-goleadores/).

Tabla "Los jugadores que han convertido más goles oficiales para el primer equipo de Racing Club"
(top 40), elaborada por miembros del Departamento de Cultura e Historia de Racing Club. Goles
oficiales: liga + copas nacionales + internacionales; excluye partidos que luego la AFA anuló. La
página indica la fecha de corte ("DATOS HASTA dd-mm-aaaa"). Los jugadores marcados con * pueden tener
más goles (faltan síntesis de partidos de 1907-1910).

Uso: python3 scripts/sources/racingpedia_argentina.py
Salida: data/sources/racingpedia_argentina.csv
"""
import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, write_csv  # noqa: E402

SITE = 'racingpedia'
URL = 'https://racingpedia.com.ar/maximos-goleadores/'
# Nombres/apodos con que los hinchas conocen a algunos jugadores (se agregan como alias).
EXTRA_ALIAS = {
    'Pedro Ochoa Baigorri': 'Pedro Ochoa',
    'Rubén Capria Labiste': 'Rubén Capria',
    'Carlos Estévez': 'Maximiliano Estévez',
    'Norberto Méndez': 'Tucho Méndez',
    'Adrián Martínez': 'Maravilla Martínez',
    'Delfín Benítez Cáceres': 'Delfín Benítez',
    'Juan Pizzuti': 'Juan José Pizzuti',
}
PARTICLES = {'de', 'del', 'la', 'las', 'los', 'di', 'da', 'do', 'dos', 'van', 'von', 'y'}


def nice_surname(s):
    out = []
    for i, w in enumerate(s.lower().split()):
        if i > 0 and w in PARTICLES:
            out.append(w)
        else:
            # "d’alessandro" -> "D’Alessandro"
            out.append(re.sub(r"(^|[-'’])(\w)", lambda m: m.group(1) + m.group(2).upper(), w))
    return ' '.join(out)


def names(raw):
    """'OHACO, Alberto Bernardino *' -> ('Alberto Ohaco', 'Alberto Bernardino Ohaco')."""
    raw = raw.replace('*', '').strip()
    last, first = [x.strip() for x in raw.split(',', 1)]
    last = nice_surname(last)
    full = f'{first} {last}'
    short = f'{first.split()[0]} {last}'
    return short, (full if full != short else '')


def main():
    html = fetch(URL, SITE)
    soup = BeautifulSoup(html, 'lxml')
    text = soup.get_text('\n', strip=True)
    m = re.search(r'DATOS HASTA\s+(\d{1,2})-(\d{1,2})-(\d{4})', text)
    fecha = f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}' if m else ''
    table = soup.find('table')
    rows = []
    for tr in table.find_all('tr'):
        tds = [td.get_text(' ', strip=True) for td in tr.find_all(['td', 'th'])]
        if len(tds) < 6 or not tds[0].isdigit():
            continue
        _, jugador_raw, goles, pj, _, anos = tds[:6]
        jugador, alias = names(jugador_raw.replace('’', "'"))
        alias = '|'.join(dict.fromkeys(a for a in (alias, EXTRA_ALIAS.get(jugador, '')) if a and a != jugador))
        nota = ('goles oficiales con el primer equipo (liga + copas nacionales + internacionales; excluye '
                f'partidos anulados por la AFA); top 40 de Racingpedia; {pj} PJ, {anos}')
        if '*' in jugador_raw:
            nota += '; la fuente aclara que puede tener más goles (faltan síntesis de 1907-1910)'
        rows.append({'equipo_id': 'racing-club', 'jugador': jugador, 'goles': int(goles), 'alias': alias,
                     'fuente': URL, 'fecha_dato': fecha, 'nota': nota})
    out = write_csv(ROOT / 'data' / 'sources' / 'racingpedia_argentina.csv', rows)
    print(Counter(r['equipo_id'] for r in rows), file=sys.stderr)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
