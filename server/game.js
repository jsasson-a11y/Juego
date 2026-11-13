'use strict';

const crypto = require('crypto');
const { findPlayer } = require('./matcher');

const DEFAULTS = {
  pickMs: 10_000,     // tiempo para elegir jugador
  revealMs: 6_000,    // tiempo mostrando resultados de la ronda
  minRounds: 4,
  maxRounds: 8,
  defaultRounds: 4,
  defaultTarget: 1000,
  minPlayers: 1,      // mínimo de jugadores cargados para que un equipo se sortee (MIN_PLAYERS)
};

const MESSAGES = {
  found: (name, goals) => `${name}: ${goals} goles`,
  notfound: 'No está en la base de este equipo: suma 0',
  ambiguous: 'Hay más de un jugador con ese nombre. Sé más específico.',
  taken: (by) => `Ese jugador ya lo eligió ${by}. Probá con otro.`,
};

class Room {
  constructor({ code, teams, options = {}, random = Math.random, now = Date.now, onChange = () => {} }) {
    this.code = code;
    this.allTeams = teams;
    this.opts = { ...DEFAULTS, ...options };
    this.random = random;
    this.now = now;
    this.onChange = onChange;
    this.players = new Map(); // id -> { id, token, name, remaining, connected, picks: [] }
    this.hostId = null;
    this.settings = { rounds: this.opts.defaultRounds, target: this.opts.defaultTarget };
    this.phase = 'lobby'; // lobby | picking | reveal | finished
    this.round = 0;
    this.team = null;
    this.deadline = null;
    this.timer = null;
    this.usedTeams = new Set();
    this.taken = new Map(); // `${teamId}:${playerIndex}` -> nombre del participante
    this.roundPicks = new Map(); // participanteId -> resultado
    this.history = [];
    this.winners = [];
  }

  playableTeams() {
    return this.allTeams.filter((t) => t.players.length > 0 && t.players.length >= this.opts.minPlayers);
  }

  addPlayer(name) {
    if (this.phase !== 'lobby') return { error: 'La partida ya empezó.' };
    const clean = String(name || '').trim().slice(0, 20);
    if (!clean) return { error: 'Poné tu nombre.' };
    const same = [...this.players.values()].find((p) => p.name.toLowerCase() === clean.toLowerCase());
    if (same && same.connected) return { error: 'Ya hay alguien con ese nombre en la sala.' };
    if (same) this.players.delete(same.id);
    const id = crypto.randomUUID();
    if (this.hostId && !this.players.get(this.hostId)?.connected) this.hostId = null;
    const player = { id, token: crypto.randomUUID(), name: clean, remaining: this.settings.target, connected: true, picks: [] };
    this.players.set(id, player);
    if (!this.hostId) this.hostId = id;
    this.changed();
    return { player };
  }

  reconnect(token) {
    const p = [...this.players.values()].find((x) => x.token === token);
    if (!p) return null;
    p.connected = true;
    this.changed();
    return p;
  }

  disconnect(id) {
    const p = this.players.get(id);
    if (!p) return;
    p.connected = false;
    if (this.hostId === id) {
      const next = [...this.players.values()].find((x) => x.connected);
      this.hostId = next ? next.id : null;
    }
    this.changed();
    if (this.phase === 'picking') this.maybeEndRoundEarly();
  }

  isEmpty() {
    return ![...this.players.values()].some((p) => p.connected);
  }

  updateSettings(byId, { rounds, target }) {
    if (byId !== this.hostId) return { error: 'Solo el anfitrión puede cambiar la configuración.' };
    if (this.phase !== 'lobby' && this.phase !== 'finished') return { error: 'No se puede cambiar durante la partida.' };
    const r = Number(rounds);
    const t = Number(target);
    if (!Number.isInteger(r) || r < this.opts.minRounds || r > this.opts.maxRounds) {
      return { error: `Las rondas deben ser entre ${this.opts.minRounds} y ${this.opts.maxRounds}.` };
    }
    if (!Number.isInteger(t) || t < 1 || t > 99999) return { error: 'El objetivo de goles debe ser un número entre 1 y 99999.' };
    this.settings = { rounds: r, target: t };
    for (const p of this.players.values()) p.remaining = t;
    this.changed();
    return { ok: true };
  }

  start(byId) {
    if (byId !== this.hostId) return { error: 'Solo el anfitrión puede empezar.' };
    if (this.phase !== 'lobby' && this.phase !== 'finished') return { error: 'La partida ya está en curso.' };
    if (this.playableTeams().length === 0) return { error: 'No hay equipos con datos cargados todavía.' };
    for (const [id, p] of this.players) {
      if (!p.connected) this.players.delete(id);
      else { p.remaining = this.settings.target; p.picks = []; }
    }
    this.round = 0;
    this.usedTeams.clear();
    this.taken.clear();
    this.history = [];
    this.winners = [];
    this.nextRound();
    return { ok: true };
  }

  pickTeam() {
    const playable = this.playableTeams();
    let pool = playable.filter((t) => !this.usedTeams.has(t.id));
    if (pool.length === 0) { this.usedTeams.clear(); pool = playable; }
    const team = pool[Math.floor(this.random() * pool.length)];
    this.usedTeams.add(team.id);
    return team;
  }

  nextRound() {
    this.round += 1;
    this.team = this.pickTeam();
    this.roundPicks = new Map();
    this.phase = 'picking';
    this.deadline = this.now() + this.opts.pickMs;
    this.setTimer(this.opts.pickMs, () => this.endRound());
    this.changed();
  }

  submit(byId, text) {
    const p = this.players.get(byId);
    if (!p) return { error: 'No estás en la sala.' };
    if (this.phase !== 'picking') return { error: 'No es momento de elegir.' };
    if (this.now() > this.deadline) return { error: 'Se terminó el tiempo.' };
    if (this.roundPicks.has(byId)) return { error: 'Ya elegiste en esta ronda.' };
    const input = String(text || '').trim().slice(0, 60);
    if (!input) return { error: 'Escribí un nombre.' };

    const res = findPlayer(this.team.index, input);
    if (res.status === 'ambiguous') return { status: 'ambiguous', message: MESSAGES.ambiguous, retry: true };
    let result;
    if (res.status === 'notfound') {
      result = { status: 'notfound', input, goals: 0 };
    } else {
      const key = `${this.team.id}:${res.index}`;
      const holder = this.taken.get(key);
      const fp = this.team.players[res.index];
      if (holder) return { status: 'taken', message: MESSAGES.taken(holder), retry: true };
      this.taken.set(key, p.name);
      result = { status: 'found', input, footballer: fp.name, goals: fp.goals };
    }
    this.roundPicks.set(byId, result);
    this.changed();
    this.maybeEndRoundEarly();
    return {
      status: result.status,
      message: result.status === 'found' ? MESSAGES.found(result.footballer, result.goals) : MESSAGES.notfound,
      retry: false,
    };
  }

  maybeEndRoundEarly() {
    const active = [...this.players.values()].filter((p) => p.connected);
    if (active.length > 0 && active.every((p) => this.roundPicks.has(p.id))) this.endRound();
  }

  endRound() {
    if (this.phase !== 'picking') return;
    this.clearTimer();
    const entries = [];
    for (const p of this.players.values()) {
      const r = this.roundPicks.get(p.id) || { status: 'timeout', goals: 0 };
      p.remaining -= r.goals;
      p.picks.push({ round: this.round, team: this.team.name, ...r });
      entries.push({ playerId: p.id, name: p.name, ...r, remaining: p.remaining });
    }
    this.history.push({ round: this.round, team: this.team.name, entries });

    // Gana quien llega a 0 (o se pasa). Si varios llegan en la misma ronda, ganan todos.
    const reached = [...this.players.values()].filter((p) => p.remaining <= 0);
    if (reached.length > 0) return this.finish(reached);
    if (this.round >= this.settings.rounds) {
      // Se terminaron las rondas: gana quien quedó más cerca de 0.
      const min = Math.min(...[...this.players.values()].map((p) => p.remaining));
      return this.finish([...this.players.values()].filter((p) => p.remaining === min));
    }
    this.phase = 'reveal';
    this.deadline = this.now() + this.opts.revealMs;
    this.setTimer(this.opts.revealMs, () => this.nextRound());
    this.changed();
  }

  finish(winners) {
    this.clearTimer();
    this.phase = 'finished';
    this.deadline = null;
    this.winners = winners.map((p) => p.id);
    this.changed();
  }

  setTimer(ms, fn) {
    this.clearTimer();
    this.timer = setTimeout(fn, ms);
  }

  clearTimer() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  destroy() {
    this.clearTimer();
  }

  changed() {
    this.onChange(this);
  }

  // Estado visible para un participante. Durante la elección no se muestran las elecciones ajenas.
  publicState(forId) {
    const mine = this.roundPicks.get(forId);
    return {
      code: this.code,
      you: forId,
      hostId: this.hostId,
      settings: this.settings,
      limits: { minRounds: this.opts.minRounds, maxRounds: this.opts.maxRounds },
      phase: this.phase,
      round: this.round,
      team: this.team ? { name: this.team.name, country: this.team.country, league: this.team.league } : null,
      deadline: this.deadline,
      serverTime: this.now(),
      playableTeams: this.playableTeams().length,
      players: [...this.players.values()].map((p) => ({
        id: p.id,
        name: p.name,
        remaining: p.remaining,
        connected: p.connected,
        picked: this.phase === 'picking' ? this.roundPicks.has(p.id) : undefined,
      })),
      myPick: this.phase === 'picking' && mine ? mine : null,
      history: this.history,
      winners: this.winners,
    };
  }
}

module.exports = { Room, DEFAULTS };
