"""Goleadores de Estudiantes de La Plata según notas del sitio oficial del club.

1) Nota "Boselli, top 12" (https://estudiantesdelaplata.com/boselli-top-12/, publicada el 17/06/2022).
Se toma la lista "TOP 15 TOTALES", que suma era amateur, era profesional, copas nacionales,
internacionales y ascenso (el desglose aparece junto a algunos nombres). No se usa la lista "TOP 12"
de la misma nota, que cuenta sólo el profesionalismo. Dato al 2022-06-17: jugadores en actividad
desde entonces (p. ej. Boselli) pueden tener más goles.

2) Nota "Desábato, histórico y goleador" (https://estudiantesdelaplata.com/desabato-historico-y-goleador/,
20/03/2017): lista "LOS 8 DEFENSORES GOLEADORES" (goles con la camiseta del club; la nota no detalla las
competiciones, pero separa expresamente un gol en un amistoso, que no cuenta). Dato al 2017-03-20
(Desábato siguió jugando después).

Uso: python3 scripts/sources/estudiantesdelaplata_argentina.py
Salida: data/sources/estudiantesdelaplata_argentina.csv
"""
import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, write_csv  # noqa: E402

SITE = 'estudiantesdelaplata'
URL = 'https://estudiantesdelaplata.com/boselli-top-12/'
URL_DEF = 'https://estudiantesdelaplata.com/desabato-historico-y-goleador/'
# Grafías de la fuente -> nombre habitual (sin cambiar cifras).
FIX = {'Alejando Scopelli': 'Alejandro Scopelli', 'Rubén Galleti': 'Rubén Galletti'}
ALIAS = {'Alejandro Scopelli': 'Alejando Scopelli', 'Rubén Galletti': 'Rubén Galleti',
         'Juan Ramón Verón': 'La Bruja Verón', 'Exequiel Julio Galliardo': 'Exequiel Galliardo'}


def article(url):
    soup = BeautifulSoup(fetch(url, SITE), 'lxml')
    meta = soup.find(class_='edlp-single__meta')
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', meta.get_text(strip=True)) if meta else None
    fecha = f'{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else ''
    return fecha, soup.get_text('\n', strip=True).splitlines()


def top15():
    fecha, lines = article(URL)
    start = next(i for i, ln in enumerate(lines) if ln.strip().upper().startswith('TOP 15 TOTALES'))
    rows = []
    for ln in lines[start + 1:]:
        mm = re.match(r'^\s*\d+\s*º\s+(.+?)\s+(\d+)\s*(?::\s*(.*))?$', ln)
        if not mm:
            if rows:
                break
            continue
        names, goles, detalle = mm.group(1), int(mm.group(2)), (mm.group(3) or '').strip()
        for name in names.split('/'):
            name = FIX.get(name.strip(), name.strip())
            nota = ('total de goles con el club (era amateur + profesional + copas nacionales + internacionales '
                    f'+ ascenso, según corresponda) según la lista TOP 15 TOTALES del club; dato al {fecha}')
            if detalle:
                nota += f'; desglose de la fuente: {detalle}'
            rows.append({'equipo_id': 'estudiantes', 'jugador': name, 'goles': goles,
                         'alias': ALIAS.get(name, ''), 'fuente': URL, 'fecha_dato': fecha, 'nota': nota})
    return rows


def defensores():
    fecha, lines = article(URL_DEF)
    start = next(i for i, ln in enumerate(lines) if 'DEFENSORES GOLEADORES' in ln.upper())
    rows = []
    for ln in lines[start + 1:]:
        mm = re.match(r'^([A-ZÁÉÍÓÚÑ][^\d#]+?)\s+(\d+)$', ln.strip())
        if not mm:
            break
        rows.append({'equipo_id': 'estudiantes', 'jugador': mm.group(1).strip(), 'goles': int(mm.group(2)),
                     'alias': '', 'fuente': URL_DEF, 'fecha_dato': fecha,
                     'nota': ('goles con la camiseta del club según la lista LOS 8 DEFENSORES GOLEADORES del sitio '
                              f'oficial; la nota no detalla competiciones (excluye un gol en amistoso); dato al {fecha}')})
    return rows


def main():
    rows = top15() + defensores()
    out = write_csv(ROOT / 'data' / 'sources' / 'estudiantesdelaplata_argentina.csv', rows)
    print(Counter(r['equipo_id'] for r in rows), file=sys.stderr)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
