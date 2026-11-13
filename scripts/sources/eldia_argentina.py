"""Dato puntual de El Día (La Plata): goles de Guido Carrillo en Estudiantes.

Nota "Sosa y Carrillo, entre los más grandes" (publicada 2026-11-13):
https://www.eldia.com/deportes/sosa-y-carrillo-entre-los-mas-grandes-deportes_1794550739
"Guido Carrillo alcanzó los 283 partidos con la camiseta de Estudiantes [...] Desde su debut acumuló
80 goles". Sirve para actualizar a Carrillo respecto del ranking de enero de 2026 (0221: 71 goles).
robots.txt de eldia.com pide Crawl-delay: 5 (se respeta).

Uso: python3 scripts/sources/eldia_argentina.py
Salida: data/sources/eldia_argentina.csv
"""
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, write_csv  # noqa: E402

SITE = 'eldia'
URL = 'https://www.eldia.com/deportes/sosa-y-carrillo-entre-los-mas-grandes-deportes_1794550739'


def main():
    html = fetch(URL, SITE, delay=5)
    m = re.search(r'datePublished"?\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
    fecha = m.group(1) if m else ''
    text = BeautifulSoup(html, 'lxml').get_text(' ', strip=True)
    pj = re.search(r'Carrillo alcanzó los (\d+) partidos con la camiseta de Estudiantes', text)
    g = re.search(r'Desde su debut acumuló (\d+) goles', text)
    rows = []
    if pj and g:
        rows.append({'equipo_id': 'estudiantes', 'jugador': 'Guido Carrillo', 'goles': int(g.group(1)),
                     'alias': '', 'fuente': URL, 'fecha_dato': fecha,
                     'nota': (f'goles con Estudiantes desde su debut en sus dos ciclos ({pj.group(1)} PJ), según '
                              f'El Día al {fecha}; dato puntual de un solo jugador')})
    else:
        print('no se encontró el dato de Carrillo en la nota', file=sys.stderr)
    out = write_csv(ROOT / 'data' / 'sources' / 'eldia_argentina.csv', rows)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
