"""Goleadores de San Lorenzo según Estadísticas CASLA (https://estadisticascasla.com/tablas/goleadores).

Archivo estadístico de hinchas, partido a partido. El ranking "Goleadores históricos" lista a todos los
jugadores con goles (PJ y goles). Las competiciones de la base son oficiales (ligas, copas nacionales,
Libertadores, Sudamericana, Mercosur y otras internacionales; no figuran amistosos) y empiezan en 1931:
es decir, SOLO PROFESIONALISMO. Para quienes debutaron desde 1931 es su total oficial; para quienes
jugaron antes (era amateur) es un dato parcial, y así se indica en `nota`.

La fuente escribe los nombres sin tildes ("Garcia, Diego"); se restituyen tildes de nombres y apellidos
españoles frecuentes sólo para mostrar (la combinación ignora tildes). La página no indica fecha de
corte: se anota la fecha de descarga.

Uso: python3 scripts/sources/estadisticascasla_argentina.py
Salida: data/sources/estadisticascasla_argentina.csv
"""
import datetime
import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE_ROOT, ROOT, fetch, write_csv  # noqa: E402

SITE = 'estadisticascasla'
URL = 'https://estadisticascasla.com/tablas/goleadores'

ACCENTS = {w.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u'): w
           for w in '''José Héctor Rubén Ramón Martín Néstor Raúl Ángel Víctor Andrés Hernán Sebastián Julián Adrián
           Fabián Iván Matías Nicolás Tomás Joaquín Agustín Máximo Darío César Simón Germán Benjamín Valentín Fermín
           Elías Jesús Lázaro René García Rodríguez González Fernández López Martínez Sánchez Pérez
           Gómez Díaz Hernández Ramírez Álvarez Jiménez Giménez Benítez Domínguez Suárez Méndez Gutiérrez Vázquez
           Velázquez Chávez Juárez Márquez Ríos Lángara Benavídez Alarcón Magán Peñalba Ojeda Muñoz Núñez Ibáñez
           Bóveda Galván Acuña Andújar Ávalos Aníbal Leguizamón Cáceres Rolón Ludueña'''.split()
           if w.lower() != w.lower().translate(str.maketrans('áéíóú', 'aeiou'))}


def accent(word):
    base = ACCENTS.get(word.lower())
    if not base:
        return word
    return base if word[:1].isupper() else base.lower()


def names(raw):
    """'Sanfilippo, Jose Francisco' -> ('José Sanfilippo', 'José Francisco Sanfilippo')."""
    raw = ' '.join(accent(w) for w in raw.replace(',', ' , ').split()).replace(' , ', ', ').strip()
    if ',' not in raw:
        return raw, ''
    last, first = [x.strip() for x in raw.split(',', 1)]
    if not first:
        return last, ''
    full = f'{first} {last}'
    short = f'{first.split()[0]} {last}'
    return short, (full if full != short else '')


def main():
    html = fetch(URL, SITE)
    soup = BeautifulSoup(html, 'lxml')
    cached = sorted((CACHE_ROOT / SITE).glob('estadisticascasla.com_tablas_goleadores_*.html'))
    fecha_desc = (datetime.date.fromtimestamp(cached[0].stat().st_mtime).isoformat() if cached
                  else datetime.date.today().isoformat())
    rows = []
    for a in soup.find_all('a', class_='archivo-row'):
        if not a.has_attr('data-goles'):
            continue
        goles = int(a['data-goles'])
        if goles <= 0:
            continue
        jugador, alias = names(a['data-nombre'])
        meta = a.find('span', class_='meta')
        puesto = meta.get_text(' ', strip=True) if meta else ''
        nota = ('solo profesionalismo (partidos oficiales desde 1931: liga + copas nacionales + internacionales); '
                'para quien debutó desde 1931 equivale a su total oficial, para quien jugó en la era amateur es '
                f'parcial; {a.get("data-pj", "?")} PJ' + (f', {puesto}' if puesto else '')
                + f'; sin fecha de corte en la fuente (consultado {fecha_desc})')
        rows.append({'equipo_id': 'san-lorenzo', 'jugador': jugador, 'goles': goles, 'alias': alias,
                     'fuente': URL, 'fecha_dato': '', 'nota': nota})
    rows.sort(key=lambda r: (-r['goles'], r['jugador']))
    out = write_csv(ROOT / 'data' / 'sources' / 'estadisticascasla_argentina.csv', rows)
    print(Counter(r['equipo_id'] for r in rows), file=sys.stderr)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
