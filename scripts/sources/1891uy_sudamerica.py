"""Goleadores de Peñarol según 1891.uy (base de datos oficial de la Comisión de Historia y
Patrimonio Histórico del C.A. Peñarol).

Lee el ranking completo "Goleadores - Jugadores (solo partidos oficiales)", paginado.

Uso: python3 scripts/sources/1891uy_sudamerica.py
Salida: data/sources/1891uy_sudamerica.csv
"""
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, short_alias, write_csv  # noqa: E402

SITE = '1891uy'
URL = 'https://1891.uy/estadisticas/jugadores/goleadores'
NOTA = ('solo partidos oficiales (todas las competiciones oficiales); base oficial de la Comisión de Historia '
        'de Peñarol, que advierte que algunos registros aún presentan faltantes')


def parse(html):
    s = BeautifulSoup(html, 'lxml')
    out, last_rank = [], 0
    for ul in s.select('section.tops ul.data-list'):
        for li in ul.find_all('li', recursive=False):
            a = li.select_one('.left a[href^="/jugadores/"]')
            p = li.select_one('.right p')
            if not a or not p:
                continue
            txt = p.get_text(strip=True)
            if not txt.isdigit():
                continue
            out.append((a.get_text(' ', strip=True), int(txt), 'https://1891.uy' + a['href']))
            rk = li.select_one('.rank')
            if rk and rk.get_text(strip=True).isdigit():
                last_rank = max(last_rank, int(rk.get_text(strip=True)))
    return out, last_rank


def main():
    # Nota: el ranking pagina con LIMIT/OFFSET sobre goles empatados y algunos jugadores aparecen en dos
    # páginas mientras otros no aparecen en ninguna (determinista: repetir la descarga no ayuda). Se avisa
    # cuántos faltan comparando con el último puesto del ranking.
    found = {}
    max_rank = 0
    dups = []
    page = 1
    while page <= 200:
        url = URL if page == 1 else f'{URL}?page={page}'
        items, last_rank = parse(fetch(url, SITE, delay=2.0))
        if not items:
            break
        max_rank = max(max_rank, last_rank)
        for name, goals, purl in items:
            if purl in found:
                dups.append((name, goals))
            found.setdefault(purl, (name, goals, url))
        page += 1
    print(f'{len(found)} jugadores distintos de {max_rank} puestos; repetidos: {dups}', file=sys.stderr)
    rows = [{'equipo_id': 'penarol', 'jugador': name, 'goles': goals, 'alias': short_alias(name),
             'fuente': url, 'fecha_dato': '', 'nota': NOTA}
            for name, goals, url in found.values() if goals > 0]
    rows.sort(key=lambda r: (-r['goles'], r['jugador']))
    out = write_csv(ROOT / 'data' / 'sources' / '1891uy_sudamerica.csv', rows)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
