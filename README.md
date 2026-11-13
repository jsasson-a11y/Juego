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

Solo se sortean equipos con al menos **20 jugadores cargados** (configurable con la variable `MIN_PLAYERS`).

### Cómo se generan los datos

Los goles salen de Wikipedia. `scripts/sources.json` indica qué página y qué tabla se usa para cada equipo, y cada fila del CSV guarda el link exacto (con la versión de la página) de donde salió.

```bash
pip install -r scripts/requirements.txt
python3 scripts/build_data.py            # regenera data/goleadores.csv
python3 scripts/build_data.py arsenal    # revisa un equipo sin escribir el CSV
python3 scripts/inspect_page.py en "List of FC Barcelona players"   # ver tablas de una página
```

Reglas al combinar: si un nombre aparece repetido en un equipo se toma el valor mayor; para la Selección de Alemania, los goles con Alemania Oriental se **suman**.

### Cobertura y limitaciones conocidas

| Situación | Equipos |
|---|---|
| Lista amplia (cientos de jugadores, todas las competencias) | Clubes ingleses, Real Madrid, Inter, Roma, Bayern, Dortmund, Schalke, PSG, Lyon, Mónaco, Benfica, Santos y la mayoría de las selecciones |
| Solo jugadores con 100+ partidos (~140-210) | Atlético de Madrid, Juventus, Milan, Marsella, Porto, Flamengo |
| Solo máximos goleadores (40-130) | Corinthians, Palmeiras, São Paulo, Colombia |
| **Solo goles de liga** (no todas las competencias) | Barcelona |
| Lista parcial | Selección de España (165 con más partidos), Portugal (127) |
| Bayern | Goles oficiales desde la Bundesliga (1963); no incluye la etapa anterior |
| **Sin datos suficientes en Wikipedia (no se sortean)** | Peñarol, Nacional, Defensor Sporting, Danubio, Liverpool (Uy), Boca, River, Independiente, Racing, San Lorenzo, Estudiantes, Rosario Central, Sevilla |
