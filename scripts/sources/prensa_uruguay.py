"""Goleadores históricos de clubes uruguayos chicos según artículos de prensa (Montevideo Portal).

Sólo se usan cifras que el artículo enuncia explícitamente como total de goles de un jugador
con el club. Cada cifra se extrae con un patrón que DEBE coincidir; si el texto del artículo
cambió y el patrón no aparece, el script falla (no se inventa ni se estima nada).

Fuentes (robots.txt de montevideo.com.uy: "User-agent: *" sin restricciones para /Deportes/):
- Liverpool, 2021-02-26: Juan Ignacio Ramírez llega a 71 y supera a Roberto Chávez (70).
- Liverpool, 2025-10-26: "El Colo, máximo goleador histórico con 85 goles en 166 presencias
  entre 2015 y 2021".

No usados (ver informe): ESPN (robots.txt bloquea GPTBot), Tenfield (bloquea ClaudeBot/anthropic-ai),
LaRed21 (HTTP 403).

Ejecutar desde la raíz del repo:  python3 scripts/sources/prensa_uruguay.py
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, write_csv  # noqa: E402

SITE = 'montevideo.com.uy'
OUT = ROOT / 'data' / 'sources' / 'prensa_uruguay.csv'

# (url, [(patrón obligatorio, fila base)])  -- el grupo "g" del patrón son los goles.
ARTICLES = [
    ('https://www.montevideo.com.uy/Deportes/Liverpool-El-Colo-Ramirez-se-convirtio-en-el-maximo-goleador-de-la-historia-negriazul-uc779342', [
        (r'llegó a \d+ goles, superando en uno a Roberto Chávez que tenía (?P<g>\d+) festejos',
         {'equipo_id': 'liverpool-uy', 'jugador': 'Roberto Chávez', 'alias': '',
          'nota': 'récord histórico del club hasta 2021 (fue superado por Juan Ignacio Ramírez); '
                  'goles con Liverpool según Montevideo Portal; competiciones no especificadas'}),
    ]),
    ('https://www.montevideo.com.uy/Deportes/Liverpool-el-record-de-Juan-Ignacio-Ramirez-que-igualo-Abel-Hernandez-con-su-ultimo-gol-uc941097', [
        (r'El Colo, máximo goleador histórico con (?P<g>\d+) goles en \d+ presencias entre 2015 y 2021',
         {'equipo_id': 'liverpool-uy', 'jugador': 'Juan Ignacio Ramírez', 'alias': 'Colo Ramírez|Ignacio Ramírez',
          'nota': 'máximo goleador histórico del club según Montevideo Portal; 166 presencias entre 2015 y 2021; '
                  'competiciones no especificadas (en 2021 el mismo medio contaba 71 goles en 150 partidos oficiales); '
                  'la cifra abarca sólo 2015-2021, no goles de etapas posteriores'}),
    ]),
]


def text_of(raw):
    raw = re.sub(r'(?s)<script.*?</script>|<style.*?</style>', ' ', raw)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', raw))
    return re.sub(r'\s+', ' ', t)


def article_date(raw):
    m = re.search(r'(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}:\d{2}-03:00', raw)
    if not m:
        raise SystemExit('No se encontró la fecha del artículo')
    return m.group(1)


def main():
    rows = []
    for url, specs in ARTICLES:
        raw = fetch(url, SITE)
        txt = text_of(raw)
        fecha = article_date(raw)
        for pattern, base in specs:
            m = re.search(pattern, txt)
            if not m:
                raise SystemExit(f'Patrón no encontrado en {url}: {pattern}')
            goles = int(m.group('g'))
            rows.append({**base, 'goles': goles, 'fuente': url, 'fecha_dato': fecha})
    write_csv(OUT, rows)
    for r in rows:
        print(f"{r['equipo_id']:18} {r['jugador']:28} {r['goles']:>4}  {r['fecha_dato']}")
    print(f'{len(rows)} filas -> {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
