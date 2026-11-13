"""Goles de liga por club según RSSSF, "Argentina - All-Time Topscorers in League"
(Pablo Ciullini y Tomás Rodríguez Couto), https://rsssf.org/tablesa/argtops-allt.html

La tabla lista a los jugadores con 100 o más goles en la Primera División argentina y desglosa sus goles
de liga por club. Para cada club de interés se toma la columna de goles de LIGA de esa fila (dato
explícito). Las columnas de copas nacionales e internacionales de esa misma fila se copian en `nota`
sin sumarlas, para que quien use el dato decida.

Uso: python3 scripts/sources/rsssf_sudamerica.py
Salida: data/sources/rsssf_sudamerica.csv
"""
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, write_csv  # noqa: E402

SITE = 'rsssf'
URL = 'https://rsssf.org/tablesa/argtops-allt.html'
CLUBS = {
    'Boca Juniors': 'boca-juniors', 'Boca': 'boca-juniors',
    'River Plate': 'river-plate',
    'Independiente': 'independiente',
    'Racing Club': 'racing-club',
    'San Lorenzo': 'san-lorenzo',
    'Estudiantes LP': 'estudiantes', 'Estudiantes (LP)': 'estudiantes', 'Estudiantes de La Plata': 'estudiantes',
    'Rosario Central': 'rosario-central',
}
# Columnas (posición del último carácter tras expandir tabulaciones a 8) de la tabla de RSSSF.
COLS = {'liga': 123, 'pj': 131, 'copa_nac': 139, 'copa_int': 148, 'total': 156}
CLUB_START = 80
PARTICLES = {'de', 'del', 'la', 'las', 'los', 'di', 'da', 'do', 'dos', 'van', 'von', 'y'}


def nice_surname(s):
    words = s.lower().split()
    out = []
    for i, w in enumerate(words):
        out.append(w if (i > 0 and w in PARTICLES) else '-'.join(p[:1].upper() + p[1:] for p in w.split('-')))
    return ' '.join(out)


def nice_name(raw):
    """'SANFILIPPO, José Francisco' -> ('José Francisco Sanfilippo', 'José Sanfilippo')."""
    raw = raw.replace('*', '').strip()
    if ',' not in raw:
        return raw.title(), ''
    last, first = [x.strip() for x in raw.split(',', 1)]
    full = f'{first} {nice_surname(last)}'.strip()
    parts = first.split()
    short = f'{parts[0]} {nice_surname(last)}' if len(parts) > 1 else ''
    return full, short


def numbers_by_col(line):
    found = {}
    for m in re.finditer(r'\d+(?:\[#\])?\*?', line):
        end = m.end()
        val = int(re.match(r'\d+', m.group()).group())
        for key, col in COLS.items():
            if abs(end - col) <= 1 and end > CLUB_START + 5:
                found[key] = val
    return found


def main():
    text = BeautifulSoup(fetch(URL, SITE), 'lxml').get_text()
    upd = re.search(r'Last updated:\s*(\d{1,2} \w{3} \d{4})', text)
    fecha = ''
    if upd:
        import datetime
        fecha = datetime.datetime.strptime(upd.group(1), '%d %b %Y').date().isoformat()
    rows = []
    player = short = None
    for line in text.splitlines():
        line = line.expandtabs(8).rstrip()
        if not line.strip() or line.strip().startswith('-'):
            continue
        m = re.match(r'^\s*(?:\d+\.)?\s+([A-ZÁÉÍÓÚÑÜ][^()]*?,[^()]*?)\s*\(\d{4}', line[:CLUB_START])
        if m:
            player, short = nice_name(m.group(1))
        if player is None or len(line) <= CLUB_START:
            continue
        club_part = line[CLUB_START:]
        cm = re.match(r'^(\S.*?)(?:\s*\([^)]*\))*\s{2,}\d', club_part)
        if not cm:
            continue
        club = re.sub(r'\s*\([^)]*\)\s*$', '', cm.group(1).strip()).strip()
        club = re.sub(r'\s*\(\d{4}[^)]*\)', '', club).strip()
        team = CLUBS.get(club)
        if not team:
            continue
        nums = numbers_by_col(line)
        if 'liga' not in nums:
            print('sin goles de liga:', line, file=sys.stderr)
            continue
        extra = []
        if 'copa_nac' in nums:
            extra.append(f'copas nacionales con este club: {nums["copa_nac"]}')
        if 'copa_int' in nums:
            extra.append(f'copas internacionales con este club: {nums["copa_int"]}')
        nota = 'solo liga (Primera División argentina, amateur y profesional); lista limitada a jugadores con 100+ goles de liga en su carrera'
        if extra:
            nota += '; la misma tabla indica ' + ', '.join(extra)
        if nums['liga'] <= 0:
            continue
        rows.append({'equipo_id': team, 'jugador': player, 'goles': nums['liga'], 'alias': short,
                     'fuente': URL, 'fecha_dato': fecha, 'nota': nota})
    rows.sort(key=lambda r: (r['equipo_id'], -r['goles'], r['jugador']))
    out = write_csv(ROOT / 'data' / 'sources' / 'rsssf_sudamerica.csv', rows)
    from collections import Counter
    print(Counter(r['equipo_id'] for r in rows), file=sys.stderr)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
