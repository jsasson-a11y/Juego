"""Máximos goleadores de Estudiantes de La Plata según el diario 0221 (La Plata).

Nota "Los goles de Guido Carrillo en la historia viviente de Estudiantes" (publicada 2026-01-21):
https://www.0221.com.ar/estudiantes/los-goles-guido-carrillo-la-historia-viviente-estudiantes-n122435
Incluye la lista "Los máximos goleadores de la historia de Estudiantes" (19 jugadores). Es el ranking
histórico del club (las cifras de la parte alta coinciden con la lista "TOP 15 TOTALES" del sitio
oficial, que suma era amateur, profesionalismo, copas nacionales, internacionales y ascenso),
actualizado a la fecha de la nota.

Uso: python3 scripts/sources/0221_argentina.py
Salida: data/sources/0221_argentina.csv
"""
import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, write_csv  # noqa: E402

SITE = '0221'
URL = 'https://www.0221.com.ar/estudiantes/los-goles-guido-carrillo-la-historia-viviente-estudiantes-n122435'
FIX = {'Alejando Scopelli': 'Alejandro Scopelli', 'Rubén Galleti': 'Rubén Galletti'}
ALIAS = {'Alejandro Scopelli': 'Alejando Scopelli', 'Rubén Galletti': 'Rubén Galleti',
         'Exequiel Julio Galliardo': 'Exequiel Galliardo'}


def main():
    html = fetch(URL, SITE)
    m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', html) or \
        re.search(r'published_time"\s+content="(\d{4}-\d{2}-\d{2})', html)
    fecha = m.group(1) if m else ''
    lines = BeautifulSoup(html, 'lxml').get_text('\n', strip=True).splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith('Los máximos goleadores de la historia de Estudiantes'))
    rows = []
    for ln in lines[start + 1:]:
        mm = re.match(r'^([A-ZÁÉÍÓÚÑ][^\d()]+?)\s*\(?(\d+)\)?$', ln.strip())
        if not mm:
            break
        name = FIX.get(mm.group(1).strip(), mm.group(1).strip())
        rows.append({'equipo_id': 'estudiantes', 'jugador': name, 'goles': int(mm.group(2)),
                     'alias': ALIAS.get(name, ''), 'fuente': URL, 'fecha_dato': fecha,
                     'nota': ('ranking histórico de goleadores del club publicado por 0221 (top 19 al '
                              f'{fecha}); total con el club según el ranking oficial (amateur + profesional + '
                              'copas nacionales + internacionales)')})
    out = write_csv(ROOT / 'data' / 'sources' / '0221_argentina.csv', rows)
    print(Counter(r['equipo_id'] for r in rows), file=sys.stderr)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
