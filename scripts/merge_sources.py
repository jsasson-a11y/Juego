"""Combina todas las fuentes de data/sources/*.csv en data/goleadores.csv.

Reglas (decididas por el usuario):
- Si dos o más fuentes tienen al mismo jugador y los goles difieren, se usa el número MÁS ALTO.
- Si hay una sola fuente, se usa esa.
- Solo se usan goles totales: las filas marcadas "solo liga" en la columna nota se descartan.

Cada jugador queda con:
    validacion = coinciden | difieren | una_fuente
    detalle    = goles según cada fuente (ej: "wikipedia=69; rsssf_selecciones=58")

    python3 scripts/merge_sources.py [-v] [--only=wikipedia,rsssf_selecciones]
"""
import csv
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / 'data' / 'sources'
STOP = {'de', 'da', 'do', 'dos', 'das', 'del', 'la', 'le', 'van', 'von', 'der', 'den', 'y', 'e', 'jr', 'junior', 'filho', 'neto'}


def strip(text):
    t = unicodedata.normalize('NFD', str(text or ''))
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn').lower()
    t = t.replace('ß', 'ss').replace('ø', 'o').replace('æ', 'ae')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', t)).strip()


def phon(word):
    for a, b in [('ph', 'f'), ('sch', 'sh'), ('ll', 'y'), ('nh', 'ni'), ('lh', 'li')]:
        word = word.replace(a, b)
    word = re.sub(r'g([ei])', r'j\1', word)
    word = re.sub(r'c([ei])', r's\1', word)
    for a, b in [('qu', 'k'), ('ck', 'k'), ('c', 'k'), ('h', ''), ('y', 'i'), ('v', 'b'), ('w', 'u'), ('z', 's')]:
        word = word.replace(a, b)
    return re.sub(r'(.)\1+', r'\1', word)


def norm(text):
    return ' '.join(phon(w) for w in strip(text).split())


def tokens(text):
    return [t for t in norm(text).split() if t not in STOP]


def lev(a, b):
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class Player:
    def __init__(self, name, aliases):
        self.name = name
        self.aliases = set(a for a in aliases if a and a != name)
        self.values = {}   # fuente -> goles
        self.urls = {}

    def names(self):
        return [self.name, *self.aliases]

    def keys(self):
        return {norm(n) for n in self.names()}

    def token_sets(self):
        return [set(tokens(n)) for n in self.names() if tokens(n)]


NICK = [
    ('robert', 'bobby', 'bob', 'rob'), ('james', 'jimmy', 'jim'), ('nathaniel', 'nat'), ('stephen', 'steve', 'steven'),
    ('geoffrey', 'geoff'), ('ronald', 'ron', 'ronnie'), ('william', 'bill', 'billy', 'willie'), ('john', 'jack', 'johnny'),
    ('henry', 'harry'), ('edward', 'ted', 'teddy', 'eddie', 'ed'), ('thomas', 'tom', 'tommy'), ('richard', 'dick'),
    ('luigi', 'gigi'), ('alessandro', 'sandro'), ('josep', 'pep'), ('jose', 'pepe'), ('ignacio', 'nacho'), ('daniel', 'dani'),
    ('santiago', 'santi'), ('joseph', 'jef', 'jos', 'joe'), ('leopold', 'pol'), ('vincenzo', 'enzo'), ('maximiliano', 'maxi'),
    ('francisco', 'paco', 'pancho', 'fran'), ('johannes', 'hannes', 'hans'), ('alexander', 'alex', 'sasha'), ('gustavo', 'gus'),
    ('jerrel', 'jimmy'), ('michael', 'mike', 'mick'), ('anthony', 'tony'), ('frederick', 'fred', 'freddie'),
]
NICK_MAP = {}
for group in NICK:
    for n in group:
        NICK_MAP.setdefault(phon(n), set()).update(phon(x) for x in group)


def first_compatible(a, b):
    if not a or not b:
        return False
    if a.startswith(b) or b.startswith(a) or (min(len(a), len(b)) >= 4 and lev(a, b) <= 1):
        return True
    return b in NICK_MAP.get(a, ())


def surname_match(players, name, goals):
    """Último recurso: mismo apellido y (nombre de pila compatible, o goles casi iguales (diferencia <= 2) con la misma inicial o un nombre de una sola palabra).
    Solo si hay un único candidato entre los jugadores que esta fuente todavía no tiene."""
    tk = tokens(name)
    if not tk:
        return None
    cands = []
    for p in players:
        for n in p.names():
            pt = tokens(n)
            if not pt or pt[-1] != tk[-1]:
                continue
            close = goals is not None and goals > 0 and any(v > 0 and abs(v - goals) <= 2 for v in p.values.values())
            both_full = len(pt) > 1 and len(tk) > 1
            same_initial = pt[0][:1] == tk[0][:1]
            if (both_full and first_compatible(pt[0], tk[0])) or (close and (not both_full or same_initial)):
                cands.append(p)
                break
    cands = list(dict.fromkeys(cands))
    return cands[0] if len(cands) == 1 else None


def find_match(players, name, aliases, source=None, goals=None):
    """Busca el jugador ya cargado que corresponde a (name, aliases). Devuelve (player | None, motivo).
    Dentro de una misma fuente solo se combina con el mismo nombre exacto (son personas distintas)."""
    same = [p for p in players if p.name == name and source in p.values]
    if same:
        return same[0], 'mismo'
    players = [p for p in players if source not in p.values]
    keys = {norm(n) for n in [name, *aliases] if n}
    exact = [p for p in players if p.keys() & keys]
    if len(exact) == 1:
        return exact[0], 'exacto'
    if len(exact) > 1:
        return None, 'ambiguo'
    # Subconjunto de tokens con el mismo apellido (ej: "Luis Suárez" ⊂ "Luis Alberto Suárez Díaz").
    cand_sets = [set(tokens(n)) for n in [name, *aliases] if tokens(n)]

    def plausible(p, shared):
        # Evita unir personas distintas que comparten dos palabras (ej: "Antônio Carlos" vs "Antonio Carlos Cerezo"):
        # con solo 2 palabras en común, los goles deben ser parecidos.
        if shared >= 3 or goals is None:
            return True
        vals = list(p.values.values())
        return any(abs(v - goals) <= max(3, 0.25 * max(v, goals)) for v in vals)

    sub = []
    for p in players:
        for a in p.token_sets():
            for b in cand_sets:
                if len(a) >= 2 and len(b) >= 2 and (a <= b or b <= a) and plausible(p, min(len(a), len(b))):
                    sub.append(p)
                    break
            else:
                continue
            break
    sub = list(dict.fromkeys(sub))
    if len(sub) == 1:
        return sub[0], 'tokens'
    if len(sub) > 1:
        return None, 'ambiguo'
    # Error de tipeo en nombre completo largo.
    k = norm(name)
    if len(k) >= 8:
        fuzzy = [p for p in players if any(lev(k, pk) <= 1 for pk in p.keys())]
        if len(fuzzy) == 1:
            return fuzzy[0], 'fuzzy'
        if len(fuzzy) > 1:
            return None, 'ambiguo'
    p = surname_match(players, name, goals)
    if p:
        return p, 'apellido'
    return None, 'nuevo'


def clean_display(name):
    """Quita marcas como "(II)" o "IIº" (hermanos/homónimos numerados) y espacios sobrantes."""
    name = re.sub(r'\(\s*[IVX]+\s*\)|\b[IVX]+º|\(detto [^)]*\)', ' ', str(name or ''))
    return re.sub(r'\s+', ' ', name).strip()


def load_sources():
    files = sorted(SRC_DIR.glob('*.csv'), key=lambda p: (p.stem != 'wikipedia', p.stem))
    only = next((a.split('=', 1)[1].split(',') for a in sys.argv if a.startswith('--only=')), None)
    if only:
        files = [f for f in files if f.stem in only]
    out = []
    for f in files:
        with open(f, encoding='utf-8') as fh:
            rows = list(csv.DictReader(fh, delimiter=';'))
        out.append((f.stem, rows))
    return out


def main():
    teams = {}
    log = defaultdict(list)
    skipped_league = defaultdict(int)
    for source, rows in load_sources():
        for r in rows:
            tid = (r.get('equipo_id') or '').strip()
            name = clean_display(r.get('jugador'))
            try:
                goals = int(str(r.get('goles', '')).strip())
            except ValueError:
                log[tid].append(f'{source}: goles inválidos para "{name}": {r.get("goles")!r}')
                continue
            if not tid or not name:
                continue
            if 'solo liga' in (r.get('nota') or '').lower():
                skipped_league[(tid, source)] += 1
                continue
            aliases = [a.strip() for a in (r.get('alias') or '').split('|') if a.strip()]
            players = teams.setdefault(tid, [])
            p, how = find_match(players, name, aliases, source, goals)
            if how == 'ambiguo':
                log[tid].append(f'{source}: "{name}" coincide con más de un jugador; no se combinó')
                continue
            if how in ('apellido', 'fuzzy', 'tokens') and p is not None:
                log[tid].append(f'{source}: "{name}" ({goals}) combinado con "{p.name}" {p.values} por {how}')
            if p is None:
                p = Player(name, aliases)
                players.append(p)
            else:
                p.aliases |= set(a for a in [name, *aliases] if a != p.name)
            # Misma fuente con el mismo jugador dos veces: se queda el mayor.
            p.values[source] = max(goals, p.values.get(source, -1))
            p.urls[source] = r.get('fuente', '')

    out = []
    summary = []
    for tid, players in teams.items():
        counts = defaultdict(int)
        for p in players:
            vals = p.values
            best_src = max(vals, key=lambda s: vals[s])
            if len(vals) == 1:
                status = 'una_fuente'
            elif len(set(vals.values())) == 1:
                status = 'coinciden'
            else:
                status = 'difieren'
            counts[status] += 1
            out.append({
                'equipo_id': tid, 'jugador': p.name, 'goles': vals[best_src],
                'alias': '|'.join(sorted(p.aliases)), 'fuente': p.urls[best_src],
                'validacion': status, 'detalle': ', '.join(f'{s}={v}' for s, v in sorted(vals.items())),
            })
        summary.append((tid, len(players), dict(counts)))

    with open(ROOT / 'data' / 'goleadores.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['equipo_id', 'jugador', 'goles', 'alias', 'fuente', 'validacion', 'detalle'], delimiter=';')
        w.writeheader()
        w.writerows(out)

    for tid, n, c in sorted(summary):
        print(f'{tid:24} {n:5}  coinciden={c.get("coinciden", 0):4}  difieren={c.get("difieren", 0):4}  una_fuente={c.get("una_fuente", 0):5}')
    for (tid, src), n in sorted(skipped_league.items()):
        print(f'  descartadas por "solo liga": {tid} / {src}: {n}')
    if '-v' in sys.argv:
        for tid, msgs in log.items():
            for m in msgs:
                print(f'  [{tid}] {m}')
    else:
        print(f'  avisos de combinación: {sum(len(v) for v in log.values())} (ver con -v)')
    print(f'Escrito data/goleadores.csv con {len(out)} filas')


if __name__ == '__main__':
    main()
