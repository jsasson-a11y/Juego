"""Goleadores de Boca Juniors según historiadeboca.com.ar (base de datos partido a partido).

Recorre las fichas de jugador listadas en el sitemap (vista "Sólo los Oficiales", 1905-2026)
y toma "Goles Convertidos". Incluye torneos oficiales de AFA (liga y copas) e internacionales
oficiales; excluye amistosos.

Uso: python3 scripts/sources/historiadeboca_sudamerica.py
Salida: data/sources/historiadeboca_sudamerica.csv
"""
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, Blocked, fetch, short_alias, write_csv  # noqa: E402

SITE = 'historiadeboca'
BASE = 'https://www.historiadeboca.com.ar/'
NOTA = 'solo partidos oficiales (AFA liga y copas + internacionales oficiales), 1905-2026; excluye amistosos'


def player_urls():
    xml = fetch(BASE + 'sitemap.xml', SITE)
    urls = re.findall(r'<loc>(https://www\.historiadeboca\.com\.ar/jugadores/[^<]+/\d+/1905/2026/6\.html)</loc>', xml)
    return sorted(set(urls))


def parse_player(html):
    s = BeautifulSoup(html, 'lxml')
    h1s = [h.get_text(' ', strip=True) for h in s.find_all('h1')]
    name = next((h for h in h1s if 'HISTORIA DE BOCA' not in h.upper()), '')
    goals = None
    for p in s.find_all('p'):
        t = p.get_text(' ', strip=True)
        m = re.match(r'Goles Convertidos:\s*(\d+)', t)
        if m:
            goals = int(m.group(1))
            break
    return name, goals


def main():
    urls = player_urls()
    print(f'{len(urls)} fichas de jugador', file=sys.stderr)
    rows = []
    for i, url in enumerate(urls, 1):
        try:
            html = fetch(url, SITE, delay=1.8)
        except Blocked as e:
            print('BLOQUEADO:', e, file=sys.stderr)
            break
        except Exception as e:  # noqa: BLE001
            print('error', url, e, file=sys.stderr)
            continue
        name, goals = parse_player(html)
        if i % 100 == 0:
            print(i, name, goals, file=sys.stderr)
        if not name or goals is None or goals <= 0:
            continue
        rows.append({'equipo_id': 'boca-juniors', 'jugador': name, 'goles': goals,
                     'alias': short_alias(name), 'fuente': url, 'fecha_dato': '', 'nota': NOTA})
    rows.sort(key=lambda r: (-r['goles'], r['jugador']))
    out = write_csv(ROOT / 'data' / 'sources' / 'historiadeboca_sudamerica.csv', rows)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
