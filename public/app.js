'use strict';

const socket = io();
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const SESSION_KEY = 'goleadores-session';

let state = null;
let TEAMS = {};
const shownSaldo = {}; // para animar la resta del saldo
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
  TEAMS = Object.fromEntries(teams.map((t) => [t.id, t]));
  render();
  const playable = teams.filter((t) => t.playable).length;
  $('data-status').textContent = `Equipos en juego: ${playable} de ${teams.length}.`;
}).catch(() => {});

$('btn-create').onclick = () => {
  socket.emit('room:create', { name: $('home-name').value }, (res) => { if (res.error) $('home-error').textContent = res.error; });
};
$('btn-join').onclick = () => {
  socket.emit('room:join', { name: $('home-name').value, code: $('home-code').value }, (res) => { if (res.error) $('home-error').textContent = res.error; });
};
$('home-code').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('btn-join').click(); });

// Link de invitación: /?sala=ABCD
const invited = (new URLSearchParams(location.search).get('sala') || '').toUpperCase().replace(/[^A-Z]/g, '').slice(0, 4);
if (invited) {
  $('home-code').value = invited;
  $('home-invite').textContent = `Te invitaron a la sala ${invited}: poné tu nombre y tocá "Unirme".`;
  $('home-invite').classList.remove('hidden');
  $('home-name').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('btn-join').click(); });
}

$('btn-invite').onclick = async () => {
  const url = `${location.origin}/?sala=${state.code}`;
  try {
    if (navigator.share) { await navigator.share({ title: 'Goleadores', text: `Sumate a mi sala ${state.code}`, url }); return; }
    await navigator.clipboard.writeText(url);
    $('invite-msg').textContent = `Link copiado: ${url}`;
  } catch {
    $('invite-msg').textContent = `Compartí este link: ${url}`;
  }
};

socket.on('connect', () => {
  const s = store.get();
  if (s) socket.emit('room:resume', s, (res) => { if (res.error) { store.clear(); show('home'); } });
});
socket.on('session', (s) => store.set(s));

// --- Sala ---
const rounds = $('set-rounds');
const sendSettings = () => {
  socket.emit('room:settings', {
    rounds: Number(rounds.value), target: Number($('set-target').value), pickSeconds: Number($('set-seconds').value),
  }, (res) => {
    $('lobby-error').textContent = res.error || '';
  });
};
rounds.onchange = sendSettings;
$('set-target').onchange = sendSettings;
$('set-seconds').onchange = sendSettings;
$('btn-start').onclick = () => socket.emit('game:start', {}, (res) => { $('lobby-error').textContent = res.error || ''; });
$('btn-again').onclick = () => socket.emit('game:start', {}, (res) => { $('final-error').textContent = res.error || ''; });

// --- Juego ---
$('btn-pass').onclick = () => {
  socket.emit('pick:pass', {}, (res) => {
    const msg = $('pick-msg');
    if (res.error) { msg.textContent = res.error; msg.className = 'msg bad'; return; }
    msg.textContent = res.message;
    msg.className = 'msg warn';
    $('pick-input').disabled = true;
    $('btn-pass').disabled = true; $('btn-pick').disabled = true;
  });
};
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
    $('btn-pass').disabled = true; $('btn-pick').disabled = true;
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
      if (showPicked && p.picked) tags.push('✔ listo');
      const right = state.phase === 'lobby' ? '' : `<span class="num">${p.remaining}</span>`;
      const cls = [p.connected ? '' : 'off', winners.includes(p.id) ? 'winner' : ''].join(' ');
      return `<li class="${cls}"><span>${winners.includes(p.id) ? '🏆 ' : ''}${esc(p.name)}<span class="tag">${tags.join(' · ')}</span></span>${right}</li>`;
    }).join('');
}

// Escudo genérico con los colores y la sigla del equipo (o el logo, si existe en public/logos/).
function badge(teamId, size = '') {
  const t = TEAMS[teamId];
  if (t && t.logo) return `<img class="badge-img ${size}" src="${esc(t.logo)}" alt="${esc(t.name)}">`;
  const [c1, c2] = (t && t.colors) || ['#556', '#889'];
  const short = (t && t.short) || '?';
  return `<span class="badge ${size}" title="${esc(t ? t.name : '')}"><span class="shield" style="--c1:${esc(c1)};--c2:${esc(c2)}"><b>${esc(short)}</b></span></span>`;
}

function pickLabel(e) {
  if (e.status === 'found') return esc(e.footballer);
  if (e.status === 'pass') return '<span class="muted">Pasó</span>';
  if (e.status === 'notfound') return `<span class="muted">"${esc(e.input)}" · no está</span>`;
  return '<span class="muted">Sin respuesta</span>';
}

// Cuenta de un participante: arranca en el objetivo y resta lo de cada ronda.
function ledger(playerId, { pending = null, saldoId = '' } = {}) {
  const rows = [`<div class="lrow start"><span class="lname">Objetivo</span><span class="lnum">${state.settings.target}</span></div>`];
  let saldo = state.settings.target;
  for (const r of state.history) {
    const e = r.entries.find((x) => x.playerId === playerId);
    if (!e) continue;
    saldo = e.remaining;
    rows.push(`<div class="lrow">${badge(r.teamId)}<span class="lname">${pickLabel(e)}<small>${esc(r.team)} · ronda ${r.round}</small></span><span class="lnum minus">−${e.goals}</span></div>`);
  }
  if (pending) {
    const label = pickLabel(pending);
    rows.push(`<div class="lrow pending">${badge(state.team && state.team.id)}<span class="lname">${label}<small>se resta al terminar la ronda</small></span><span class="lnum minus">−${pending.goals}</span></div>`);
  }
  rows.push(`<div class="lrow saldo"><span class="lname">Saldo</span><span class="lnum" ${saldoId ? `id="${saldoId}" data-target="${saldo}"` : ''}>${saldoId ? (shownSaldo[saldoId] ?? saldo) : saldo}</span></div>`);
  return rows.join('');
}

// Animación: el saldo baja de a poco hasta el valor nuevo.
function animateSaldos() {
  document.querySelectorAll('[data-target]').forEach((el) => {
    const id = el.id;
    const to = Number(el.dataset.target);
    const from = shownSaldo[id] ?? to;
    if (from === to) { shownSaldo[id] = to; el.textContent = to; return; }
    const t0 = performance.now();
    const step = (now) => {
      const k = Math.min(1, (now - t0) / 900);
      const v = Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3)));
      el.textContent = v;
      if (k < 1) requestAnimationFrame(step); else shownSaldo[id] = to;
    };
    requestAnimationFrame(step);
  });
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
    if (!$('set-seconds').options.length) {
      for (const sec of state.limits.pickSeconds) $('set-seconds').add(new Option(`${sec} s`, String(sec)));
    }
    $('set-seconds').value = String(state.settings.pickSeconds);
    $('set-seconds').disabled = !isHost;
    rounds.disabled = !isHost;
    $('set-target').disabled = !isHost;
    $('btn-start').classList.toggle('hidden', !isHost);
    $('lobby-wait').classList.toggle('hidden', isHost);
    if (isHost && state.playableTeams === 0) $('lobby-error').textContent = 'Todavía no hay equipos con datos cargados: no se puede empezar.';
    return;
  }

  if (state.phase === 'countdown') {
    show('game');
    $('game-round').textContent = `Ronda ${state.round} de ${state.settings.rounds}`;
    $('team-badge').innerHTML = '<span class="badge big"><span class="shield" style="--c1:#2b4234;--c2:#18271e"><b>?</b></span></span>';
    $('team-name').textContent = '¿Qué equipo saldrá?';
    $('team-league').textContent = '';
    $('countdown').classList.remove('hidden');
    $('pick-form').classList.add('hidden');
    $('reveal').classList.add('hidden');
    $('pick-msg').textContent = '';
    $('my-ledger').innerHTML = ledger(state.you, { saldoId: 'saldo-me' });
    playerList($('game-players'), state.players);
    animateSaldos();
    return;
  }

  if (state.phase === 'picking' || state.phase === 'reveal') {
    show('game');
    $('countdown').classList.add('hidden');
    $('game-round').textContent = `Ronda ${state.round} de ${state.settings.rounds} · ${state.settings.pickSeconds} s`;
    $('team-badge').innerHTML = badge(state.team.id, 'big');
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
      $('btn-pass').disabled = false; $('btn-pick').disabled = false;
      $('pick-msg').textContent = '';
      $('pick-msg').className = 'msg';
      $('pick-input').focus();
    }
    if (picking && state.myPick) { $('pick-input').disabled = true; $('btn-pass').disabled = true; $('btn-pick').disabled = true; }
    if (!picking) {
      const last = state.history[state.history.length - 1];
      $('reveal-title').textContent = `Ronda ${last.round}: ${last.team}`;
      $('reveal-body').innerHTML = last.entries.map((e) => `
        <div class="rv">${badge(last.teamId)}
          <span class="lname"><b>${esc(e.name)}</b><small>${pickLabel(e)}</small></span>
          <span class="rv-math"><span class="minus">−${e.goals}</span><span class="eq">= ${e.remaining}</span></span>
        </div>`).join('');
    }
    $('my-ledger').innerHTML = ledger(state.you, { pending: picking ? state.myPick : null, saldoId: 'saldo-me' });
    playerList($('game-players'), state.players, { showPicked: picking });
    animateSaldos();
    return;
  }

  if (state.phase === 'finished') {
    show('final');
    const names = state.players.filter((p) => state.winners.includes(p.id)).map((p) => p.name);
    $('final-title').textContent = names.length > 1 ? `🏆 Empate: ${names.join(', ')}` : `🏆 Ganó ${names[0] || '—'}`;
    const ordered = [...state.players].sort((a, b) => a.remaining - b.remaining);
    $('final-ledgers').innerHTML = ordered.map((p) => `
      <div class="ledger-card ${state.winners.includes(p.id) ? 'winner' : ''}">
        <div class="ledger-head">${state.winners.includes(p.id) ? '🏆 ' : ''}${esc(p.name)}${p.id === state.you ? ' <span class="tag">vos</span>' : ''}</div>
        <div class="ledger">${ledger(p.id)}</div>
      </div>`).join('');
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
  if (state && state.deadline && state.phase === 'countdown') {
    const n = Math.max(1, Math.ceil((state.deadline - (Date.now() + clockOffset)) / 1000));
    $('countdown-num').textContent = n;
    $('game-timer').textContent = '';
    return;
  }
  if (!state || !state.deadline || state.phase !== 'picking') { $('game-timer').textContent = ''; return; }
  const left = Math.max(0, Math.ceil((state.deadline - (Date.now() + clockOffset)) / 1000));
  $('game-timer').textContent = `${left}s`;
  $('game-timer').classList.toggle('low', left <= 3);
}, 200);
