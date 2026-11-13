"""Muestra las tablas de una página que parecen tener nombre + goles, con su top 5.
    python3 scripts/inspect_page.py en "List of FC Barcelona players" ["otra página" ...]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki import read_tables, flat_cols, to_int, clean_name  # noqa: E402
from build_data import pick_cols  # noqa: E402

lang = sys.argv[1]
for title in sys.argv[2:]:
    try:
        tables, revid, real = read_tables(lang, title)
    except Exception as e:  # noqa: BLE001
        print(f'### {title}: ERROR {e}')
        continue
    print(f'### {real} (rev {revid}): {len(tables)} tablas')
    for i, t in enumerate(tables):
        if len(t) < 5:
            continue
        cols = flat_cols(t)
        n, g = pick_cols(cols)
        if not n or not g:
            continue
        t = t.copy()
        t.columns = cols
        rows = [(clean_name(r[n]), to_int(r[g])) for _, r in t.iterrows()]
        rows = [r for r in rows if r[1] is not None]
        top = sorted(rows, key=lambda x: -x[1])[:5]
        print(f'  [{i}] filas={len(t)} ({len(rows)} con goles) name="{n}" goals="{g}"')
        print(f'      cols={cols[:12]}')
        print('      top:', ', '.join(f'{a} {b}' for a, b in top))
