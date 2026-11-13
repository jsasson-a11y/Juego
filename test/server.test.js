'use strict';

// Prueba de punta a punta con dos clientes Socket.IO reales.
// OJO: usa datos de prueba (test/fixtures), NO datos reales.
const test = require('node:test');
const assert = require('node:assert');
const path = require('path');
const { io: ioc } = require('socket.io-client');
const { createServer } = require('../server/index');

const call = (s, ev, payload) => new Promise((res) => s.emit(ev, payload, res));
const nextState = (s, pred) => new Promise((res) => {
  const h = (st) => { if (pred(st)) { s.off('room:state', h); res(st); } };
  s.on('room:state', h);
});

test('dos jugadores juegan una partida online', async () => {
  const { server, rooms } = createServer({ dataDir: path.join(__dirname, 'fixtures'), options: { pickMs: 1500, revealMs: 200, minPlayers: 1, countdownMs: 300 } });
  await new Promise((r) => server.listen(0, r));
  const url = `http://localhost:${server.address().port}`;
  const c1 = ioc(url);
  const c2 = ioc(url);
  try {
    assert.deepEqual(await call(c1, 'room:create', { name: 'Ana' }), { ok: true });
    const code = [...rooms.keys()][0];
    assert.deepEqual(await call(c2, 'room:join', { code, name: 'Beto' }), { ok: true });
    assert.ok((await call(c2, 'room:join', { code: 'ZZZZ', name: 'X' })).error);
    assert.deepEqual(await call(c1, 'room:settings', { rounds: 4, target: 100 }), { ok: true });

    const picking = nextState(c2, (s) => s.phase === 'picking');
    assert.deepEqual(await call(c1, 'game:start', {}), { ok: true });
    const st = await picking;
    assert.equal(st.team.name, 'Equipo de Prueba');

    const r1 = await call(c1, 'pick:submit', { text: 'jugadr prueba' });
    assert.equal(r1.status, 'found');
    const r2 = await call(c2, 'pick:submit', { text: 'Jugador Prueba' });
    assert.equal(r2.status, 'taken');

    // Beto no responde: se termina el tiempo y Ana ya llegó a 0 (120 >= 100).
    const fin = await nextState(c2, (s) => s.phase === 'finished');
    assert.equal(fin.winners.length, 1);
    assert.equal(fin.players.find((p) => p.name === 'Ana').remaining, -20);
    assert.equal(fin.players.find((p) => p.name === 'Beto').remaining, 100);
  } finally {
    c1.close();
    c2.close();
    for (const r of rooms.values()) r.destroy();
    await new Promise((r) => server.close(r));
  }
});
