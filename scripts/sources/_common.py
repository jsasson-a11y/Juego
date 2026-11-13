"""Shared helpers for the second-source extraction scripts (scripts/sources/*.py).

- Polite HTTP fetcher: honest User-Agent, robots.txt check, >=1.5 s between
  requests to the same host, raw responses cached under .cache/<site>/.
- CSV writer for data/sources/<site>_europa.csv with the agreed header.

Downloaded content is treated as untrusted data: it is only parsed, never
executed.
"""
import csv
import hashlib
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE_ROOT = os.path.join(REPO, ".cache")
OUT_DIR = os.path.join(REPO, "data", "sources")
UA = "GoleadoresGame/1.0 (data build script)"
MIN_DELAY = 2.0  # seconds between requests to the same host (>= 1.5 required)
HEADER = ["equipo_id", "jugador", "goles", "alias", "fuente", "fecha_dato", "nota"]


class Blocked(Exception):
    """Raised when robots.txt disallows a URL or the site refuses us."""


class Fetcher:
    def __init__(self, site, refresh=False):
        self.site = site
        self.cache_dir = os.path.join(CACHE_ROOT, site)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.refresh = refresh or os.environ.get("REFRESH") == "1"
        self._last = {}
        self._robots = {}

    def _cache_path(self, url):
        p = urllib.parse.urlsplit(url)
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", (p.path + ("_" + p.query if p.query else "")).strip("/"))[:120]
        h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
        return os.path.join(self.cache_dir, f"{slug or 'index'}_{h}.html")

    def _wait(self, host):
        last = self._last.get(host)
        if last is not None:
            dt = time.monotonic() - last
            if dt < MIN_DELAY:
                time.sleep(MIN_DELAY - dt)
        self._last[host] = time.monotonic()

    def _raw_get(self, url, timeout=60):
        host = urllib.parse.urlsplit(url).netloc
        self._wait(host)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,es;q=0.8"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()

    def allowed(self, url):
        p = urllib.parse.urlsplit(url)
        base = f"{p.scheme}://{p.netloc}"
        rp = self._robots.get(base)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                status, body = self._raw_get(base + "/robots.txt", timeout=30)
                rp.parse(body.decode("utf-8", "replace").splitlines())
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    rp.disallow_all = True
                else:  # 404 etc.: no robots.txt -> everything allowed
                    rp.allow_all = True
            except Exception:
                rp.allow_all = True
            self._robots[base] = rp
        return rp.can_fetch(UA, url)

    def get(self, url, encoding=None):
        path = self._cache_path(url)
        if os.path.exists(path) and not self.refresh:
            with open(path, "rb") as f:
                data = f.read()
        else:
            if not self.allowed(url):
                raise Blocked(f"robots.txt disallows {url}")
            try:
                status, data = self._raw_get(url)
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 429):
                    raise Blocked(f"HTTP {e.code} for {url}")
                raise
            with open(path, "wb") as f:
                f.write(data)
        if encoding:
            return data.decode(encoding, "replace")
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("cp1252", "replace")


def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def write_csv(site, rows):
    """rows: iterable of dicts with HEADER keys. Drops exact repeats; homonyms with different totals are kept."""
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{site}_europa.csv")
    seen = set()
    n = 0
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(HEADER)
        for r in rows:
            key = (r["equipo_id"], r["jugador"], str(r["goles"]))
            if key in seen:
                continue
            if (r["equipo_id"], r["jugador"]) in seen:
                print(f"warning: homonym kept twice: {r['equipo_id']} {r['jugador']}", file=sys.stderr)
            seen.add((r["equipo_id"], r["jugador"]))
            seen.add(key)
            w.writerow([clean(str(r.get(k) if r.get(k) is not None else "")).replace(";", ",") for k in HEADER])
            n += 1
    print(f"wrote {n} rows -> {os.path.relpath(out, REPO)}", file=sys.stderr)
    return out
