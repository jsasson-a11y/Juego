#!/usr/bin/env python3
"""Segunda fuente (independiente de Wikipedia) para los goles de las 13 selecciones.

Fuente: RSSSF, páginas "Record International Players" (índice:
https://rsssf.org/intlp-countrywise.html). Condiciones del sitio: no hay robots.txt
(404) y cada página dice "You are free to copy this document in whole or part
provided that proper acknowledgement is given to the author(s)/RSSSF".

Uso (desde la raíz del repo):
    python3 scripts/sources/rsssf_selecciones.py            # usa caché si existe
    python3 scripts/sources/rsssf_selecciones.py --refresh  # vuelve a descargar

Salida: data/sources/rsssf_selecciones.csv (UTF-8, ';')
    equipo_id;jugador;goles;alias;fuente;fecha_dato;nota

Reglas:
  * Solo se leen las secciones "Appearances" (#app), "Goalscoring" (#goals) y
    "Additional Players with Detailed Files" (#other) de cada página. No se leen
    las listas alternativas (p. ej. RDA "according to former GDR Federation",
    que incluyen partidos olímpicos) ni las de partidos oficiales/competitivos.
  * Un valor entre paréntesis como "(-69)" son goles recibidos por un portero:
    nunca se toman como goles marcados. Si en la fila no hay goles marcados, la
    fila se descarta (y se cuenta en el informe).
  * Si una fila no se puede interpretar con seguridad, se descarta y se cuenta.
  * Si un jugador aparece en "Appearances" y en "Goalscoring" con cifras
    distintas, se usa la de "Goalscoring" (lista específica de goleadores) y la
    otra se deja en la columna nota.
  * seleccion-alemania = (West) Germany/Germany + East Germany, sumando por
    jugador cuando jugó en ambas (nota "suma RFA+RDA").
  * El contenido descargado se trata como datos: solo se parsea texto, nunca se
    ejecuta nada.
"""
import argparse
import csv
import html
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '.cache' / 'rsssf'
OUT = ROOT / 'data' / 'sources' / 'rsssf_selecciones.csv'
UA = 'GoleadoresGame/1.0 (data build script)'
BASE = 'https://rsssf.org/miscellaneous/{}-recintlp.html'
MIN_INTERVAL = 2.0  # segundos entre pedidos al mismo sitio (mínimo exigido: 1.5)

# código de página RSSSF -> (equipo_id, estilo de nombres)
#   caps_only  : el nombre usado es lo que va en MAYÚSCULAS (Brasil)
#   caps_used  : ídem, pero si el nombre en mayúsculas no va primero se antepone el
#                primer nombre (España, Portugal: "Iker CASILLAS", "SERGIO RAMOS García")
#   given_caps : "Nombre(s) APELLIDO(S)"
#   given_caps1: ídem, pero se usa solo el primer apellido (Uruguay, Chile)
#   surname_first: "APELLIDO Nombre" (Francia, Italia)
#   mixed      : nombre normal sin mayúsculas (Inglaterra, Alemania, RDA)
PAGES = OrderedDict([
    ('uru', ('seleccion-uruguay', 'given_caps1')),
    ('arg', ('seleccion-argentina', 'given_caps')),
    ('braz', ('seleccion-brasil', 'caps_only')),
    ('span', ('seleccion-espana', 'caps_used')),
    ('eng', ('seleccion-inglaterra', 'mixed')),
    ('fran', ('seleccion-francia', 'surname_first')),
    ('duit', ('seleccion-alemania', 'mixed')),
    ('ddr', ('seleccion-alemania', 'mixed')),
    ('ital', ('seleccion-italia', 'surname_first')),
    ('port', ('seleccion-portugal', 'caps_used')),
    ('col', ('seleccion-colombia', 'given_caps')),
    ('chil', ('seleccion-chile', 'given_caps1')),
    ('belg', ('seleccion-belgica', 'given_caps')),
    ('ned', ('seleccion-paises-bajos', 'given_caps')),
])

# Correcciones SOLO del nombre visible (nunca de cifras), para casos en que la regla
# general da un nombre que no es el habitual. Clave: (código, nombre tal cual en la página).
NAME_OVERRIDES = {
    ('ital', 'JORGINHO Jorge Luiz Frello'): 'Jorginho',
    ('col', 'Radamel Falcao GARCÍA'): 'Radamel Falcao',
    ('fran', 'THURAM-Ulien Marcus'): 'Marcus Thuram',
    ('ital', 'EMERSON PALMIERI d. Santos'): 'Emerson Palmieri',
    ('braz', 'Antonio A. Ribeiro Reis "JUNINHO PERNAMB."'): 'Juninho Pernambucano',
}

PARTICLES = {'de', 'del', 'della', 'delle', 'dello', 'di', 'da', 'das', 'do', 'dos', 'du',
             'la', 'las', 'le', 'les', 'lo', 'los', 'van', 'von', 'der', 'den', 'ten',
             'ter', 'het', "'t", 'y', 'e', 'vom', 'zu', 'of'}

MONTHS = {m: i for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}

_last_request = [0.0]


# ----------------------------------------------------------------------------- descarga
def fetch(url, refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / url.rsplit('/', 1)[-1]
    if path.exists() and path.stat().st_size > 0 and not refresh:
        return path.read_bytes()
    wait = MIN_INTERVAL - (time.time() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.time()
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        # No se reintenta ni se intenta esquivar un bloqueo (403, captcha...).
        raise SystemExit(f'ERROR: {url} respondió HTTP {e.code}; se aborta sin reintentar.')
    path.write_bytes(data)
    return data


def decode(raw):
    text = raw.decode('cp1252', errors='replace')
    return text


def strip_tags(s):
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    s = s.replace('Ĳ', 'IJ').replace('ĳ', 'ij')  # ligadura holandesa Ĳ/ĳ
    s = s.replace('“', '"').replace('”', '"').replace('\xa0', ' ')
    return s


# ----------------------------------------------------------------------------- fechas
def parse_date(s):
    s = s.strip().rstrip('.')
    m = re.search(r'(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{4})', s)
    if m and m.group(2).lower() in MONTHS:
        return f'{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}'
    m = re.search(r'(\d{1,2})[-/.]\s?(\d{1,2})[-/.](\d{4})', s)
    if m:
        return f'{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'
    return None


def page_dates(text):
    """(fecha del último partido incluido, fecha de actualización) tal como dice la página."""
    last_match = updated = None
    m = re.search(r'Last match included:\s*([^\n<]+)', text)
    if m:
        last_match = parse_date(m.group(1))
    m = re.search(r'Last updated:\s*([^\n<]+)', text)
    if m:
        updated = parse_date(m.group(1))
    return last_match, updated


# ----------------------------------------------------------------------------- nombres
def is_caps(tok):
    letters = [c for c in tok if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters) and len(letters) >= 2


def is_initial(tok):
    return bool(re.fullmatch(r'[A-ZÀ-Þ]\.', tok))


def cap_word(w):
    """MAYÚSCULAS -> Capitalizado, respetando guiones y O'/D'."""
    def one(part):
        if not part:
            return part
        if re.fullmatch(r"[A-Za-z]'.+", part) and len(part) > 2:  # O'NEILL, D'ALESSANDRO
            return part[0].upper() + "'" + part[2:3].upper() + part[3:].lower()
        if part.startswith('IJ') and len(part) > 2:  # IJsselmeer
            return 'IJ' + part[2:].lower()
        return part[0].upper() + part[1:].lower()
    return '-'.join(one(p) for p in w.split('-'))


def fix_run(tokens, style):
    """Convierte una secuencia de palabras en mayúsculas (un apellido) a forma legible."""
    out = []
    for i, t in enumerate(tokens):
        low = t.lower()
        if low in PARTICLES and (style == 'ned' or i > 0):
            out.append(low)
        else:
            out.append(cap_word(t))
    return out


def readable(tokens, style):
    """Todas las palabras, con las de mayúsculas pasadas a forma legible."""
    out, run = [], []
    for t in tokens:
        if is_caps(t) or (t.lower() in PARTICLES and t.isupper()):
            run.append(t)
        else:
            if run:
                out += fix_run(run, style)
                run = []
            out.append(t)
    if run:
        out += fix_run(run, style)
    return ' '.join(out)


def caps_runs(tokens):
    """Índices de las palabras en mayúsculas (partículas en mayúsculas incluidas)."""
    return [i for i, t in enumerate(tokens) if is_caps(t) or (t.isupper() and t.lower() in PARTICLES
                                                              and len(t) >= 2)]


def split_nick(raw):
    m = re.search(r'"([^"]+)"', raw)
    if not m:
        return raw.split(), None, None
    before = raw[:m.start()].split()
    after = raw[m.end():].split()
    return before + after, m.group(1).split(), (len(before), len(after))


def make_name(raw, code, style):
    """Devuelve (jugador, [alias])."""
    raw = re.sub(r'\s+', ' ', raw).strip()
    raw = re.sub(r'^Dr\.\s+', '', raw)
    override = NAME_OVERRIDES.get((code, raw))
    raw = re.sub(r'\.(?=[^\s."])', '. ', raw)  # 'E.CHEVANTON' -> 'E. CHEVANTON'
    pstyle = 'ned' if code == 'ned' else style
    tokens, nick, pos = split_nick(raw)
    full = readable(tokens, pstyle)
    aliases = [full]
    nick_r = None
    if nick:
        nick_r = ' '.join(cap_word(t) if is_caps(t) else t for t in nick)

    if style == 'mixed':
        if nick:
            n_before, n_after = pos
            rest = tokens[n_before:]
            name = ' '.join([nick_r] + rest) if rest else nick_r
            if n_before and rest:
                aliases.append(' '.join([tokens[0]] + rest))
        else:
            name = full
            if len(tokens) >= 3:
                # "Harry Edward Kane" -> "Harry Kane"
                last = [tokens[-1]]
                if tokens[-2].lower() in PARTICLES:
                    last = [tokens[-2], tokens[-1]]
                short = ' '.join([tokens[0]] + last)
                if code == 'eng':  # Inglaterra pone segundos nombres solo a algunos jugadores
                    name = short
                else:
                    aliases.append(short)
    elif style == 'surname_first':
        caps = []
        i = 0
        while i < len(tokens) and (is_caps(tokens[i]) or tokens[i].lower() in PARTICLES):
            caps.append(tokens[i]); i += 1
        given = tokens[i:]
        surname = ' '.join(fix_run(caps, pstyle))
        if given:
            name = f'{given[0]} {surname}'
            full = ' '.join(given + [surname])
            aliases = [full]
        else:
            name = surname
            aliases = []
        if nick_r:
            name = nick_r
    else:
        idx = caps_runs(tokens)
        idx_noinit = [i for i in idx if not is_initial(tokens[i])]
        caps_words = fix_run([tokens[i] for i in idx_noinit], pstyle) if idx_noinit else []
        if style in ('caps_only', 'caps_used') and nick:
            # el apodo (y las otras palabras en mayúsculas) es el nombre usado
            n_before = pos[0]
            before_caps = [w for i, w in zip(idx_noinit, caps_words) if i < n_before]
            after_caps = [w for i, w in zip(idx_noinit, caps_words) if i >= n_before]
            name = ' '.join(before_caps + [nick_r] + after_caps)
        elif style == 'caps_only':
            name = ' '.join(caps_words) if caps_words else full
            if idx_noinit and idx_noinit[0] > 0:
                aliases.append(' '.join([tokens[0]] + caps_words))
        elif style == 'caps_used':
            n_real = sum(1 for w in caps_words if w.lower() not in PARTICLES)
            if not caps_words:
                name = full
            elif idx_noinit[0] == 0 or n_real >= 2:
                # 'SERGIO RAMOS García', 'José RUI Lopes ÁGUAS' -> 'Rui Águas'
                name = ' '.join(caps_words)
                if idx_noinit[0] > 0:
                    aliases.append(' '.join([tokens[0]] + caps_words))
            else:
                name = ' '.join([tokens[0]] + caps_words)
        else:  # given_caps / given_caps1
            if nick:
                n_before, n_after = pos
                after_caps = [w for i, w in zip(idx_noinit, caps_words) if i >= n_before]
                name = ' '.join([nick_r] + after_caps) if after_caps else nick_r
            if not caps_words:
                base = full
            else:
                sur = caps_words
                if style == 'given_caps1':
                    # primer apellido (con sus partículas iniciales: DE LOS SANTOS)
                    k = 0
                    while k < len(sur) - 1 and sur[k].lower() in PARTICLES:
                        k += 1
                    sur1 = sur[:k + 1]
                    if sur1 != sur:
                        aliases.append(' '.join(([tokens[0]] if idx_noinit[0] > 0 else []) + sur))
                    sur = sur1
                base = ' '.join(([tokens[0]] if idx_noinit[0] > 0 else []) + sur)
            if nick:
                aliases.append(base)
            else:
                name = base
    if override:
        aliases.append(name)
        name = override
    if nick_r and nick_r != name and all(is_caps(t) for t in nick):
        aliases.append(nick_r)  # apodo usado como nombre ('CALOMINO')
    seen, out = set(), []
    for a in aliases:
        a = a.strip()
        if a and a != name and a not in seen:
            seen.add(a)
            out.append(a)
    return name, out


def name_key(raw):
    s = re.sub(r'^Dr\.\s+', '', raw)
    s = s.replace('"', ' ')
    s = unicodedata.normalize('NFKD', s.casefold())
    s = ''.join(c for c in s if c.isalnum())
    return s


# ----------------------------------------------------------------------------- tablas
ANCHOR_RE = re.compile(r'<a\s+name="([^"]+)"', re.I)
PRE_RE = re.compile(r'<pre>(.*?)</pre>', re.I | re.S)
WANTED = ('app', 'goals', 'other')
YEARS_RE = re.compile(r'\b(\d{4})-(\d{4})\b')
DATE_RE = re.compile(r'\b(\d{1,2})[-/.]\s?(\d{1,2})[-/.](\d{2,4})\b')


def sections(raw_html):
    """[(nombre, texto del primer <pre> de la sección)] para #app, #goals y #other.
    Cada sección va desde su ancla hasta la siguiente ancla de sección (o 'about')."""
    anchors = [(m.start(), m.end(), m.group(1).lower()) for m in ANCHOR_RE.finditer(raw_html)
               if m.group(1).lower() in WANTED + ('1app', '1goals', 'about')]
    out = []
    for i, (a, b, name) in enumerate(anchors):
        if name not in WANTED:
            continue
        stop = anchors[i + 1][0] if i + 1 < len(anchors) else len(raw_html)
        m = PRE_RE.search(raw_html, b, stop)
        if m:
            out.append((name, m.group(1)))
    return out


def header_cols(line):
    """Orden de las columnas numéricas según la cabecera, p. ej. ['caps','goals']."""
    line = re.sub(r'\[[^\]]*\]', '', line)  # "[Olympic Goals Removal]" no es una columna
    cols = []
    for m in re.finditer(r'\b(Caps|App|Goals|Gls)\b', line):
        cols.append((m.start(), 'caps' if m.group(1) in ('Caps', 'App') else 'goals'))
    return [c for _, c in sorted(cols)]


def parse_line(line, cols):
    """Devuelve (dict, None) o (None, motivo). dict: name, caps, goals, first_year, last_year."""
    s = line.replace('\t', '    ').rstrip()
    s = re.sub(r'\[[^\]]*\]', '', s)  # [also played for ...] / [was 102; minus 4 matches]
    s = re.sub(r'^\s*\d+(?:\.\s*|\s+)', '', s)  # puesto ("1.", "100.", "20  ")
    m = re.match(r'\s*(.*?[^\s\d])\s+(?=\d|\(|\*|GK\b|K\b)(.*)$', s)
    if not m:
        return None, 'sin nombre/cifras reconocibles'
    name, rest = m.group(1).strip(), m.group(2)
    if re.search(r'\d', name):
        return None, 'nombre con dígitos'
    years = []
    ym = YEARS_RE.search(rest)
    if ym:
        years = [int(ym.group(1)), int(ym.group(2))]
    rest = YEARS_RE.sub(' ', rest)
    dates = tuple('%s-%s-%s' % (d[2], d[1].strip(), d[0]) for d in DATE_RE.findall(rest))
    if not years:
        years = [int(d[2]) for d in DATE_RE.findall(rest) if len(d[2]) == 4]
    rest = DATE_RE.sub(' ', rest)
    gk = None
    pm = re.search(r'\(\s*-?\s*(\d+)\s*\)', rest)
    if pm:
        gk = int(pm.group(1))
        rest = rest[:pm.start()] + ' ' + rest[pm.end():]
    rest = re.sub(r'(?<!\S)(\*|GK|K|[ACDHMS])(?!\S)', ' ', rest)
    toks = rest.split()
    if any(not t.isdigit() for t in toks):
        return None, f'texto no numérico en las cifras ({" ".join(toks)})'
    nums = [int(t) for t in toks]
    if len(nums) != len(cols):
        if gk is not None and len(nums) == len(cols) - 1 and 'goals' in cols:
            return None, 'portero: solo goles recibidos entre paréntesis, sin goles marcados'
        if len(nums) == len(cols) - 1 and cols and cols[-1] == 'goals':
            return None, 'columna de goles vacía'
        return None, f'{len(nums)} números para columnas {cols}'
    d = dict(zip(cols, nums))
    if not (0 <= d.get('goals', 0) <= 300) or not (0 <= d.get('caps', 0) <= 300):
        return None, 'cifra fuera de rango'
    return {'name': name, 'caps': d.get('caps'), 'goals': d.get('goals'),
            'first_year': years[0] if years else None,
            'last_year': years[-1] if years else None, 'dates': dates}, None


def looks_like_player_row(line):
    return bool(re.search(r'[A-Za-zÀ-ÿ]{2,}', line) and re.search(r'\d', line)
                and (YEARS_RE.search(line) or DATE_RE.search(line)))


def surname_words(raw):
    """Palabras normalizadas que probablemente son apellido (mayúsculas, o la última)."""
    toks = raw.replace('"', ' ').split()
    caps = [t for t in toks if is_caps(t)]
    words = caps or toks[-1:]
    return {name_key(w) for w in words if len(name_key(w)) > 2}


def given_words(raw):
    """Nombres de pila normalizados (lo que no está en mayúsculas; sin mayúsculas: todo menos
    la última palabra). 'Wash.Sebastián' -> ['wash', 'sebastian']."""
    toks = raw.replace('"', ' ').split()
    caps = [t for t in toks if is_caps(t)]
    given = [t for t in toks if not is_caps(t)] if caps else toks[:-1]
    out = []
    for t in given:
        out += [name_key(x) for x in t.split('.') if name_key(x)]
    return out


def given_compatible(a, b):
    ga, gb = given_words(a), given_words(b)
    if not ga or not gb:
        return False
    def ok(x, ys):
        n = min(3, len(x))
        return any(y[:n] == x[:n] for y in ys)
    return ok(ga[0], gb) or ok(gb[0], ga)


def find_same_player(players, rec):
    """Para una fila cuyo nombre no coincide exactamente (p. ej. 'José M. CÁCERES SILVA' frente
    a 'José Martín CÁCERES SILVA'): mismas fechas de primer y último partido, mismos partidos,
    algún apellido en común y nombre de pila compatible. Solo se acepta un candidato único."""
    if rec['caps'] is None or rec['first_year'] is None:
        return None
    sw = surname_words(rec['name'])
    cands = [k for k, p in players.items()
             if p['caps'] == rec['caps'] and p['first_year'] == rec['first_year']
             and p['last_year'] == rec['last_year'] and p['dates'] == rec['dates']
             and sw & surname_words(p['raw']) and given_compatible(rec['name'], p['raw'])]
    return cands[0] if len(cands) == 1 else None


def parse_page(code, raw_html):
    """Devuelve (filas, saltadas, fechas, fusiones). filas: OrderedDict key -> registro."""
    text_all = strip_tags(raw_html)
    last_match, updated = page_dates(text_all)
    players = OrderedDict()
    skipped, fuzzy = [], []
    secs = sections(raw_html)
    if not any(name == 'app' for name, _ in secs):
        raise SystemExit(f'ERROR: {code}: no se encontró la sección #app; el formato cambió.')
    app_cols = None
    for sec, body in secs:
        cols = None
        in_note = False
        for line in strip_tags(body).splitlines():
            if not line.strip():
                continue
            if cols is None:
                if re.search(r'\b(Caps|App|Goals|Gls)\b', line) and not re.search(r'\d', line):
                    cols = header_cols(line)
                    if sec == 'app':
                        app_cols = cols
                    continue
                if sec == 'other' and app_cols and looks_like_player_row(line):
                    cols = app_cols  # sección sin cabecera: mismas columnas que #app
                else:
                    continue
            if (re.match(r'\s*(Notes?|NB|N\.B\.)\b', line, re.I) or re.match(r'\s*\*\s+(still|ind)', line)
                    or re.match(r'\s*vs\s', line)):
                in_note = True  # texto de notas: se ignora hasta la siguiente fila de jugador válida
                continue
            if not looks_like_player_row(line):
                continue
            rec, why = parse_line(line, cols)
            if rec is None:
                if not in_note:
                    skipped.append((sec, line.strip(), why))
                continue
            in_note = False
            key = (name_key(rec['name']), rec['first_year'])
            if key not in players and sec != 'app':
                same = [k for k, p in players.items() if k[0] == key[0] and p['caps'] == rec['caps']
                        and rec['caps'] is not None and p['last_year'] == rec['last_year']]
                alt = same[0] if len(same) == 1 else find_same_player(players, rec)
                if alt is not None:
                    fuzzy.append((rec['name'], players[alt]['raw']))
                    key = alt
            p = players.get(key)
            if p is None:
                p = players[key] = {'raw': rec['name'], 'first_year': rec['first_year'],
                                    'last_year': rec['last_year'], 'dates': rec['dates'],
                                    'caps': None, 'goals_app': None,
                                    'goals_goals': None, 'goals_other': None, 'variants': []}
            if rec['name'] != p['raw'] and rec['name'] not in p['variants']:
                p['variants'].append(rec['name'])
            if rec['caps'] is not None and p['caps'] is None:
                p['caps'] = rec['caps']
            if rec['goals'] is not None:
                field = {'app': 'goals_app', 'goals': 'goals_goals', 'other': 'goals_other'}[sec]
                if p[field] is not None and p[field] != rec['goals']:
                    skipped.append((sec, line.strip(), 'fila duplicada con otra cifra'))
                    continue
                p[field] = rec['goals']
        if cols is None:
            raise SystemExit(f'ERROR: {code}: sección #{sec} sin cabecera reconocible.')
    return players, skipped, (last_match, updated), fuzzy


def resolve_goals(p):
    """(goles, nota) para un jugador según sus apariciones en las secciones."""
    vals = [(s, p[f]) for s, f in (('goals', 'goals_goals'), ('app', 'goals_app'),
                                   ('other', 'goals_other')) if p[f] is not None]
    if not vals:
        return None, None
    goals = vals[0][1]
    note = None
    distinct = {v for _, v in vals}
    if len(distinct) > 1:
        names = {'goals': 'lista de goleadores', 'app': 'lista de partidos', 'other': 'jugadores adicionales'}
        note = ('discrepancia en la página: ' +
                ', '.join(f'{names[s]} {v}' for s, v in vals) + f', se usa {goals}')
    return goals, note


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--refresh', action='store_true', help='volver a descargar aunque haya caché')
    args = ap.parse_args()

    rows = []
    report = OrderedDict()
    germany = {}
    for code, (team, style) in PAGES.items():
        url = BASE.format(code)
        raw = decode(fetch(url, args.refresh))
        players, skipped, (last_match, updated), fuzzy = parse_page(code, raw)
        fecha = last_match or updated
        page_note = None if last_match else (f"la página no indica 'Last match included', "
                                             f"fecha = 'Last updated' ({updated})")
        out = []
        for (k, fy), p in players.items():
            goals, note = resolve_goals(p)
            if goals is None:
                skipped.append(('-', p['raw'], 'sin goles en ninguna sección'))
                continue
            name, aliases = make_name(p['raw'], code, style)
            for v in p['variants']:  # otra grafía del mismo jugador en otra lista de la página
                vn, va = make_name(v, code, style)
                aliases += [a for a in [vn] + va if a != name and a not in aliases]
            notes = [n for n in (note, page_note) if n]
            if code == 'braz' and p['raw'].startswith(('Roberto RIVELLINO', 'Eduardo Gonçalves de Andrade')):
                notes.append('incluye 1 gol en Brasil-FIFA 1968, partido que la CBF mantiene como oficial')
            out.append({'equipo_id': team, 'jugador': name, 'goles': goals, 'alias': aliases,
                        'fuente': url, 'fecha_dato': fecha or '', 'nota': notes,
                        '_key': k, '_first': fy, '_raw': p['raw'], '_code': code})
        report[code] = {'team': team, 'url': url, 'last_match': last_match, 'updated': updated,
                        'rows': len(out), 'skipped': skipped, 'fuzzy': fuzzy}
        if team == 'seleccion-alemania':
            germany[code] = out
        else:
            rows += out

    # ---- Alemania: RFA/Alemania + RDA
    merged = []
    ddr_by_key = {}
    for r in germany['ddr']:
        ddr_by_key.setdefault(r['_key'], []).append(r)
    used_ddr = set()
    for r in germany['duit']:
        cands = ddr_by_key.get(r['_key'], [])
        # mismo nombre y carreras encadenadas (RDA hasta 1990, Alemania unificada desde 1990)
        cands = [c for c in cands if r['_first'] and r['_first'] >= 1990]
        if len(cands) == 1:
            c = cands[0]
            used_ddr.add(id(c))
            r = dict(r)
            r['nota'] = r['nota'] + [f'suma RFA+RDA: {r["goles"]} Alemania + {c["goles"]} RDA']
            r['goles'] = r['goles'] + c['goles']
            r['fuente'] = f'{r["fuente"]}|{c["fuente"]}'
            r['alias'] = r['alias'] + [a for a in [c['jugador']] + c['alias']
                                       if a not in r['alias'] and a != r['jugador']]
        merged.append(r)
    for c in germany['ddr']:
        if id(c) not in used_ddr:
            c = dict(c)
            c['nota'] = c['nota'] + ['RDA (Alemania Oriental), lista sin los 10 partidos olímpicos '
                                     'retirados por la FIFA en 1999']
            merged.append(c)
    rows += merged

    # ---- homónimos dentro de un mismo equipo
    cnt = Counter((r['equipo_id'], r['jugador']) for r in rows)
    for r in rows:
        if cnt[(r['equipo_id'], r['jugador'])] > 1:
            r['nota'].append(f'homónimo en la misma página, nombre completo: {r["_raw"]}'
                             + (f'; debut {r["_first"]}' if r['_first'] else ''))

    team_list = list(dict.fromkeys(t for t, _ in PAGES.values()))
    rows.sort(key=lambda r: (team_list.index(r['equipo_id']), -r['goles'], r['jugador']))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter=';', lineterminator='\n')
        w.writerow(['equipo_id', 'jugador', 'goles', 'alias', 'fuente', 'fecha_dato', 'nota'])
        for r in rows:
            w.writerow([r['equipo_id'], r['jugador'], r['goles'], '|'.join(r['alias']),
                        r['fuente'], r['fecha_dato'],
                        ' / '.join(n.replace(';', ',').replace('"', "'") for n in r['nota'])])

    # ---- informe
    print(f'Escrito {OUT.relative_to(ROOT)} ({len(rows)} filas)\n')
    for code, rep in report.items():
        print(f'[{code}] {rep["team"]}: {rep["rows"]} jugadores; último partido incluido: '
              f'{rep["last_match"]}; actualizado: {rep["updated"]}; saltadas: {len(rep["skipped"])}')
        for sec, line, why in rep['skipped']:
            print(f'    - ({sec}) {why}: {line}')
        for a, b in rep['fuzzy']:
            print(f'    = fusionado por partidos/años: "{a}" -> "{b}"')
    print()
    by_team = OrderedDict()
    for r in rows:
        by_team.setdefault(r['equipo_id'], []).append(r)
    for team, rs in by_team.items():
        top = ', '.join(f'{r["jugador"]} {r["goles"]}' for r in rs[:3])
        print(f'{team}: {len(rs)} filas; top 3: {top}')
    disc = [r for r in rows if any(n.startswith('discrepancia') for n in r['nota'])]
    print(f'\nDiscrepancias internas de la página: {len(disc)}')
    for r in disc:
        print(f'    {r["equipo_id"]}: {r["jugador"]}: {[n for n in r["nota"] if n.startswith("discrepancia")][0]}')


if __name__ == '__main__':
    main()
