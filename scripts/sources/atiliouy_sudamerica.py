"""Goleadores de Nacional (Montevideo) según atilio.uy ("Atilio Software", aplicación de la Comisión de
Historia y Estadística del Club Nacional de Football).

La página https://atilio.uy/goleadores es una grilla PrimeFaces (JSF). Por defecto suma partidos oficiales
y amistosos; aquí se aplica el filtro del propio sitio "Oficial" (sin "Amistoso" ni "Entrenamiento") y se
pagina de a 200 filas, igual que haría un navegador al usar los controles de la página.

Uso: python3 scripts/sources/atiliouy_sudamerica.py
Salida: data/sources/atiliouy_sudamerica.csv
"""
import hashlib
import http.cookiejar
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE_ROOT, ROOT, UA, write_csv  # noqa: E402

URL = 'https://atilio.uy/goleadores'
CACHE = CACHE_ROOT / 'atiliouy'
NOTA = ('solo partidos oficiales (filtro "Oficial" del sitio, sin amistosos); Comisión de Historia y '
        'Estadística del Club Nacional de Football')
ROWS = 200

_cj = http.cookiejar.CookieJar()
_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))
_last = [0.0]


def post(data=None, ajax=False, tag=''):
    """GET (data=None) o POST a URL, con pausa >= 2 s y copia de la respuesta en .cache/atiliouy/."""
    wait = 2.0 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    h = {'User-Agent': UA}
    if ajax:
        h.update({'Faces-Request': 'partial/ajax', 'X-Requested-With': 'XMLHttpRequest',
                  'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
    body = urllib.parse.urlencode(data).encode() if data else None
    with _op.open(urllib.request.Request(URL, data=body, headers=h), timeout=90) as r:
        text = r.read().decode('utf-8', 'replace')
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f'goleadores_{tag or hashlib.sha1((body or b"")).hexdigest()[:10]}.html').write_text(text)
    return text


def parse_grid(text):
    """Devuelve [(id, 'Apellido, Nombre', goles)] de un fragmento de la grilla."""
    s = BeautifulSoup(text.replace('<![CDATA[', '').replace(']]>', ''), 'lxml')
    out = []
    for card in s.select('div.item-player'):
        a = card.find('a', href=re.compile(r'^/jugador:\d+$'))
        h4 = card.select_one('h4.h4-jugador')
        g = card.select_one('span.span-goleador')
        if not a or not h4 or not g or not g.get_text(strip=True).isdigit():
            continue
        pos = h4.select_one('span.span-posicion')
        if pos:
            pos.extract()
        out.append((int(a['href'].split(':')[1]), h4.get_text(' ', strip=True), int(g.get_text(strip=True))))
    return out


def display_name(lastfirst):
    if ',' in lastfirst:
        last, first = [x.strip() for x in lastfirst.split(',', 1)]
        return re.sub(r'\s+', ' ', f'{first} {last}').strip()
    return lastfirst.strip()


def main():
    html = post(tag='inicio')
    vs = re.search(r'name="javax.faces.ViewState"[^>]*value="([^"]+)"', html).group(1)
    s = BeautifulSoup(html, 'lxml')
    hasta = s.find(id='form:buttonfechaHasta_input')['value']
    desde = s.find(id='form:buttonfechaDesde_input')['value']
    # Casillas: j_idt210=Oficial (marcada), j_idt212=Amistoso (se desmarca), j_idt214=Entrenamiento (no),
    # j_idt226 marcada por defecto (se mantiene). Se comprueba que los ids sigan existiendo.
    for cid in ('form:j_idt210_input', 'form:j_idt212_input', 'form:j_idt226_input', 'form:j_idt230'):
        if not s.find(id=cid):
            sys.exit(f'La estructura del formulario cambió (falta {cid}); revisar el script.')
    labels = s.find(id='form:j_idt210_input').find_parent('div').find_parent('div').find_parent().get_text(' ', strip=True)
    if 'Oficial' not in labels:
        print('aviso: no se pudo verificar la etiqueta "Oficial" del filtro', file=sys.stderr)
    base = {'form': 'form', 'form:buttonfechaDesde_input': desde, 'form:buttonfechaHasta_input': hasta,
            'form:j_idt206_input': '', 'form:j_idt208_input': '', 'form:j_idt210_input': 'on',
            'form:pais_input': '', 'form:j_idt220_input': '', 'form:j_idt222_input': '',
            'form:j_idt226_input': 'on', 'form:jugadores_rppDD': str(ROWS), 'javax.faces.ViewState': vs}
    d = dict(base)
    d.update({'javax.faces.partial.ajax': 'true', 'javax.faces.source': 'form:j_idt230',
              'javax.faces.partial.execute': '@all', 'javax.faces.partial.render': 'form:contenido',
              'form:j_idt230': 'form:j_idt230'})
    x = post(d, ajax=True, tag='filtro_oficial')
    total = int(re.search(r'rowCount:(\d+)', x).group(1))
    m = re.search(r'javax.faces.ViewState[^>]*><!\[CDATA\[([^\]]+)\]\]>', x)
    if m:
        base['javax.faces.ViewState'] = m.group(1)
    found = {}
    first = 0
    while first < total:
        d = dict(base)
        d.update({'javax.faces.partial.ajax': 'true', 'javax.faces.source': 'form:jugadores',
                  'javax.faces.partial.execute': 'form:jugadores', 'javax.faces.partial.render': 'form:jugadores',
                  'javax.faces.behavior.event': 'page', 'javax.faces.partial.event': 'page',
                  'form:jugadores_pagination': 'true', 'form:jugadores_first': str(first),
                  'form:jugadores_rows': str(ROWS), 'form:jugadores_encodeFeature': 'true'})
        y = post(d, ajax=True, tag=f'oficial_desde_{first}')
        items = parse_grid(y)
        for pid, name, goals in items:
            found.setdefault(pid, (name, goals))
        print(f'filas {first}-{first + ROWS}: {len(items)} (acumulado {len(found)} de {total})', file=sys.stderr)
        if not items:
            break
        first += ROWS
    rows = []
    for pid, (name, goals) in found.items():
        if goals <= 0:
            continue
        rows.append({'equipo_id': 'nacional', 'jugador': display_name(name), 'goles': goals,
                     'alias': '', 'fuente': URL,
                     'fecha_dato': '', 'nota': NOTA})
    rows.sort(key=lambda r: (-r['goles'], r['jugador']))
    out = write_csv(ROOT / 'data' / 'sources' / 'atiliouy_sudamerica.csv', rows)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
