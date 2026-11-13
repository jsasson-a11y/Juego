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


RANKING = BASE + 'records-jugadores/50/1/0/1905/2026/6/0/0.html'  # top 50 "Más goles", solo oficiales
CHALLENGED = ROOT / '.cache' / SITE / '_desafio_antibots.txt'


def player_id(url):
    m = re.search(r'/jugadores/[^/]+/(\d+)/', url)
    return m.group(1) if m else None


def ranking_rows():
    """Top 50 goleadores oficiales (para cubrir fichas que no se pudieron descargar)."""
    s = BeautifulSoup(fetch(RANKING, SITE, delay=1.8), 'lxml')
    out = {}
    for tr in s.find_all('tr'):
        tds = tr.find_all('td')
        a = tr.find('a', href=re.compile(r'/jugadores/'))
        if not a or len(tds) < 3:
            continue
        nums = [td.get_text(strip=True) for td in tds if td.get_text(strip=True).isdigit()]
        if len(nums) < 2:
            continue
        pid = player_id(a['href'])
        name = re.sub(r'^Partidos y Goles de\s+', '', a.get('title') or a.get_text(' ', strip=True)).strip()
        if not name or name.lower().startswith('partidos y goles'):
            name = tds[1].get_text(' ', strip=True)
        out[pid] = (name, int(nums[0]))
    return out


def main():
    urls = player_urls()
    challenged = set(CHALLENGED.read_text().split()) if CHALLENGED.exists() else set()
    print(f'{len(urls)} fichas de jugador; {len(challenged)} omitidas por desafío anti-bots previo', file=sys.stderr)
    rows, seen_ids = [], set()
    consecutive = 0
    for i, url in enumerate(urls, 1):
        if url in challenged:
            continue
        try:
            html = fetch(url, SITE, delay=1.8)
            consecutive = 0
        except Blocked as e:
            # El sitio a veces responde con una página "One moment, please..." (verificación anti-bots).
            # No se reintenta ni se sortea: se anota la URL y se sigue; si se repite mucho, se abandona.
            print('desafío/bloqueo:', e, file=sys.stderr)
            challenged.add(url)
            CHALLENGED.write_text('\n'.join(sorted(challenged)))
            consecutive += 1
            if consecutive >= 5:
                print('demasiados bloqueos seguidos: se detiene la descarga', file=sys.stderr)
                break
            continue
        except Exception as e:  # noqa: BLE001
            print('error', url, e, file=sys.stderr)
            continue
        name, goals = parse_player(html)
        if i % 100 == 0:
            print(i, name, goals, file=sys.stderr)
        if not name or goals is None:
            continue
        seen_ids.add(player_id(url))
        if goals <= 0:
            continue
        rows.append({'equipo_id': 'boca-juniors', 'jugador': name, 'goles': goals,
                     'alias': short_alias(name), 'fuente': url, 'fecha_dato': '', 'nota': NOTA})
    added = 0
    try:
        for pid, (name, goals) in ranking_rows().items():
            if pid not in seen_ids and goals > 0:
                rows.append({'equipo_id': 'boca-juniors', 'jugador': name, 'goles': goals,
                             'alias': short_alias(name), 'fuente': RANKING, 'fecha_dato': '', 'nota': NOTA})
                added += 1
    except Blocked as e:
        print('ranking no disponible:', e, file=sys.stderr)
    print(f'{added} jugadores añadidos desde el ranking top 50', file=sys.stderr)
    rows.sort(key=lambda r: (-r['goles'], r['jugador']))
    out = write_csv(ROOT / 'data' / 'sources' / 'historiadeboca_sudamerica.csv', rows)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
