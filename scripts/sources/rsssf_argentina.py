"""Goles TOTALES por club (liga + copas nacionales + copas internacionales) según RSSSF,
"Argentina - All-Time Topscorers in League", https://rsssf.org/tablesa/argtops-allt.html

La tabla (jugadores con 100+ goles de liga en su carrera) da, por cada club de un jugador, los goles
de LIGA y, en columnas aparte, los de COPAS NACIONALES y COPAS INTERNACIONALES, más una columna TOTAL
de toda la carrera (todos los clubes listados). Este script sólo emite un total por club cuando la
página lo da completo, sin estimar nada:

  a) la fila del club trae los tres componentes (liga, copas nacionales, internacionales) escritos:
     total = suma de los tres;
  b) el jugador tiene un único club en la tabla: el TOTAL de carrera de RSSSF es el total de ese club.

Si a la fila le falta algún componente (celda vacía) y el jugador tuvo más de un club, NO se emite nada
(esa fila ya está como "solo liga" en data/sources/rsssf_sudamerica.csv). Sólo los 6 clubes argentinos
de este lote (Boca ya tiene otras fuentes).

Uso: python3 scripts/sources/rsssf_argentina.py
Salida: data/sources/rsssf_argentina.csv
"""
import datetime
import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, write_csv  # noqa: E402
from rsssf_sudamerica import CLUB_START, CLUBS, SITE, URL, nice_name, numbers_by_col  # noqa: E402

TEAMS = {'river-plate', 'independiente', 'racing-club', 'san-lorenzo', 'estudiantes', 'rosario-central'}
PLAYER_RE = re.compile(r'^\s*(?:\d+\.)?\s+([A-ZÁÉÍÓÚÑÜ][^()]*?,[^()]*?)\s*\(\d{4}')


def fix_apostrophe(name):
    """"D'alessandro" -> "D'Alessandro"."""
    return re.sub(r"\b([DO]')([a-zà-ÿ])", lambda m: m.group(1) + m.group(2).upper(), name)


def club_of(line):
    club_part = line[CLUB_START:]
    cm = re.match(r'^(\S.*?)(?:\s*\([^)]*\))*\s{2,}\d', club_part)
    if not cm:
        return None
    club = re.sub(r'\s*\([^)]*\)\s*$', '', cm.group(1).strip()).strip()
    return re.sub(r'\s*\(\d{4}[^)]*\)', '', club).strip()


def blocks(text):
    """Agrupa las líneas de la tabla por jugador: [(nombre_crudo, [(club, nums), ...], total)]."""
    out, cur = [], None
    for line in text.splitlines():
        line = line.expandtabs(8).rstrip()
        if not line.strip():
            continue
        if line.strip().startswith('-'):
            if cur:
                out.append(cur)
            cur = None
            continue
        m = PLAYER_RE.match(line[:CLUB_START])
        if m:
            if cur:
                out.append(cur)
            cur = {'raw': m.group(1), 'clubs': [], 'total': None}
        if cur is None or len(line) <= CLUB_START:
            continue
        club = club_of(line)
        if not club:
            continue
        nums = numbers_by_col(line)
        if 'liga' not in nums:
            continue
        if 'total' in nums and cur['total'] is None:
            cur['total'] = nums['total']
        cur['clubs'].append((club, nums))
    if cur:
        out.append(cur)
    return out


def main():
    text = BeautifulSoup(fetch(URL, SITE), 'lxml').get_text()
    upd = re.search(r'Last updated:\s*(\d{1,2} \w{3} \d{4})', text)
    fecha = datetime.datetime.strptime(upd.group(1), '%d %b %Y').date().isoformat() if upd else ''
    rows, skipped = [], Counter()
    for b in blocks(text):
        player, short = (fix_apostrophe(x) for x in nice_name(b['raw']))
        for club, nums in b['clubs']:
            team = CLUBS.get(club)
            if team not in TEAMS:
                continue
            comp = f"liga {nums['liga']}"
            if 'copa_nac' in nums and 'copa_int' in nums:
                goles = nums['liga'] + nums['copa_nac'] + nums['copa_int']
                nota = ('total = suma de liga + copas + internacionales según RSSSF '
                        f"({comp}, copas nacionales {nums['copa_nac']}, copas internacionales {nums['copa_int']})")
            elif len(b['clubs']) == 1 and b['total'] is not None:
                goles = b['total']
                parts = [comp]
                if 'copa_nac' in nums:
                    parts.append(f"copas nacionales {nums['copa_nac']}")
                if 'copa_int' in nums:
                    parts.append(f"copas internacionales {nums['copa_int']}")
                nota = ('total según la columna TOTAL de RSSSF (liga + copas nacionales + copas internacionales); '
                        'único club del jugador en la tabla; componentes mostrados: ' + ', '.join(parts))
            else:
                skipped[team] += 1
                continue
            nota += '; lista limitada a jugadores con 100+ goles de liga en su carrera'
            rows.append({'equipo_id': team, 'jugador': player, 'goles': goles, 'alias': short,
                         'fuente': URL, 'fecha_dato': fecha, 'nota': nota})
    rows.sort(key=lambda r: (r['equipo_id'], -r['goles'], r['jugador']))
    out = write_csv(ROOT / 'data' / 'sources' / 'rsssf_argentina.csv', rows)
    print(Counter(r['equipo_id'] for r in rows), file=sys.stderr)
    print('sin todos los componentes (se omiten):', dict(skipped), file=sys.stderr)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
