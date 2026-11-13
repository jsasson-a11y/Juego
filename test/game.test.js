'use strict';

// OJO: equipos y goles de este archivo son de prueba, NO datos reales.
const test = require('node:test');
const assert = require('node:assert');
const { Room } = require('../server/game');
const { indexTeam } = require('../server/matcher');

function makeTeam(id, players) {
  return { id, name: id, country: 'X', league: 'X', players, index: indexTeam(players) };
}

const teams = [
  makeTeam('equipo-a', [{ name: 'Jugador Uno', goals: 300 }, { name: 'Jugador Dos', goals: 200 }, { name: 'Otro Tres', goals: 50 }, { name: 'Pedro Pérez', goals: 10 }, { name: 'Juan Pérez', goals: 20 }]),
  makeTeam('equipo-b', [{ name: 'Jugador Uno', goals: 400 }, { name: 'Cuatro Cinco', goals: 900 }]),
  makeTeam('equipo-vacio', []),
];

function setup(target = 1000, rounds = 4) {
  const room = new Room({ code: 'TEST', teams, options: { pickMs: 60_000, revealMs: 60_000, minPlayers: 1, countdownMs: 0 }, random: () => 0 });
  const a = room.addPlayer('Ana').player;
  const b = room.addPlayer('Beto').player;
  assert.deepEqual(room.updateSettings(a.id, { rounds, target }), { ok: true });
  return { room, a, b };
}

test('validaciones de configuración', () => {
  const { room, a, b } = setup();
  assert.ok(room.updateSettings(a.id, { rounds: 3, target: 1000 }).error);
  assert.ok(room.updateSettings(a.id, { rounds: 9, target: 1000 }).error);
  assert.ok(room.updateSettings(b.id, { rounds: 5, target: 1000 }).error, 'solo el anfitrión');
  room.destroy();
});

test('ronda: resta goles, bloquea duplicados y no encontrados suman 0', () => {
  const { room, a, b } = setup();
  room.start(a.id);
  assert.equal(room.team.id, 'equipo-a', 'nunca sortea equipos sin datos');
  assert.equal(room.submit(a.id, 'jugador uno').status, 'found');
  const dup = room.submit(b.id, 'Jugador Uno');
  assert.equal(dup.status, 'taken');
  assert.equal(dup.retry, true);
  const nf = room.submit(b.id, 'Pelé');
  assert.equal(nf.status, 'notfound');
  assert.equal(nf.retry, true, 'si no está en la base puede volver a intentar');
  assert.equal(room.phase, 'picking');
  assert.equal(room.submit(b.id, 'Otro Tres').status, 'found');
  // Todos eligieron: la ronda termina sola.
  assert.equal(room.phase, 'reveal');
  assert.equal(room.players.get(a.id).remaining, 700);
  assert.equal(room.players.get(b.id).remaining, 950);
  room.destroy();
});

test('segundos por ronda configurables (solo valores permitidos)', () => {
  const { room, a } = setup();
  assert.ok(room.updateSettings(a.id, { rounds: 4, target: 1000, pickSeconds: 7 }).error);
  assert.deepEqual(room.updateSettings(a.id, { rounds: 4, target: 1000, pickSeconds: 30 }), { ok: true });
  assert.equal(room.settings.pickSeconds, 30);
  room.start(a.id);
  assert.equal(room.deadline - Date.now() > 29_000, true);
  room.destroy();
});

test('ambiguo permite reintentar', () => {
  const { room, a } = setup();
  room.start(a.id);
  const r = room.submit(a.id, 'perez');
  assert.equal(r.status, 'ambiguous');
  assert.equal(r.retry, true);
  assert.equal(room.submit(a.id, 'juan perez').status, 'found');
  assert.equal(room.players.get(a.id).remaining, 1000, 'se resta recién al cerrar la ronda');
  room.destroy();
});

test('llegar o pasarse de 0 gana', () => {
  const { room, a, b } = setup(250);
  room.start(a.id);
  room.submit(a.id, 'Jugador Uno'); // 300 > 250 => gana igual
  room.submit(b.id, 'Otro Tres');
  assert.equal(room.phase, 'finished');
  assert.deepEqual(room.winners, [a.id]);
  room.destroy();
});

test('sin respuesta al terminar el tiempo suma 0 y al final gana el más cercano', () => {
  const { room, a, b } = setup(5000, 4);
  room.start(a.id);
  for (let i = 0; i < 4; i++) {
    if (room.team.id === 'equipo-a' && i === 0) room.submit(a.id, 'Jugador Dos');
    room.endRound(); // simula fin del tiempo
    if (room.phase === 'reveal') room.nextRound();
  }
  assert.equal(room.phase, 'finished');
  assert.equal(room.players.get(b.id).remaining, 5000);
  assert.deepEqual(room.winners, [a.id]);
  room.destroy();
});

test('no sortea equipos con menos jugadores que el mínimo', () => {
  const room = new Room({ code: 'X', teams, options: { minPlayers: 4 } });
  assert.deepEqual(room.playableTeams().map((t) => t.id), ['equipo-a']);
});

test('no deja empezar sin datos', () => {
  const room = new Room({ code: 'X', teams: [makeTeam('vacio', [])] });
  const a = room.addPlayer('Ana').player;
  assert.ok(room.start(a.id).error);
});

test('las elecciones ajenas no se ven durante la ronda', () => {
  const { room, a, b } = setup();
  room.start(a.id);
  room.submit(a.id, 'Jugador Uno');
  const sb = room.publicState(b.id);
  assert.equal(sb.myPick, null);
  assert.equal(sb.players.find((p) => p.id === a.id).picked, true);
  assert.equal(JSON.stringify(sb).includes('Jugador Uno'), false);
  room.destroy();
});

test('cuenta regresiva: el equipo no se ve hasta que empieza la ronda', () => {
  const room = new Room({ code: 'C', teams, options: { minPlayers: 1, countdownMs: 60_000, pickMs: 60_000 }, random: () => 0 });
  const a = room.addPlayer('Ana').player;
  room.start(a.id);
  assert.equal(room.phase, 'countdown');
  assert.equal(room.publicState(a.id).team, null);
  assert.ok(room.submit(a.id, 'Jugador Uno').error, 'no se puede elegir durante la cuenta regresiva');
  room.startPicking();
  assert.equal(room.phase, 'picking');
  assert.equal(room.publicState(a.id).team.id, 'equipo-a');
  room.destroy();
});

test('pasar: suma 0 y cierra la ronda si todos eligieron', () => {
  const { room, a, b } = setup();
  room.start(a.id);
  assert.equal(room.pass(a.id).status, 'pass');
  assert.ok(room.pass(a.id).error, 'no puede pasar dos veces');
  assert.ok(room.submit(a.id, 'Jugador Uno').error, 'después de pasar no puede elegir');
  room.submit(b.id, 'Jugador Dos');
  assert.equal(room.phase, 'reveal');
  assert.equal(room.players.get(a.id).remaining, 1000);
  assert.equal(room.history[0].entries.find((e) => e.playerId === a.id).status, 'pass');
  room.destroy();
});
