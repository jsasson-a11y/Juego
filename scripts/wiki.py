"""Herramientas para extraer tablas de goleadores de Wikipedia.

Uso típico:
    python3 scripts/wiki.py tables en "List of Manchester United F.C. players"
    -> lista las tablas de la página con sus columnas y primeras filas.
"""
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

CACHE = Path(__file__).resolve().parent.parent / '.cache' / 'wiki'
UA = 'GoleadoresGame/1.0 (data build script)'


_last = [0.0]


def api_get(req, tries=6):
    """GET con pausa entre pedidos y reintentos (Wikipedia limita la frecuencia: HTTP 429)."""
    for attempt in range(tries):
        wait = 1.5 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if attempt == tries - 1:
                raise
            retry = e.headers.get('Retry-After')
            time.sleep(int(retry) if retry and retry.isdigit() else 5 * (attempt + 1))
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def search(lang, query, limit=8):
    q = urllib.parse.urlencode({'action': 'query', 'list': 'search', 'srsearch': query, 'srlimit': limit,
                                'format': 'json', 'srnamespace': '0|104'})
    req = urllib.request.Request(f'https://{lang}.wikipedia.org/w/api.php?{q}', headers={'User-Agent': UA})
    return [x['title'] for x in api_get(req)['query']['search']]


def fetch_html(lang, title):
    """HTML renderizado de una página (vía API de MediaWiki), con caché local."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = re.sub(r'[^A-Za-z0-9_.-]+', '_', f'{lang}_{title}')[:180] + '.json'
    path = CACHE / key
    if path.exists():
        data = json.loads(path.read_text())
    else:
        q = urllib.parse.urlencode({'action': 'parse', 'page': title, 'prop': 'text|revid', 'format': 'json',
                                    'redirects': 1, 'formatversion': 2})
        req = urllib.request.Request(f'https://{lang}.wikipedia.org/w/api.php?{q}', headers={'User-Agent': UA})
        data = api_get(req)
        if 'error' in data:
            raise RuntimeError(f"{lang}:{title}: {data['error'].get('info')}")
        path.write_text(json.dumps(data))
    p = data['parse']
    return p['text'], p.get('revid'), p.get('title')


def page_url(lang, title, revid=None):
    base = f'https://{lang}.wikipedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_'))
    return f'{base}?oldid={revid}' if revid else base


def read_tables(lang, title):
    html, revid, real_title = fetch_html(lang, title)
    # Quitar notas al pie [1], [a] y spans ocultos de ordenamiento.
    html = re.sub(r'<sup[^>]*class="[^"]*reference[^"]*"[^>]*>.*?</sup>', '', html, flags=re.S)
    html = re.sub(r'<span[^>]*style="display:\s*none[^"]*"[^>]*>.*?</span>', '', html, flags=re.S)
    html = re.sub(r'<span[^>]*class="[^"]*sortkey[^"]*"[^>]*>.*?</span>', '', html, flags=re.S)
    # Nombre común + nombre completo en la misma celda (ej: "Neymar<br><small>Neymar da Silva...</small>").
    html = re.sub(r'<br\s*/?>', ' ‖ ', html)
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        tables = []
    return tables, revid, real_title


def flat_cols(df):
    cols = []
    for c in df.columns:
        if isinstance(c, tuple):
            parts = []
            for x in c:
                x = re.sub(r'\s+', ' ', str(x).replace('‖', ' ')).strip()
                if x and not x.startswith('Unnamed') and x not in parts:
                    parts.append(x)
            cols.append(' / '.join(parts))
        else:
            cols.append(re.sub(r'\s+', ' ', str(c).replace('‖', ' ')).strip())
    return cols


def to_int(v):
    if isinstance(v, str) and re.search(r'conced|recibid|sofrid|encaiss', v, re.I):
        return 0  # arqueros: la columna muestra goles recibidos
    if isinstance(v, float):
        return None if v != v else int(v)
    if isinstance(v, int):
        return v
    s = re.sub(r'^(\d+)\.0$', r'\1', str(v).strip())
    s = re.sub(r'\[.*?\]|\(.*?\)', '', s)
    s = re.sub(r'[\s,.]', '', s)
    m = re.match(r'^(\d+)', s)
    return int(m.group(1)) if m else None


def _clean(s):
    s = re.sub(r'[\u200b-\u200f\u2060\ufeff\xad]', '', s)
    s = re.sub(r'\[.*?\]|\(.*?\)', '', s)
    s = re.sub(r'[†‡§*¤#^~♦✝°]+', '', s)
    s = re.sub(r'\s+\d+$', '', s.strip())
    return re.sub(r'\s+', ' ', s).strip(' ,;')


def split_name(v):
    """Devuelve (nombre, [alias]) a partir de una celda; '‖' separa nombre común y nombre completo."""
    raw = str(v)
    m = re.search(r'\s*0*genannt0*\s*', raw)  # de.wikipedia: "Nombre completo genannt Apodo"
    if m:
        raw = raw[m.end():] + ' ‖ ' + raw[:m.start()]
    parts = [_clean(x) for x in raw.split('‖')]
    parts = [x for x in parts if x and x.lower() != 'nan']
    if not parts:
        return '', []
    name = parts[0]
    # "Apellido, Nombre" -> "Nombre Apellido"
    m = re.match(r'^([^,]+),\s*([^,]+)$', name)
    if m:
        name = f'{m.group(2)} {m.group(1)}'
    return name, [x for x in parts[1:] if x != name]


def clean_name(v):
    return split_name(v)[0]


def main():
    cmd, lang, title = sys.argv[1], sys.argv[2], sys.argv[3]
    if cmd == 'search':
        print(search(lang, title))
    if cmd == 'tables':
        tables, revid, real = read_tables(lang, title)
        print(f'{real} (rev {revid}) -> {len(tables)} tablas')
        for i, t in enumerate(tables):
            if len(t) < 5:
                continue
            print(f'\n[{i}] filas={len(t)} cols={flat_cols(t)}')
            t2 = t.copy()
            t2.columns = flat_cols(t)
            print(t2.head(3).to_string(max_colwidth=25))


if __name__ == '__main__':
    main()
