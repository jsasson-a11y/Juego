"""Goleadores del Palmeiras según el sitio oficial del club, página "Listas e Rankings"
(https://palmeiras.com.br/listas-e-rankings/), bloque "100 Maiores Artilheiros" (incluye empates, ~105).

Uso: python3 scripts/sources/palmeiras_sudamerica.py
Salida: data/sources/palmeiras_sudamerica.csv
"""
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, write_csv  # noqa: E402

SITE = 'palmeiras'
URL = 'https://palmeiras.com.br/listas-e-rankings/'
NOTA = ('top ~100 del ranking oficial del club ("100 Maiores Artilheiros"); el sitio no aclara si cuenta '
        'amistosos (la cuenta histórica del Palmeiras suele incluir todos los partidos)')


def main():
    s = BeautifulSoup(fetch(URL, SITE, delay=2.0), 'lxml')
    h3 = next((h for h in s.find_all('h3') if 'Maiores Artilheiros' in h.get_text()), None)
    if not h3:
        sys.exit('No se encontró el bloque "Maiores Artilheiros"; revisar el script.')
    block = h3.find_parent('div')
    fecha = ''
    upd = s.find(string=re.compile(r'Atualizado até \d{2}/\d{2}/\d{4}'))
    if upd:
        d, m, y = re.search(r'(\d{2})/(\d{2})/(\d{4})', upd).groups()
        fecha = f'{y}-{m}-{d}'
    rows = []
    for cell in block.select('div.div-inner-center'):
        txt = cell.get_text(' ', strip=True)
        g = re.search(r'(\d+)\s+gols?\b', txt)
        if not g:
            continue
        goals = int(g.group(1))
        names = []
        for p in cell.find_all('p'):
            # Los empatados van en el mismo <p> separados por <br/>.
            names += [x.strip() for x in p.get_text('\n').split('\n') if x.strip()]
        for name in names:
            alias = ''
            m = re.match(r'^(.*?)\s*\((.+)\)$', name)
            if m:  # "Dudu (Eduardo Pereira Rodrigues)": apodo + nombre completo para desambiguar
                name, alias = m.group(1).strip(), m.group(2).strip()
            rows.append({'equipo_id': 'palmeiras', 'jugador': name, 'goles': goals, 'alias': alias,
                         'fuente': URL, 'fecha_dato': fecha, 'nota': NOTA})
    rows.sort(key=lambda r: (-r['goles'], r['jugador']))
    out = write_csv(ROOT / 'data' / 'sources' / 'palmeiras_sudamerica.csv', rows)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
