"""Goleadores del São Paulo FC según el "Fichário" de la SPFCpédia (sitio oficial del club,
https://www.saopaulofc.net/o-clube/fichario/): perfil de todos los jugadores del plantel principal
masculino con "Histórico: J, V, E, D, GM" (GM = goles marcados).

Ojo: la base del club cuenta todos los partidos del primer equipo, amistosos incluidos (la SPFCpédia
lista, por ejemplo, goles en "Amistoso" entre sus récords). Se indica en `nota`.

Uso: python3 scripts/sources/saopaulofc_sudamerica.py
Salida: data/sources/saopaulofc_sudamerica.csv
"""
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, write_csv  # noqa: E402

SITE = 'saopaulofc'
URL = 'https://www.saopaulofc.net/o-clube/fichario/'
PARTICLES = {'de', 'da', 'do', 'das', 'dos', 'e', 'del', 'la', 'di', 'van', 'von'}
HEAD = re.compile(r'^([A-ZÀ-ÖØ-Þ0-9][A-ZÀ-ÖØ-Þ0-9 .\'´`\-]*?)(?:\s*\(([A-Z]{2})-(\d{4})\))?$')


def nice(nick):
    words = nick.lower().split()
    return ' '.join(w if (i > 0 and w in PARTICLES) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def main():
    html = fetch(URL, SITE, delay=2.0)
    s = BeautifulSoup(html, 'lxml')
    tab = s.find(id='tabs-page-1')
    h2 = tab.find('h2') if tab else None
    if not tab or not h2 or 'Masculino' not in h2.get_text():
        sys.exit('No se encontró la pestaña "Masculino" (tabs-page-1); revisar el script.')
    for t in tab(['script', 'style']):
        t.decompose()
    fecha = ''
    m = re.search(r'atualizado até (\d{1,2}) de (\w+) de (\d{4})', tab.get_text(' ', strip=True))
    meses = {'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7,
             'agosto': 8, 'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12}
    if m and m.group(2).lower() in meses:
        fecha = f'{int(m.group(3)):04d}-{meses[m.group(2).lower()]:02d}-{int(m.group(1)):02d}'
    lines = tab.get_text('\n', strip=True).split('\n')
    rows = []
    unknown = 0
    for i, line in enumerate(lines):
        if not line.startswith('Histórico:'):
            continue
        # Retroceder hasta la cabecera "APODO (POS-AÑO)"; la línea siguiente es el nombre completo.
        j = i - 1
        while j > 0 and not HEAD.match(lines[j]):
            j -= 1
        hm = HEAD.match(lines[j])
        if not hm or i - j > 9:
            print('cabecera no encontrada para', line, file=sys.stderr)
            continue
        nick, pos, year = hm.group(1).strip(), hm.group(2), hm.group(3)
        full = lines[j + 1] if j + 1 < i else ''
        gm = re.search(r'(\d+) GM', line)
        if not gm:
            unknown += 1
            continue
        goals = int(gm.group(1))
        if goals <= 0:
            continue
        alias = [full] if full and not full.startswith(('Nasc.', 'Base:', 'Contratado')) else []
        if pos:
            alias.append(f'{nice(nick)} ({pos}-{year})')
        rows.append({'equipo_id': 'sao-paulo', 'jugador': nice(nick), 'goles': goals, 'alias': '|'.join(alias),
                     'fuente': URL, 'fecha_dato': fecha,
                     'nota': 'todos los partidos del primer equipo según la base oficial del club (incluye amistosos)'})
    rows.sort(key=lambda r: (-r['goles'], r['jugador']))
    out = write_csv(ROOT / 'data' / 'sources' / 'saopaulofc_sudamerica.csv', rows)
    print(f'{len(rows)} filas -> {out} (sin datos de partidos: {unknown})', file=sys.stderr)


if __name__ == '__main__':
    main()
