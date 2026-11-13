'use strict';

// OJO: los goles de este archivo son valores de prueba, NO datos reales.
const test = require('node:test');
const assert = require('node:assert');
const { indexTeam, findPlayer } = require('../server/matcher');

const team = indexTeam([
  { name: 'Neymar', aliases: ['Neymar Jr'], goals: 1 },
  { name: 'Luis Suárez', goals: 2 },
  { name: 'Lionel Messi', aliases: ['Leo Messi'], goals: 3 },
  { name: 'Cristiano Ronaldo', goals: 4 },
  { name: 'Ronaldo', aliases: ['Ronaldo Nazário'], goals: 5 },
  { name: 'Diego Forlán', goals: 6 },
  { name: 'Gonzalo Higuaín', goals: 7 },
  { name: 'Zlatan Ibrahimović', goals: 8 },
  { name: 'Fernando Morena', goals: 9 },
  { name: 'Álvaro Morata', goals: 10 },
]);

const name = (input) => {
  const r = findPlayer(team, input);
  return r.status === 'found' ? team[r.index].player.name : r.status;
};

test('tolera errores de tipeo y fonética', () => {
  assert.equal(name('neimar'), 'Neymar');
  assert.equal(name('NEYMAR'), 'Neymar');
  assert.equal(name('suares'), 'Luis Suárez');
  assert.equal(name('Luis Suarez'), 'Luis Suárez');
  assert.equal(name('mesi'), 'Lionel Messi');
  assert.equal(name('lionel mesi'), 'Lionel Messi');
  assert.equal(name('forlan'), 'Diego Forlán');
  assert.equal(name('higuain'), 'Gonzalo Higuaín');
  assert.equal(name('iguain'), 'Gonzalo Higuaín');
  assert.equal(name('ibrahimovic'), 'Zlatan Ibrahimović');
  assert.equal(name('ibraimovich'), 'Zlatan Ibrahimović');
});

test('nombre exacto gana sobre apellido', () => {
  assert.equal(name('Ronaldo'), 'Ronaldo');
  assert.equal(name('Cristiano Ronaldo'), 'Cristiano Ronaldo');
  assert.equal(name('cristiano ronaldo'), 'Cristiano Ronaldo');
});

test('apellidos parecidos de distintos jugadores no se confunden al escribir bien', () => {
  assert.equal(name('Morena'), 'Fernando Morena');
  assert.equal(name('Morata'), 'Álvaro Morata');
});

test('ambiguo cuando el error de tipeo queda igual de cerca de dos jugadores', () => {
  assert.equal(name('morana'), 'ambiguous');
});

test('no encuentra nombres que no están', () => {
  assert.equal(name('Pelé'), 'notfound');
  assert.equal(name('xyz'), 'notfound');
  assert.equal(name(''), 'notfound');
});
