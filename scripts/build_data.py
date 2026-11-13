"""Genera data/goleadores.csv a partir de las páginas de Wikipedia listadas en scripts/sources.json.

    python3 scripts/build_data.py              # todos los equipos -> escribe data/goleadores.csv
    python3 scripts/build_data.py arsenal ...  # solo algunos (para revisar), no escribe el CSV

Cada fuente admite:
    lang, title          página de Wikipedia
    tables               índices de tablas a usar (si falta: detección automática)
    name_col, goals_col  columnas a usar (si faltan: se detectan)
    goals_sum_re         suma todas las columnas cuyo nombre cumple esta regex (ej: goles por competición)
    goals_after_slash    la celda viene como "partidos/goles" -> toma lo que está después de "/"
"""
import csv
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki import read_tables, flat_cols, to_int, split_name, page_url  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r'^(name|player|players|jugador|jugadores|nombre|futbolista|nome|jogador|atleta|spieler|joueur|nom|giocatore)$', re.I)
GOALS_RE = re.compile(r'\b(goals|goles|gols|golos|tore|buts|gol|goal|reti|g)\b', re.I)
APPS_RE = re.compile(r'\b(apps|appearances|partidos|jogos|pj|matches|caps|pld|partite|spiele|m)\b', re.I)


def pick_cols(cols):
    name = next((c for c in cols if NAME_RE.match(c.split(' / ')[-1].strip())), None)
    goal_cols = [c for c in cols if GOALS_RE.search(c) and not APPS_RE.search(c.split(' / ')[-1])]
    goals = None
    if len(goal_cols) == 1:
        goals = goal_cols[0]
    elif goal_cols:
        tot = [c for c in goal_cols if re.search(r'total', c, re.I)]
        goals = tot[-1] if tot else None
    return name, goals


def regroup(t):
    """Tablas con columnas numéricas y la cabecera repetida en bloques (ej: 3 rankings lado a lado)."""
    for r in range(min(4, len(t))):
        row = [str(x).strip() for x in t.iloc[r].tolist()]
        starts = [i for i, x in enumerate(row) if NAME_RE.match(x)]
        if not starts:
            continue
        size = starts[1] - starts[0] if len(starts) > 1 else len(row)
        offset = starts[0] - (starts[0] % size) if size else 0
        parts = []
        for s in range(offset, len(row), size):
            block = t.iloc[r + 1:, s:s + size].copy()
            hdr = row[s:s + size]
            if len(hdr) < size:
                continue
            block.columns = hdr
            parts.append(block)
        if parts:
            return pd.concat(parts, ignore_index=True)
    return None


def extract(src):
    tables, revid, title = read_tables(src['lang'], src['title'])
    url = page_url(src['lang'], title, revid)
    rows, used = [], []
    idxs = src.get('tables') or range(len(tables))
    for i in idxs:
        t = tables[i]
        if len(t) < src.get('min_rows', 3):
            continue
        cols = flat_cols(t)
        t = t.copy()
        t.columns = cols
        if all(re.fullmatch(r'\d+', c) for c in cols):
            g = regroup(t)
            if g is None:
                continue
            t = g
            cols = list(t.columns)
        name_c, goals_c = pick_cols(cols)
        if 'tables' not in src:
            # Modo automático: solo tablas tipo "plantel histórico" (con partidos jugados),
            # descartando tablas de selección (caps) o por temporada.
            if not any(APPS_RE.search(c) for c in cols) or any(re.search(r'caps|season|temporada|year', c, re.I) for c in cols):
                continue
        name_c = src.get('name_col', name_c)
        sum_cols = [c for c in cols if re.search(src['goals_sum_re'], c)] if src.get('goals_sum_re') else None
        goals_c = src.get('goals_col', goals_c)
        if not name_c or name_c not in cols or not (sum_cols or (goals_c and goals_c in cols)):
            continue
        used.append(f'[{i}] {name_c} | {"+".join(sum_cols) if sum_cols else goals_c}')
        for _, r in t.iterrows():
            name, aliases = split_name(r[name_c])
            if sum_cols:
                vals = [to_int(r[c]) for c in sum_cols]
                goals = sum(v for v in vals if v is not None) if any(v is not None for v in vals) else None
            elif src.get('goals_after_slash'):
                cell = str(r[goals_c])
                goals = to_int(cell.split('/')[-1]) if '/' in cell else None
            else:
                goals = to_int(r[goals_c])
            if not name or name.lower() in ('nan', 'total', 'totals', 'totales') or goals is None:
                continue
            if re.fullmatch(r'[\d\sº°.#-]+', name):
                continue
            rows.append((name, goals, aliases))
    return rows, used, url


def build(team_ids=None):
    sources = json.loads((ROOT / 'scripts' / 'sources.json').read_text())
    teams = json.loads((ROOT / 'data' / 'teams.json').read_text())
    out, report = [], []
    for team in teams:
        tid = team['id']
        if team_ids and tid not in team_ids:
            continue
        merged = {}
        notes = []
        for src in sources.get(tid, []):
            try:
                rows, used, url = extract(src)
            except Exception as e:  # noqa: BLE001
                notes.append(f'ERROR {src["title"]}: {e}')
                continue
            notes.append(f'{src["lang"]}:{src["title"]}: {len(rows)} filas {used}')
            for name, goals, aliases in rows:
                if name in merged and src.get('combine') == 'sum':
                    # Ej: goles con Alemania Oriental se suman a los de Alemania.
                    merged[name]['goles'] += goals
                    merged[name]['alias'] |= set(aliases)
                    notes.append(f'  sumado "{name}": +{goals}')
                    continue
                if name in merged:
                    prev = merged[name]
                    if prev['goles'] != goals:
                        notes.append(f'  repetido "{name}": {prev["goles"]} vs {goals} -> se toma el mayor')
                    prev['alias'] |= set(aliases)
                    if goals <= prev['goles']:
                        continue
                    prev.update(goles=goals, fuente=url)
                else:
                    merged[name] = {'goles': goals, 'alias': set(aliases), 'fuente': url}
        for name, d in merged.items():
            out.append({'equipo_id': tid, 'jugador': name, 'goles': d['goles'],
                        'alias': '|'.join(sorted(d['alias'])), 'fuente': d['fuente']})
        top = sorted(merged.items(), key=lambda kv: -kv[1]['goles'])[:5]
        report.append((tid, len(merged), top, notes))
    return out, report


def main():
    ids = [a for a in sys.argv[1:] if not a.startswith('-')]
    out, report = build(ids or None)
    for tid, n, top, notes in report:
        print(f'\n== {tid}: {n} jugadores')
        for note in notes:
            if not note.startswith('  ') or '-v' in sys.argv:
                print('   ', note)
        print('    top:', ', '.join(f'{k} {v["goles"]}' for k, v in top))
    if not ids:
        with open(ROOT / 'data' / 'goleadores.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['equipo_id', 'jugador', 'goles', 'alias', 'fuente'], delimiter=';')
            w.writeheader()
            w.writerows(out)
        print(f'\nEscrito data/goleadores.csv con {len(out)} filas')


if __name__ == '__main__':
    main()
