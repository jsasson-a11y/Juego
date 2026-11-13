'use strict';

const socket = io();
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const SESSION_KEY = 'goleadores-session';

let state = null;
let clockOffset = 0;
let lastRoundShown = 0;

const store = {
  get() { try { return JSON.parse(sessionStorage.getItem(SESSION_KEY)); } catch { return null; } },
  set(v) { try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(v)); } catch { /* sin storage */ } },
  clear() { try { sessionStorage.removeItem(SESSION_KEY); } catch { /* sin storage */ } },
};

function show(screen) {
  for (const s of ['home', 'lobby', 'game', 'final']) $(`screen-${s}`).classList.toggle('hidden', s !== screen);
}

// --- Inicio ---
fetch('/api/teams').then((r) => r.json()).then((teams) => {
  const loaded = teams.filter((t) => t.players > 0).length;
  $('data-status').textContent = `Equipos con datos cargados: ${loaded} de ${teams.length}.`;
}).catch(() => {});

$('btn-create').onclick = () => {
  socket.emit('room:create', { name: $('home-name').value }, (res) => { if (res.error) $('home-error').textContent = res.error; });
};
$('btn-join').onclick = () => {
  socket.emit('room:join', { name: $('home-name').value, code: $('home-code').value }, (res) => { if (res.error) $('home-error').textContent = res.error; });
};
$('home-code').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('btn-join').click(); });

socket.on('connect', () => {
  const s = store.get();
  if (s) socket.emit('room:resume', s, (res) => { if (res.error) { store.clear(); show('home'); } });
});
socket.on('session', (s) => store.set(s));

// --- Sala ---
const rounds = $('set-rounds');
const sendSettings = () => {
  socket.emit('room:settings', { rounds: Number(rounds.value), target: Number($('set-target').value) }, (res) => {
    $('lobby-error').textContent = res.error || '';
  });
};
rounds.onchange = sendSettings;
$('set-target').onchange = sendSettings;
$('btn-start').onclick = () => socket.emit('game:start', {}, (res) => { $('lobby-error').textContent = res.error || ''; });
$('btn-again').onclick = () => socket.emit('game:start', {}, (res) => { $('final-error').textContent = res.error || ''; });

// --- Juego ---
$('pick-form').onsubmit = (e) => {
  e.preventDefault();
  const text = $('pick-input').value.trim();
  if (!text) return;
  socket.emit('pick:submit', { text }, (res) => {
    const msg = $('pick-msg');
    if (res.error) { msg.textContent = res.error; msg.className = 'msg bad'; return; }
    msg.textContent = res.message;
    msg.className = `msg ${res.status === 'found' ? 'ok' : res.retry ? 'warn' : 'bad'}`;
    if (res.retry) { $('pick-input').select(); return; }
    $('pick-input').disabled = true;
  });
};

function playerList(el, players, { showPicked = false, winners = [] } = {}) {
  el.innerHTML = [...players]
    .sort((a, b) => (state.phase === 'lobby' ? 0 : a.remaining - b.remaining))
    .map((p) => {
      const tags = [];
      if (p.id === state.you) tags.push('vos');
      if (p.id === state.hostId) tags.push('anfitrión');
      if (!p.connected) tags.push('desconectado');
      if (showPicked && p.picked) tags.push('✔ eligió');
      const right = state.phase === 'lobby' ? '' : `<span class="num">${p.remaining}</span>`;
      const cls = [p.connected ? '' : 'off', winners.includes(p.id) ? 'winner' : ''].join(' ');
      return `<li class="${cls}"><span>${winners.includes(p.id) ? '🏆 ' : ''}${esc(p.name)}<span class="tag">${tags.join(' · ')}</span></span>${right}</li>`;
    }).join('');
}

function describe(entry) {
  if (entry.status === 'found') return `${esc(entry.footballer)}`;
  if (entry.status === 'notfound') return `<span class="muted">"${esc(entry.input)}" (no está)</span>`;
  return '<span class="muted">sin respuesta</span>';
}

function historyTable(round) {
  return `<table class="results"><tbody>${round.entries.map((e) =>
    `<tr><td>${esc(e.name)}</td><td>${describe(e)}</td><td class="num">−${e.goals}</td><td class="num">${e.remaining}</td></tr>`).join('')}</tbody></table>`;
}

function render() {
  if (!state) return;
  const isHost = state.you === state.hostId;
  $('room-code').textContent = state.code;
  $('room-code').classList.remove('hidden');

  if (state.phase === 'lobby') {
    show('lobby');
    $('lobby-code').textContent = state.code;
    playerList($('lobby-players'), state.players);
    if (!rounds.options.length) {
      for (let r = state.limits.minRounds; r <= state.limits.maxRounds; r++) rounds.add(new Option(String(r), String(r)));
    }
    rounds.value = String(state.settings.rounds);
    if (document.activeElement !== $('set-target')) $('set-target').value = state.settings.target;
    rounds.disabled = !isHost;
    $('set-target').disabled = !isHost;
    $('btn-start').classList.toggle('hidden', !isHost);
    $('lobby-wait').classList.toggle('hidden', isHost);
    if (isHost && state.playableTeams === 0) $('lobby-error').textContent = 'Todavía no hay equipos con datos cargados: no se puede empezar.';
    return;
  }

  if (state.phase === 'picking' || state.phase === 'reveal') {
    show('game');
    $('game-round').textContent = `Ronda ${state.round} de ${state.settings.rounds} · Objetivo ${state.settings.target}`;
    $('team-name').textContent = state.team.name;
    $('team-league').textContent = state.team.league;
    const picking = state.phase === 'picking';
    if (!picking) $('game-timer').textContent = '';
    $('pick-form').classList.toggle('hidden', !picking);
    $('reveal').classList.toggle('hidden', picking);
    if (picking && lastRoundShown !== state.round) {
      lastRoundShown = state.round;
      $('pick-input').value = '';
      $('pick-input').disabled = false;
      $('pick-msg').textContent = '';
      $('pick-msg').className = 'msg';
      $('pick-input').focus();
    }
    if (picking && state.myPick) $('pick-input').disabled = true;
    if (!picking) {
      const last = state.history[state.history.length - 1];
      $('reveal-body').innerHTML = last.entries.map((e) =>
        `<tr><td>${esc(e.name)}</td><td>${describe(e)}</td><td class="num">−${e.goals}</td></tr>`).join('');
      $('reveal-next').textContent = 'La próxima ronda empieza en unos segundos…';
    }
    playerList($('game-players'), state.players, { showPicked: picking });
    return;
  }

  if (state.phase === 'finished') {
    show('final');
    const names = state.players.filter((p) => state.winners.includes(p.id)).map((p) => p.name);
    $('final-title').textContent = names.length > 1 ? `🏆 Empate: ${names.join(', ')}` : `🏆 Ganó ${names[0] || '—'}`;
    playerList($('final-players'), state.players, { winners: state.winners });
    $('final-history').innerHTML = state.history.map((r) => `<h3>Ronda ${r.round}: ${esc(r.team)}</h3>${historyTable(r)}`).join('');
    $('btn-again').classList.toggle('hidden', !isHost);
    $('final-wait').classList.toggle('hidden', isHost);
  }
}

socket.on('room:state', (s) => {
  state = s;
  clockOffset = s.serverTime - Date.now();
  render();
});

setInterval(() => {
  if (!state || !state.deadline || state.phase !== 'picking') { $('game-timer').textContent = ''; return; }
  const left = Math.max(0, Math.ceil((state.deadline - (Date.now() + clockOffset)) / 1000));
  $('game-timer').textContent = `${left}s`;
  $('game-timer').classList.toggle('low', left <= 3);
}, 200);
