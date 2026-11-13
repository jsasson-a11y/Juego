"""Utilidades compartidas por los extractores de scripts/sources/.

- Descargas con User-Agent honesto, pausa mínima por sitio y caché en .cache/<sitio>/.
- Respeta robots.txt (urllib.robotparser) antes de cada pedido.
- El contenido descargado se trata como datos: sólo se parsea, nunca se ejecuta.
"""
import csv
import hashlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_ROOT = ROOT / '.cache'
UA = 'GoleadoresGame/1.0 (data build script)'
HEADER = ['equipo_id', 'jugador', 'goles', 'alias', 'fuente', 'fecha_dato', 'nota']

_last = {}
_robots = {}


class Blocked(Exception):
    pass


def _robots_ok(url):
    p = urllib.parse.urlsplit(url)
    base = f'{p.scheme}://{p.netloc}'
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + '/robots.txt', headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read().decode('utf-8', 'replace')
            # Algunos sitios devuelven una página HTML de error con código 200: se ignora.
            rp.parse(body.splitlines() if 'user-agent' in body.lower() else [])
        except urllib.error.HTTPError as e:
            rp.parse([] if e.code in (404, 410) else ['User-agent: *', 'Disallow: /'])
        except Exception:
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(UA, url)


def fetch(url, site, delay=1.6, encoding=None, tries=3, data=None, cache_tag=''):
    """Devuelve el texto de `url`, usando caché en .cache/<site>/. Lanza Blocked ante 403/429/captcha.

    `cache_tag` permite guardar una segunda copia (p. ej. una nueva descarga de una página cuyo orden varía)."""
    cache = CACHE_ROOT / site
    cache.mkdir(parents=True, exist_ok=True)
    key = re.sub(r'[^A-Za-z0-9_.-]+', '_', url.split('://', 1)[-1])[:150]
    key += '_' + hashlib.sha1((url + (data or '') + cache_tag).encode()).hexdigest()[:10] + '.html'
    path = cache / key
    if path.exists():
        raw = path.read_bytes()
    else:
        if not _robots_ok(url):
            raise Blocked(f'robots.txt no permite {url}')
        host = urllib.parse.urlsplit(url).netloc
        for attempt in range(tries):
            wait = delay - (time.time() - _last.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            _last[host] = time.time()
            try:
                req = urllib.request.Request(url, headers={'User-Agent': UA},
                                             data=data.encode() if data else None)
                with urllib.request.urlopen(req, timeout=90) as r:
                    raw = r.read()
                break
            except urllib.error.HTTPError as e:
                if e.code in (403, 429, 503) or e.code == 404:
                    raise Blocked(f'HTTP {e.code} en {url}') if e.code != 404 else e
                if attempt == tries - 1:
                    raise
                time.sleep(5 * (attempt + 1))
            except (urllib.error.URLError, TimeoutError):
                if attempt == tries - 1:
                    raise
                time.sleep(5 * (attempt + 1))
        low = raw[:5000].lower()
        if b'just a moment' in low and b'challenge' in raw.lower():
            raise Blocked(f'desafío anti-bots en {url}')
        path.write_bytes(raw)
    if encoding:
        return raw.decode(encoding, 'replace')
    m = re.search(rb'charset=["\']?([A-Za-z0-9_-]+)', raw[:3000])
    enc = m.group(1).decode() if m else 'utf-8'
    try:
        return raw.decode(enc)
    except (LookupError, UnicodeDecodeError):
        return raw.decode('utf-8', 'replace')


def write_csv(path, rows):
    """rows: iterable de dicts con las claves de HEADER."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=HEADER, delimiter=';')
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in HEADER})
    return path


def short_alias(full):
    """'Diego Armando Maradona' -> 'Diego Maradona' (variante corta como alias, sólo si hay 3+ palabras)."""
    parts = full.split()
    if len(parts) >= 3:
        return f'{parts[0]} {parts[-1]}'
    return ''
