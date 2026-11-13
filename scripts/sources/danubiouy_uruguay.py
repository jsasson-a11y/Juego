"""Danubio F.C.: goleadores con total de goles indicado en la web oficial del club (danubio.uy).

Página: https://danubio.uy/futbol/grandes-jugadores ("Eternos en la franja").
robots.txt de danubio.uy: "User-agent: * / Allow: /" (sólo bloquea /api/, /_nuxt/, /__nuxt_error).

La página renderizada en el servidor muestra cada jugador como una tarjeta con sus INICIALES
(el nombre completo lo agrega el JavaScript del sitio, que está en /_nuxt/, bloqueado por robots),
un texto y una línea de logros. Sólo se toman las tarjetas que enuncian un total de goles con el
club, y cada una se valida con un patrón que debe coincidir (iniciales + período + texto):

- DP  "goleador histórico del club ... con 72 tantos y más de 200 partidos" -> Diego Perrone
      (además el <title> de la página es "DIEGO PERRONE | Danubio FC").
- RDS "Década del 80-90 ... Primer bicampeón uruguayo • 71 goles" -> Rubén da Silva
- EC  "2000-2003 ... En el año 2000 hizo 33 goles ... 53 goles en 3 años" -> Javier (Ernesto) Chevantón
      (goleador del Campeonato Uruguayo 2000 con 33 goles jugando para Danubio).

No se usan tarjetas con goles de una sola temporada (p. ej. "12 tantos del Campeonato Uruguayo de 1966").
La página no indica qué competiciones abarcan los totales ni la fecha de actualización.

Ejecutar desde la raíz del repo:  python3 scripts/sources/danubiouy_uruguay.py
"""
import html
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, write_csv  # noqa: E402

SITE = 'danubio.uy'
URL = 'https://danubio.uy/futbol/grandes-jugadores'
OUT = ROOT / 'data' / 'sources' / 'danubiouy_uruguay.csv'

# iniciales, período mostrado en la tarjeta, patrón del total (grupo g), jugador, alias, nota extra
CARDS = [
    ('DP', '200+ partidos',
     r'goleador histórico del club\. Genuino producto del semillero franjeado, con (?P<g>\d+) tantos',
     'Diego Perrone', '',
     'goleador histórico del club según su web oficial (tarjeta "DP"; el título de la página es "DIEGO PERRONE")'),
    ('RDS', 'Década del 80-90',
     r'Primer bicampeón uruguayo • (?P<g>\d+) goles',
     'Rubén da Silva', 'Rubén Da Silva|Polillita da Silva|Polillita',
     'tarjeta con iniciales "RDS" (década del 80-90, "Primer bicampeón uruguayo"); nombre completo no visible '
     'sin JavaScript, identificado por iniciales y época'),
    ('EC', '2000-2003',
     r'En el año 2000 hizo 33 goles, tercer mejor registro de la historia del fútbol uruguayo\. \| (?P<g>\d+) goles en 3 años',
     'Javier Chevantón', 'Ernesto Chevantón|Ernesto Javier Chevantón',
     'tarjeta con iniciales "EC" ("En el año 2000 hizo 33 goles"; Chevantón fue goleador del Uruguayo 2000 con 33 con Danubio); '
     'la web dice "53 goles en 3 años"; nombre identificado por iniciales y época'),
]


def cards_text(raw):
    raw = re.sub(r'(?s)<script.*?</script>|<style.*?</style>', ' ', raw)
    t = html.unescape(re.sub(r'<[^>]+>', ' | ', raw))
    return re.sub(r'(\s*\|\s*)+', ' | ', t)


def main():
    raw = fetch(URL, SITE)
    if not re.search(r'<title>DIEGO PERRONE \| Danubio FC</title>', raw):
        raise SystemExit('La página cambió: no se encontró el título "DIEGO PERRONE | Danubio FC"')
    txt = cards_text(raw)
    consultado = date.today().isoformat()
    rows = []
    for initials, period, pattern, name, alias, extra in CARDS:
        # Cada tarjeta: "| INICIALES | período | texto | logros |"; se busca el patrón dentro de esa tarjeta.
        m = re.search(r'\| ' + re.escape(initials) + r' \| ' + re.escape(period) + r' \|(.{0,600}?)(?=\| [A-Z]{2,3} \| |ETERNOS EN LA FRANJA)', txt)
        if not m:
            raise SystemExit(f'No se encontró la tarjeta {initials} ({period})')
        g = re.search(pattern, m.group(1))
        if not g:
            raise SystemExit(f'Patrón no encontrado en la tarjeta {initials}: {pattern}')
        rows.append({
            'equipo_id': 'danubio', 'jugador': name, 'goles': int(g.group('g')), 'alias': alias,
            'fuente': URL, 'fecha_dato': '',
            'nota': f'web oficial del club; {extra}; competiciones no especificadas; consultado {consultado}',
        })
    write_csv(OUT, rows)
    for r in rows:
        print(f"{r['equipo_id']:10} {r['jugador']:22} {r['goles']:>4}")
    print(f'{len(rows)} filas -> {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
