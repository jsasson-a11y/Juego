'use strict';

const fs = require('fs');
const path = require('path');
const { indexTeam } = require('./matcher');

// Parser CSV mínimo: soporta comillas y separador ";" o "," (se detecta por la cabecera).
function parseCsv(text) {
  const lines = text.replace(/^﻿/, '').split(/\r?\n/);
  const header = lines.find((l) => l.trim());
  if (!header) return [];
  const sep = header.split(';').length >= header.split(',').length ? ';' : ',';
  const parseLine = (line) => {
    const out = [];
    let cur = '';
    let quoted = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (quoted) {
        if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
        else if (ch === '"') quoted = false;
        else cur += ch;
      } else if (ch === '"') quoted = true;
      else if (ch === sep) { out.push(cur); cur = ''; }
      else cur += ch;
    }
    out.push(cur);
    return out.map((s) => s.trim());
  };
  const rows = [];
  const cols = parseLine(header);
  let lineNo = lines.indexOf(header) + 1;
  for (const line of lines.slice(lines.indexOf(header) + 1)) {
    lineNo++;
    if (!line.trim()) continue;
    const vals = parseLine(line);
    const row = { _line: lineNo };
    cols.forEach((c, i) => { row[c] = vals[i] ?? ''; });
    rows.push(row);
  }
  return rows;
}

/**
 * Carga equipos y goleadores. Devuelve { teams, errors }.
 * teams: [{ id, name, country, league, players: [{name, goals, aliases, source}], index }]
 */
function loadData(dir = path.join(__dirname, '..', 'data')) {
  const teams = JSON.parse(fs.readFileSync(path.join(dir, 'teams.json'), 'utf8'));
  const byId = new Map(teams.map((t) => [t.id, { ...t, players: [] }]));
  const errors = [];
  const csvPath = path.join(dir, 'goleadores.csv');
  const rows = fs.existsSync(csvPath) ? parseCsv(fs.readFileSync(csvPath, 'utf8')) : [];
  for (const r of rows) {
    const team = byId.get(r.equipo_id);
    const goals = Number(r.goles);
    if (!team) { errors.push(`Línea ${r._line}: equipo_id desconocido "${r.equipo_id}"`); continue; }
    if (!r.jugador) { errors.push(`Línea ${r._line}: falta el nombre del jugador`); continue; }
    if (!Number.isInteger(goals) || goals < 0) { errors.push(`Línea ${r._line}: goles inválidos "${r.goles}"`); continue; }
    if (team.players.some((p) => p.name === r.jugador)) { errors.push(`Línea ${r._line}: jugador repetido en ${team.id}: ${r.jugador}`); continue; }
    team.players.push({
      name: r.jugador,
      goals,
      aliases: (r.alias || '').split('|').map((s) => s.trim()).filter(Boolean),
      source: r.fuente || '',
    });
  }
  const list = [...byId.values()].map((t) => ({ ...t, index: indexTeam(t.players) }));
  return { teams: list, errors };
}

module.exports = { loadData, parseCsv };
