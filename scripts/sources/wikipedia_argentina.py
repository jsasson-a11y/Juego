"""Goleadores de 6 clubes argentinos según anexos de Wikipedia en español (no los artículos principales,
que ya están en data/sources/wikipedia.csv).

Tablas usadas (sólo las que cuentan TODOS los partidos oficiales del club, o se marca lo contrario):
- Independiente, "Anexo:Goleadores del Club Atlético Independiente":
    · "Tabla histórica": ligas amateur y profesional + copas nacionales + internacionales (total).
    · "Jugadores extranjeros con más goles": 1.ª y 2.ª División + copas internacionales; la página aclara que
      las copas nacionales pueden estar incompletas -> se anota en `nota`.
- River Plate, "Anexo:Estadísticas del Club Atlético River Plate": "Máximos goleadores históricos" (top 10 en
  todas las competiciones) y "Extranjeros" (columna Total).
- San Lorenzo, "Anexo:Futbolistas del ..." y "Anexo:Estadísticas del Club Atlético San Lorenzo de Almagro":
  tablas de goleadores y de más partidos (partidos oficiales nacionales e internacionales). Se descartan filas
  cuyo "% de Gol" no coincide con goles/partidos (error evidente en la tabla).
- Rosario Central, "Anexo:Estadísticas de los futbolistas del Club Atlético Rosario Central" (todos los
  jugadores con partidos oficiales desde 1903; incluye la Liga Rosarina previa a la AFA; los marcados con *
  tienen datos incompletos antes de 1927) y la tabla de la era profesional de
  "Anexo:Estadísticas del Club Atlético Rosario Central".
- Estudiantes, "Anexo:Estadísticas del Club Estudiantes de La Plata (fútbol)": "Máximos goleadores".

Si un jugador aparece en varias tablas del mismo club se deja el valor más alto y se anotan los otros.
Se cita cada página con su revisión (oldid). Usa scripts/wiki.py (API de MediaWiki con caché en .cache/wiki).

Uso: python3 scripts/sources/wikipedia_argentina.py
Salida: data/sources/wikipedia_argentina.csv
"""
import io
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, write_csv  # noqa: E402
import wiki  # noqa: E402  (scripts/wiki.py)

MESES = {m: i for i, m in enumerate(['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
                                     'septiembre', 'octubre', 'noviembre', 'diciembre'], 1)}


def key(name):
    t = unicodedata.normalize('NFD', name)
    return re.sub(r'\s+', ' ', ''.join(c for c in t if unicodedata.category(c) != 'Mn').lower()).strip()


def to_int(v):
    s = str(v).strip()
    return int(float(s)) if re.fullmatch(r'\d+(\.0)?', s) else None


def date_in(text):
    m = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', text or '')
    if m and m.group(2).lower() in MESES:
        return f'{m.group(3)}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}'
    return ''


def clean_html(html):
    html = re.sub(r'<sup[^>]*class="[^"]*reference[^"]*"[^>]*>.*?</sup>', '', html, flags=re.S)
    html = re.sub(r'<span[^>]*style="display:\s*none[^"]*"[^>]*>.*?</span>', '', html, flags=re.S)
    return re.sub(r'<span[^>]*class="[^"]*sortkey[^"]*"[^>]*>.*?</span>', '', html, flags=re.S)


def sections(title):
    """[(encabezado, texto previo de la sección, DataFrame)] en orden del documento, más la URL citada."""
    html, revid, real = wiki.fetch_html('es', title)
    soup = BeautifulSoup(clean_html(html), 'lxml')
    out, head, intro = [], '', []
    for el in soup.find_all(['h2', 'h3', 'h4', 'p', 'table']):
        if el.name in ('h2', 'h3', 'h4'):
            head, intro = el.get_text(' ', strip=True), []
        elif el.name == 'p':
            intro.append(el.get_text(' ', strip=True))
        elif not el.find('table'):  # tablas "hoja" (algunas páginas anidan tablas en otra de diseño)
            try:
                df = pd.read_html(io.StringIO(str(el)))[0]
            except ValueError:
                continue
            out.append((head, ' '.join(intro), df))
    return out, wiki.page_url('es', real, revid)


def flat(df):
    """Columnas MultiIndex -> 'Nivel0|Nivel1' (sin repetir)."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = ['|'.join(dict.fromkeys(str(c) for c in col)) for col in df.columns]
    return df


def col(df, *needles):
    for c in df.columns:
        if all(n.lower() in str(c).lower() for n in needles):
            return c
    return None


class Collector:
    """Junta filas por (club, jugador); reconoce al mismo jugador por nombre o alias."""

    def __init__(self):
        self.best = {}
        self.names = defaultdict(set)   # clave canónica -> nombres conocidos (jugador y alias)
        self.index = {}                 # (club, nombre normalizado) -> clave canónica
        self.others = defaultdict(list)

    def add(self, team, jugador, goles, fuente, nota, alias='', fecha='', prio=1):
        """`prio`: ante empate de goles gana la tabla de mayor prioridad (p. ej. un total sobre una parcial)."""
        if goles is None or goles <= 0 or not jugador or jugador.lower() == 'nan':
            return
        known = [jugador] + [a for a in alias.split('|') if a]
        k = next((self.index[(team, key(n))] for n in known if (team, key(n)) in self.index), (team, key(jugador)))
        for n in known:
            self.index[(team, key(n))] = k
            self.names[k].add(n)
        row = {'equipo_id': team, 'jugador': jugador, 'goles': goles, 'fuente': fuente,
               'fecha_dato': fecha, 'nota': nota, '_prio': prio}
        cur = self.best.get(k)
        if cur is None or goles > cur['goles'] or (goles == cur['goles'] and prio > cur['_prio']):
            if cur:
                self.others[k].append(f"{cur['goles']} ({cur['nota'].split(';')[0]})")
            self.best[k] = row
        else:
            self.others[k].append(f'{goles} ({nota.split(";")[0]})')

    def rows(self):
        out = []
        for k, r in self.best.items():
            r = dict(r)
            r.pop('_prio', None)
            r['alias'] = '|'.join(sorted(n for n in self.names[k] if key(n) != key(r['jugador'])))
            vals = [v for v in self.others[k] if not v.startswith(f"{r['goles']} ")]
            if vals:
                r['nota'] += '; otras tablas de Wikipedia dan: ' + ', '.join(dict.fromkeys(vals))
            out.append(r)
        return sorted(out, key=lambda r: (r['equipo_id'], -r['goles'], r['jugador']))


def independiente(c):
    secs, url = sections('Anexo:Goleadores del Club Atlético Independiente')
    for head, intro, df in secs:
        df = flat(df)
        if head == 'Tabla histórica':
            for _, r in df.iterrows():
                tot = to_int(r[col(df, 'Totales')])
                comp = {n: to_int(r[col(df, n)]) for n in ('Ligas nacionales', 'Copas nacionales', 'Copas internacionales')}
                desc = ', '.join(f'{n.lower()} {v if v is not None else "sin dato"}' for n, v in comp.items())
                nota = ('total (ligas amateur y profesional + copas nacionales + copas internacionales) según la '
                        f'tabla «Tabla histórica»; componentes: {desc}')
                if tot is not None and all(v is not None for v in comp.values()) and sum(comp.values()) != tot:
                    nota += ' (los componentes no suman el total publicado)'
                c.add('independiente', str(r[col(df, 'Jugador')]).strip(), tot, url, nota, prio=2)
        elif head == 'Jugadores extranjeros con más goles':
            fecha = date_in(intro)
            for _, r in df.iterrows():
                c.add('independiente', str(r['Jugador']).strip(), to_int(r['Goles']), url,
                      'liga (1.ª y 2.ª División) + copas internacionales oficiales; según la página las copas '
                      f'nacionales pueden estar incompletas; tabla de extranjeros{" al " + fecha if fecha else ""}',
                      fecha=fecha)


def river(c):
    secs, url = sections('Anexo:Estadísticas del Club Atlético River Plate')
    for head, intro, df in secs:
        if head not in ('Máximos goleadores históricos', 'Extranjeros'):
            continue
        df = flat(df)
        tot, liga, copa, sud, otras = (col(df, 'Total', 'G.'), col(df, 'Liga', 'G.'), col(df, 'Copa', 'G.'),
                                       col(df, 'Sudamérica', 'G.'), col(df, 'Otras', 'G.'))
        if not tot or not col(df, 'Jugador'):
            continue
        for _, r in df.iterrows():
            comp = ', '.join(f'{n} {r[x]}' for n, x in (('liga', liga), ('copas', copa), ('sudamérica', sud),
                                                       ('otras', otras)) if x)
            what = 'top 10 histórico' if head.startswith('Máximos') else 'top 10 de extranjeros'
            c.add('river-plate', str(r[col(df, 'Jugador')]).strip(), to_int(r[tot]), url,
                  f'total en todas las competiciones oficiales ({what} del anexo); componentes: {comp}')


def san_lorenzo(c):
    for title in ('Anexo:Futbolistas del Club Atlético San Lorenzo de Almagro',
                  'Anexo:Estadísticas del Club Atlético San Lorenzo de Almagro'):
        secs, url = sections(title)
        for head, intro, df in secs:
            df = flat(df)
            name_c = col(df, 'Nombre') or col(df, 'Jugador')
            g_c, pj_c, pct_c = col(df, 'Goles'), col(df, 'Partidos'), col(df, '% de Gol')
            if not (name_c and g_c and pj_c):
                continue
            fecha = date_in(intro)
            for _, r in df.iterrows():
                g, pj = to_int(r[g_c]), to_int(r[pj_c])
                if g is None or pj is None:
                    continue
                if pct_c and to_int(r[pct_c]) is not None and abs(100 * g / pj - to_int(r[pct_c])) > 3:
                    print(f'San Lorenzo: se descarta {r[name_c]} {g} goles/{pj} PJ (% de gol {r[pct_c]} no cuadra)',
                          file=sys.stderr)
                    continue
                c.add('san-lorenzo', str(r[name_c]).strip(), g, url,
                      f'partidos oficiales nacionales e internacionales; tabla «{head}» ({pj} PJ)'
                      + (f'; actualizada al {fecha}' if fecha else ''), fecha=fecha)


def rc_names(raw):
    """'Ruben, Marco Gastón *' -> ('Marco Ruben', 'Marco Gastón Ruben')."""
    raw = raw.replace('*', '').strip()
    if ',' not in raw:
        return raw, ''
    last, first = [x.strip() for x in raw.split(',', 1)]
    full = f'{first} {last}'
    short = f'{first.split()[0]} {last}' if first else last
    return short, (full if full != short else '')


def rosario_central(c):
    secs, url = sections('Anexo:Estadísticas de los futbolistas del Club Atlético Rosario Central')
    tables = [df for _, _, df in secs if 'Futbolista' in df.columns and 'Goles' in df.columns]
    # Si dos jugadores distintos quedan con el mismo nombre corto, se usa el nombre completo.
    shorts = Counter(rc_names(str(n))[0] for df in tables for n in df['Futbolista'])
    for df in tables:
        for _, r in df.iterrows():
            raw = str(r['Futbolista'])
            jugador, alias = rc_names(raw)
            if shorts[jugador] > 1 and alias:
                jugador, alias = alias, ''
            nota = ('partidos oficiales desde 1903 (incluye la Liga Rosarina previa a la AFA, torneos de AFA, copas '
                    'nacionales e internacionales) según «Historia en Azul y Amarillo» (La Capital, hasta 2009-10) '
                    f'y Soccerway después; {r["PJ"]} PJ')
            if '*' in raw:
                nota += '; jugador anterior a 1927: la página aclara que no hay datos completos (puede tener más goles)'
            c.add('rosario-central', jugador, to_int(r['Goles']), url, nota, alias=alias)
    secs, url = sections('Anexo:Estadísticas del Club Atlético Rosario Central')
    for head, intro, df in secs:
        if 'Jugador' in df.columns and 'Goles' in df.columns and 'Temporadas' in df.columns:
            for _, r in df.iterrows():
                c.add('rosario-central', str(r['Jugador']).strip(), to_int(r['Goles']), url,
                      'goles en la era profesional de AFA (desde 1939), todas las competiciones; tabla '
                      f'«Máximos goleadores de la era profesional» ({r["Temporadas"]})')


def estudiantes(c):
    secs, url = sections('Anexo:Estadísticas del Club Estudiantes de La Plata (fútbol)')
    for head, intro, df in secs:
        if head == 'Máximos goleadores' and 'Jugador' in df.columns and 'Goles' in df.columns:
            for _, r in df.iterrows():
                c.add('estudiantes', str(r['Jugador']).strip(), to_int(r['Goles']), url,
                      'partidos oficiales (eras amateur y profesional) por Primera División, copas nacionales y '
                      'competencias internacionales; la página aclara que Pelegrina suma 14 más si se cuenta la '
                      'Segunda División 1954')


def main():
    c = Collector()
    for f in (independiente, river, san_lorenzo, rosario_central, estudiantes):
        f(c)
    rows = c.rows()
    out = write_csv(ROOT / 'data' / 'sources' / 'wikipedia_argentina.csv', rows)
    print(Counter(r['equipo_id'] for r in rows), file=sys.stderr)
    print(f'{len(rows)} filas -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
