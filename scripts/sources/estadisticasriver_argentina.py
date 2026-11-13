"""Goleadores históricos de River Plate según Estadísticas de River (https://estadisticasriver.com/goleadores/).

Sitio de estadísticas de hinchas (no afiliado al club). La tabla "100 máximos anotadores del club"
ordena por goles totales en partidos oficiales; según las fichas del propio sitio, "los datos incluyen
todas las competencias oficiales disputadas con la camiseta millonaria" (liga, copas nacionales e
internacionales). La página no indica fecha de corte: se anota la fecha de descarga en `nota`.

Uso: python3 scripts/sources/estadisticasriver_argentina.py
Salida: data/sources/estadisticasriver_argentina.csv
"""
import datetime
import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE_ROOT, ROOT, fetch, write_csv  # noqa: E402

SITE = 'estadisticasriver'
URL = 'https://estadisticasriver.com/goleadores/'
PARTICLES = {'de', 'del', 'la', 'las', 'los', 'di', 'da', 'do', 'dos', 'van', 'von', 'y'}

# Nombre completo en la fuente -> nombre con que lo conocen los hinchas (cuando la regla
# "primer nombre + apellido" no alcanza: apellidos compuestos, segundo nombre de uso, apodos).
FAN_NAME = {
    'Ramón Ismael Medina Bello': 'Ramón Medina Bello',
    'Juan Pablo Ángel': 'Juan Pablo Ángel',
    'José Manuel Moreno': 'José Manuel Moreno',
    'Juan José López': 'Juan José López',
    'Juan Carlos Sarnari': 'Juan Carlos Sarnari',
    'Juan Carlos Muñoz': 'Juan Carlos Muñoz',
    'Juan Carlos Lallana': 'Juan Carlos Lallana',
    'Juan Carlos Irurieta': 'Juan Carlos Irurieta',
    'Juan Fernando Quintero': 'Juan Fernando Quintero',
    'José Marcelo Salas': 'Marcelo Salas',
    'Radamel Falcao García': 'Radamel Falcao',
    'Vladem Lázaro Ruiz Quevedo “Delem”': 'Delem',
    'Arnaldo Ariel Ortega': 'Ariel Ortega',
    'Enrique Omar Sívori': 'Omar Sívori',
    'José Atilio Granara Costa': 'José Granara Costa',
    'Rogelio Gabriel Funes Mori': 'Rogelio Funes Mori',
    'José R. Penichet': 'José Penichet',
}
EXTRA_ALIAS = {
    'Norberto Alonso': 'Beto Alonso',
    'Ariel Ortega': 'Burrito Ortega',
    'Marcelo Gallardo': 'Muñeco Gallardo',
    'Gonzalo Martínez': 'Pity Martínez',
    'Rafael Borré': 'Santos Borré',
    'Radamel Falcao': 'Falcao',
    'Delem': 'Vladem Ruiz Quevedo',
    'Ramón Díaz': 'Ramón Ángel Díaz',
}


def fan_name(full):
    full = full.replace('’', "'").strip()
    if full in FAN_NAME:
        return FAN_NAME[full]
    w = full.split()
    if len(w) <= 2:
        return full
    # Apellido: última palabra, más las partículas que la preceden ("De La Cruz", "Di Stéfano", "Da Silva").
    i = len(w) - 1
    while i - 1 > 0 and w[i - 1].lower() in PARTICLES:
        i -= 1
    return ' '.join([w[0]] + w[i:])


def main():
    html = fetch(URL, SITE)
    soup = BeautifulSoup(html, 'lxml')
    cached = sorted((CACHE_ROOT / SITE).glob('estadisticasriver.com_goleadores__*.html'))
    fecha_desc = (datetime.date.fromtimestamp(cached[0].stat().st_mtime).isoformat() if cached
                  else datetime.date.today().isoformat())
    rows = []
    for tr in soup.find('table').find_all('tr'):
        if not tr.has_attr('data-goles'):
            continue
        full = tr.find('td', class_='td-nombre').get_text(' ', strip=True)
        periodo = tr.find('td', class_='td-periodo').get_text(' ', strip=True)
        goles, pj = int(tr['data-goles']), tr.get('data-pj', '?')
        jugador = fan_name(full)
        clean = re.sub(r'\s*“[^”]*”', '', full).replace('’', "'")
        alias = [a for a in (clean, EXTRA_ALIAS.get(jugador, '')) if a and a != jugador]
        nota = (f'goles en partidos oficiales (todas las competencias oficiales: liga, copas nacionales e '
                f'internacionales); top 100 del sitio; {pj} PJ'
                + (f', {periodo}' if periodo and periodo != '-' else '')
                + f'; sin fecha de corte en la fuente (consultado {fecha_desc})')
        rows.append({'equipo_id': 'river-plate', 'jugador': jugador, 'goles': goles,
                     'alias': '|'.join(dict.fromkeys(alias)), 'fuente': URL, 'fecha_dato': '', 'nota': nota})
    out = write_csv(ROOT / 'data' / 'sources' / 'estadisticasriver_argentina.csv', rows)
    print(Counter(r['equipo_id'] for r in rows), file=sys.stderr)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
