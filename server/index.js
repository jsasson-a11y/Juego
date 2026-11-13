'use strict';

const path = require('path');
const http = require('http');
const express = require('express');
const { Server } = require('socket.io');
const { Room, DEFAULTS } = require('./game');
const { loadData } = require('./data');

function createServer({ dataDir, options } = {}) {
  const { teams, errors } = loadData(dataDir);
  for (const e of errors) console.warn('[datos]', e);
  const minPlayers = options?.minPlayers ?? DEFAULTS.minPlayers;
  const playable = teams.filter((t) => t.players.length > 0 && t.players.length >= minPlayers);
  console.log(`[datos] ${playable.length}/${teams.length} equipos en juego (mínimo ${minPlayers} jugadores cargados)`);

  const app = express();
  app.use(express.static(path.join(__dirname, '..', 'public')));
  app.get('/api/teams', (_req, res) => {
    res.json(teams.map((t) => ({
      id: t.id, name: t.name, country: t.country, league: t.league,
      players: t.players.length, playable: t.players.length > 0 && t.players.length >= minPlayers,
    })));
  });

  const server = http.createServer(app);
  const io = new Server(server);
  const rooms = new Map();

  const broadcast = (room) => {
    for (const p of room.players.values()) {
      if (p.socketId) io.to(p.socketId).emit('room:state', room.publicState(p.id));
    }
  };

  const newCode = () => {
    const letters = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
    let code;
    do code = Array.from({ length: 4 }, () => letters[Math.floor(Math.random() * letters.length)]).join('');
    while (rooms.has(code));
    return code;
  };

  io.on('connection', (socket) => {
    let room = null;
    let me = null;

    const attach = (r, p) => {
      room = r;
      me = p;
      p.socketId = socket.id;
      socket.emit('session', { code: r.code, token: p.token });
      broadcast(r);
    };

    socket.on('room:create', ({ name } = {}, ack = () => {}) => {
      const r = new Room({ code: newCode(), teams, options, onChange: broadcast });
      const res = r.addPlayer(name);
      if (res.error) return ack(res);
      rooms.set(r.code, r);
      attach(r, res.player);
      ack({ ok: true });
    });

    socket.on('room:join', ({ code, name } = {}, ack = () => {}) => {
      const r = rooms.get(String(code || '').trim().toUpperCase());
      if (!r) return ack({ error: 'No existe una sala con ese código.' });
      const res = r.addPlayer(name);
      if (res.error) return ack(res);
      attach(r, res.player);
      ack({ ok: true });
    });

    socket.on('room:resume', ({ code, token } = {}, ack = () => {}) => {
      const r = rooms.get(String(code || '').toUpperCase());
      const p = r && r.reconnect(token);
      if (!p) return ack({ error: 'La sesión anterior ya no existe.' });
      attach(r, p);
      ack({ ok: true });
    });

    const withRoom = (fn) => (payload = {}, ack = () => {}) => {
      if (!room || !me) return ack({ error: 'No estás en una sala.' });
      ack(fn(payload) || { ok: true });
    };

    socket.on('room:settings', withRoom((s) => room.updateSettings(me.id, s)));
    socket.on('game:start', withRoom(() => room.start(me.id)));
    socket.on('pick:submit', withRoom(({ text }) => room.submit(me.id, text)));

    socket.on('disconnect', () => {
      if (!room || !me || me.socketId !== socket.id) return;
      me.socketId = null;
      room.disconnect(me.id);
      if (room.isEmpty()) {
        const r = room;
        // Se da un margen para reconexiones (ej: recargar la página).
        setTimeout(() => { if (r.isEmpty()) { r.destroy(); rooms.delete(r.code); } }, 60_000).unref();
      }
    });
  });

  return { app, server, io, rooms, teams };
}

if (require.main === module) {
  const port = Number(process.env.PORT) || 3000;
  const options = process.env.MIN_PLAYERS ? { minPlayers: Number(process.env.MIN_PLAYERS) } : undefined;
  const { server } = createServer({ dataDir: process.env.DATA_DIR, options });
  server.listen(port, () => console.log(`Juego escuchando en http://localhost:${port}`));
}

module.exports = { createServer };
