"""Defensor Sporting: máximos goleadores históricos según Wikipedia en español.

La sección "Máximos goleadores" de https://es.wikipedia.org/wiki/Defensor_Sporting_Club dice:
  "Con 98 goles, Juan Emilio Píriz es el máximo goleador en la historia de Defensor Sporting,
   seguido por Alberto Santelli con 92, Antonio Cataldo con 87 y Eliomar Marcón con 85."
citando a LaRed21, "Defensor Sporting viene realizando la peor campaña", 7 de agosto de 2003
(ese artículo responde HTTP 403 a este script, por eso se usa la cita de Wikipedia).

Se lee la página HTML normal (/wiki/..., permitida por robots.txt; /w/ y /api/ no lo están) y se guarda
como fuente el enlace permanente a la revisión leída (?oldid=wgRevisionId).
La frase se valida con un patrón que debe coincidir; si cambió, el script falla.

Ejecutar desde la raíz del repo:  python3 scripts/sources/wikipedia_uruguay.py
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, write_csv  # noqa: E402

SITE = 'es.wikipedia.org'
URL = 'https://es.wikipedia.org/wiki/Defensor_Sporting_Club'
OUT = ROOT / 'data' / 'sources' / 'wikipedia_uruguay.csv'

SENTENCE = (r'Con (?P<g1>\d+) goles, (?P<n1>Juan Emilio Píriz) es el máximo goleador en la historia de Defensor Sporting, '
            r'seguido por (?P<n2>Alberto Santelli) con (?P<g2>\d+), (?P<n3>Antonio Cataldo) con (?P<g3>\d+) '
            r'y (?P<n4>Eliomar Marcón) con (?P<g4>\d+)\.')
NOTA = ('top 4 histórico según es.wikipedia, que cita a LaRed21 (2003-08-07); cifras de 2003; '
        'competiciones no especificadas')
ALIAS = {'Antonio Cataldo': 'Antonio Castaldo'}  # la misma página lo escribe "Castaldo" en la sección de historia


def main():
    raw = fetch(URL, SITE, delay=3)
    rev = re.search(r'"wgRevisionId":(\d+)', raw)
    if not rev:
        raise SystemExit('No se encontró wgRevisionId')
    txt = re.sub(r'(?s)<script.*?</script>|<style.*?</style>', ' ', raw)
    txt = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', txt)))
    m = re.search(SENTENCE, txt)
    if not m:
        raise SystemExit('No se encontró la frase de máximos goleadores en ' + URL)
    if 'peor campaña' not in txt or '2003' not in txt:
        raise SystemExit('No se encontró la cita de LaRed21 (2003)')
    fuente = f'{URL}?oldid={rev.group(1)}'
    rows = []
    for i in range(1, 5):
        name = m.group(f'n{i}')
        rows.append({'equipo_id': 'defensor-sporting', 'jugador': name, 'goles': int(m.group(f'g{i}')),
                     'alias': ALIAS.get(name, ''), 'fuente': fuente, 'fecha_dato': '2003-08-07', 'nota': NOTA})
    write_csv(OUT, rows)
    for r in rows:
        print(f"{r['equipo_id']:18} {r['jugador']:22} {r['goles']:>4}")
    print(f'{len(rows)} filas -> {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
