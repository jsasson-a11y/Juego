# Goleadores (juego multijugador online)

Cada ronda sale un equipo al azar. Todos los jugadores tienen **10 segundos** para escribir el nombre de un futbolista de ese equipo, y se restan los goles que ese futbolista hizo en el club.

## Reglas implementadas

| Regla | Cómo funciona |
|---|---|
| Rondas | Entre 4 y 8 (la elige el anfitrión). |
| Objetivo | 1000 goles por defecto (se puede cambiar). Todos arrancan con el mismo objetivo y cada uno lleva su propia cuenta. |
| Turnos | Simultáneos: todos juegan con el mismo equipo y tienen los mismos 10 segundos. |
| Ganador | El primero que llega a 0 **o se pasa** gana. Si varios llegan en la misma ronda, ganan todos (empate). Si se terminan las rondas, gana quien quedó más cerca de 0. |
| Duplicados | Un futbolista que ya eligió alguien no se puede volver a elegir. Gana el que lo mandó primero. Al otro le avisa y puede probar con otro mientras le quede tiempo. |
| Sin respuesta | Si se acaba el tiempo, suma 0. |
| No está en la base | Suma 0 y se termina su turno. |
| Errores de tipeo | Se toleran tildes, mayúsculas y errores comunes (ej: "neimar" → Neymar, "suares" → Suárez, "iguain" → Higuaín). Alcanza con el apellido si es único en ese equipo. |
| Nombre ambiguo | Si lo escrito coincide con más de un jugador del equipo (ej: dos "Rodríguez"), pide ser más específico y deja reintentar. |
| Club y selección | Son independientes: elegir a un futbolista en un club no lo bloquea para su selección (y viceversa). |
| Equipos | No se repite un equipo dentro de la misma partida, salvo que se acaben los equipos con datos. |

## Cómo correrlo

```bash
npm install
npm start          # http://localhost:3000
npm test
```

Para jugar online hay que publicarlo en un servicio que soporte Node.js con WebSockets (por ejemplo Render, Railway o Fly.io). Variables: `PORT` (puerto) y `DATA_DIR` (carpeta de datos alternativa).

## Datos

- `data/teams.json`: lista de equipos.
- `data/goleadores.csv`: goleadores, separado por `;` (se puede abrir con Excel):

```
equipo_id;jugador;goles;alias;fuente
```

  - `goles`: **todos los goles oficiales** con el club (no solo liga). En selecciones: goles con la selección mayor en todos los partidos internacionales, amistosos incluidos (sin juveniles ni Juegos Olímpicos). En Alemania se suman los goles con Alemania Federal y Alemania Oriental.
  - `alias`: otros nombres separados por `|` (ej: `Neymar Jr|Ney`).
  - `fuente`: de dónde salió el dato (URL).

Al arrancar, el servidor valida el CSV y avisa en consola qué líneas tienen problemas. Solo se sortean equipos que tengan al menos un jugador cargado.

> **Estado actual:** `goleadores.csv` está **vacío**. Los datos de `test/fixtures` son ficticios y solo se usan para las pruebas.
