'use strict';

// Reconocimiento de nombres tolerante a tildes, mayúsculas y errores de tipeo
// (ej: "neimar" -> "Neymar", "suares" -> "Suárez").

const STOPWORDS = new Set(['de', 'da', 'do', 'dos', 'das', 'del', 'la', 'le', 'van', 'von', 'y', 'e', 'jr', 'junior']);

function strip(text) {
  return String(text || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/ß/g, 'ss')
    .replace(/ø/g, 'o')
    .replace(/æ/g, 'ae')
    .replace(/[^a-z0-9 ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

// Normalización "fonética" simple para español/portugués/italiano.
// Se aplica igual al texto ingresado y a los nombres de la base,
// así que solo importa que sea consistente.
function phonetic(word) {
  return word
    .replace(/ph/g, 'f')
    .replace(/sch/g, 'sh')
    .replace(/ll/g, 'y')
    .replace(/nh/g, 'ni')
    .replace(/lh/g, 'li')
    .replace(/g([ei])/g, 'j$1')
    .replace(/c([ei])/g, 's$1')
    .replace(/qu/g, 'k')
    .replace(/ck/g, 'k')
    .replace(/c/g, 'k')
    .replace(/h/g, '')
    .replace(/y/g, 'i')
    .replace(/v/g, 'b')
    .replace(/w/g, 'u')
    .replace(/z/g, 's')
    .replace(/(.)\1+/g, '$1');
}

function normalize(text) {
  return strip(text).split(' ').filter(Boolean).map(phonetic).join(' ');
}

function levenshtein(a, b) {
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
    }
    prev = cur;
  }
  return prev[b.length];
}

// Cuántos errores de tipeo se toleran según el largo de lo escrito.
function allowedDistance(len) {
  if (len <= 3) return 0;
  if (len <= 5) return 1;
  if (len <= 10) return 2;
  return 3;
}

// Claves por las que se puede encontrar a un jugador.
// "strong": nombre completo o alias. "weak": apellido suelto.
function buildKeys(player) {
  const strong = new Set();
  const weak = new Set();
  for (const raw of [player.name, ...(player.aliases || [])]) {
    const full = normalize(raw);
    if (!full) continue;
    strong.add(full);
    const all = full.split(' ');
    if (all.length > 1) {
      // Todos los "apellidos" posibles: "del piero", "piero"; "van basten", "basten".
      for (let i = 1; i < all.length; i++) {
        const tail = all.slice(i);
        if (tail.every((t) => STOPWORDS.has(t))) continue;
        const key = tail.join(' ');
        if (key.replace(/ /g, '').length >= 3 && !STOPWORDS.has(tail[tail.length - 1])) weak.add(key);
      }
      // Nombre de pila (ej: "Cristiano", "Zlatan"). Si lo comparten varios, se pide ser más específico.
      if (all[0].length >= 4 && !STOPWORDS.has(all[0])) weak.add(all[0]);
    }
  }
  for (const k of strong) weak.delete(k);
  return { strong: [...strong], weak: [...weak] };
}

function indexTeam(players) {
  return players.map((p, i) => ({ i, player: p, keys: buildKeys(p) }));
}

/**
 * Busca un jugador dentro de un equipo.
 * Devuelve { status: 'found', index } | { status: 'ambiguous' } | { status: 'notfound' }
 */
function findPlayer(index, input) {
  const q = normalize(input);
  if (!q) return { status: 'notfound' };

  // 1) Coincidencia exacta con nombre completo o alias.
  const strongHits = index.filter((e) => e.keys.strong.includes(q));
  if (strongHits.length === 1) return { status: 'found', index: strongHits[0].i };
  if (strongHits.length > 1) return { status: 'ambiguous' };

  // 2) Coincidencia exacta con apellido.
  const weakHits = index.filter((e) => e.keys.weak.includes(q));
  if (weakHits.length === 1) return { status: 'found', index: weakHits[0].i };
  if (weakHits.length > 1) return { status: 'ambiguous' };

  // 3) Coincidencia aproximada (errores de tipeo).
  const maxD = allowedDistance(q.replace(/ /g, '').length);
  if (maxD === 0) return { status: 'notfound' };
  let best = Infinity;
  let bestStrong = [];
  let bestAll = [];
  for (const e of index) {
    let dStrong = Infinity;
    for (const k of e.keys.strong) dStrong = Math.min(dStrong, levenshtein(q, k));
    let d = dStrong;
    for (const k of e.keys.weak) d = Math.min(d, levenshtein(q, k));
    if (d > maxD) continue;
    if (d < best) {
      best = d;
      bestAll = [e];
      bestStrong = dStrong === d ? [e] : [];
    } else if (d === best) {
      bestAll.push(e);
      if (dStrong === d) bestStrong.push(e);
    }
  }
  if (bestAll.length === 1) return { status: 'found', index: bestAll[0].i };
  if (bestStrong.length === 1) return { status: 'found', index: bestStrong[0].i };
  if (bestAll.length > 1) return { status: 'ambiguous' };
  return { status: 'notfound' };
}

module.exports = { strip, normalize, levenshtein, indexTeam, findPlayer };
