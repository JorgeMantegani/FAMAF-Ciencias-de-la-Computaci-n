Resumen para estudiar: sustituciones por WebSocket
1. ¿Qué busca resolver el ticket?
Permitir que un usuario solicite un cambio de jugador durante un partido, sin que el frontend controle directamente el estado del motor:

Si el partido está en juego, la sustitución se guarda pendiente y se realiza en la próxima pausa.
Si el partido está en pausa, se realiza inmediatamente.
Cada club puede hacer como máximo un cambio por pausa.
El servidor verifica que el jugador que sale sea titular y que quien entra sea suplente del mismo equipo.
2. Recorrido de una solicitud
El canal es /api/matches/{match_id}/ws, atendido en matches.py.

El cliente se conecta y envía primero su autenticación:


El servidor valida la sesión y que el usuario pertenezca a uno de los clubes del partido. De esa identidad obtiene el equipo; el cliente no envía el club en la solicitud.

Para pedir el cambio, el cliente envía:


El WebSocket pasa la solicitud al runner en match_runner.py, que busca el motor activo del partido y traduce el club autenticado a HOME o AWAY.

El motor valida la solicitud y decide si la deja pendiente o la aplica. Esa lógica está en match_engine.py.

3. Estados y conceptos principales
En el motor hay dos valores por equipo:

pending_substitution: cambio pendiente o None.
changes_used_this_pause: contador del cupo usado durante la pausa.
El motor conserva además conjuntos de titulares y suplentes. El runner carga el roster desde la base de datos, separando quién está en cancha y quién está de suplente, en match_runner.py.

set_substitute() registra el objeto del suplente que entrará al estado activo cuando se aplique el cambio. Al realizar la sustitución, el motor reemplaza al titular en state.players y actualiza los conjuntos de titulares y suplentes. Eso ocurre en _apply_single_substitution().

4. Qué pasa según la fase del partido
Partido en juego
Si la solicitud es válida:

Se guarda el par de IDs en pending_substitution.
Se emite SUBSTITUTION_SCHEDULED.
Se rechaza otra solicitud del mismo club si ya tiene un cambio pendiente.
Llegada a una pausa
Cuando el motor cambia a una fase distinta de PLAY, llama a la lógica que aplica las sustituciones pendientes. El cambio se efectúa, se limpia pending_substitution, se marca el cupo como usado y se emite SUBSTITUTION_APPLIED. La transición y aplicación están en _enter_segment() y _apply_substitutions().

Solicitud durante una pausa
Si el cupo del club todavía está libre, se aplica inmediatamente y el contador queda en 1. Si ya se utilizó, el servidor rechaza la solicitud con el mensaje:


Al reanudarse el juego, el contador se reinicia para cada club.

5. Cómo viajan los eventos al frontend
El motor crea los eventos y llama a un callback. El manager los distribuye a las conexiones autorizadas de ese partido mediante una cola separada de la cola de snapshots, en manager.py.

La cola separada importa porque los snapshots pueden llegar en cada tick: los eventos de sustitución no deben desaparecer al reemplazarse un snapshot por uno más reciente.

El cliente puede recibir:

SUBSTITUTION_SCHEDULED: solicitud aceptada y pendiente.
SUBSTITUTION_APPLIED: sustitución ya aplicada.
error: solicitud rechazada, por ejemplo por IDs inválidos, equipo incorrecto o cupo agotado.
state: snapshot del partido, que refleja qué jugadores están en cancha.
El mensaje de error se devuelve al socket solicitante; los eventos de cambio programado y aplicado se transmiten a los sockets autorizados del partido.

El canal conserva también la autenticación inicial y el heartbeat: el servidor envía ping periódicamente y el cliente debe responder {"type":"pong"}. Si el cliente manda un evento no reconocido, recibe un error.

6. Pruebas y documentación
test_match_engine.py verifica que una solicitud pendiente se aplique al alcanzar una pausa, que el cambio inmediato funcione y que se rechace exceder el límite.
test_match_websocket.py verifica el envío del comando por WebSocket, la recepción de los eventos y el rechazo por límite.
El contrato para el frontend está descrito en README.md.
La validación ejecutada pasó la suite completa: 320 tests.

7. Límites importantes de la implementación
La sustitución cambia el estado en memoria del motor y se refleja en los snapshots, pero no actualiza MatchPlayer.on_field en la base de datos. Al reconstruir el motor, ese cambio no queda persistido.
coach_active se comprueba en el motor, pero no está conectado a un estado real del DT: actualmente se inicializa como False. Por eso, esa regla requiere una definición e integración adicionales si debe bloquear cambios en producción.

Pruebas de sustituciones
Las pruebas específicas del flujo están en test_match_engine.py y test_match_websocket.py.

Pruebas del motor
El fixture de make_engine crea un partido de prueba con jugadores como h0, h1 y h2. El helper register_home_substitute() registra h3 como suplente local.

test_pending_substitution_is_stored_in_memory_and_applies_on_pause: solicita el cambio de h0 por h3 mientras se juega. Comprueba que queda guardado en pending_substitution y genera SUBSTITUTION_SCHEDULED. Luego ajusta el tick al último de esa fase y hace avanzar el motor con await eng.tick(). Comprueba que entra en hidratación, aplica el cambio, limpia la solicitud y marca el cupo como usado.
test_substitution_applies_immediately_during_pause: pone el partido en hidratación y solicita el cambio. Comprueba que el motor lo aplica en esa misma llamada, marca el cupo y registra SUBSTITUTION_APPLIED.
test_substitution_is_blocked_if_already_used_this_pause: inicia con el contador del equipo en 1 y solicita otro cambio durante la pausa. Comprueba que se rechaza con el mensaje del límite y no queda una solicitud pendiente.
test_resume_clears_changes_used_this_pause: simula el regreso al juego entrando a un segmento PLAY. Comprueba que el contador vuelve a 0.
Prueba de integración WebSocket
test_substitution_command_is_applied_and_events_reach_websocket, en test_match_websocket.py: construye un motor con el roster de una partida de prueba, registra ese motor para que el handler pueda encontrarlo y se conecta con un usuario autenticado. Envía SUBSTITUTE_PLAYER; comprueba que el socket recibe SUBSTITUTION_SCHEDULED. Después cambia manualmente el motor a hidratación y llama a _apply_substitutions(); comprueba que llega SUBSTITUTION_APPLIED. Finalmente solicita otro cambio en esa pausa y verifica el rechazo por límite.
Detalle importante: la prueba WebSocket sí cubre el envío y la recepción de eventos, pero la parte diferida fuerza manualmente la fase y llama al método del motor. La transición real por tick y aplicación automática se prueba en test_pending_substitution_is_stored_in_memory_and_applies_on_pause.


Resumen para estudiar
1. Botón de sustitución en el partido
En LiveMatchControls.jsx agregué el botón “Sustituir”. Se muestra mientras el partido está in_progress o paused, y desaparece al finalizar.

El botón recibe una propiedad disabled para contemplar el caso de un DT activo. El estado actual del backend no publica ese dato, así que la interfaz solo podrá bloquearlo cuando el servidor incluya coach_active o active_coach en el snapshot.

2. Modal para preparar el cambio
En SubstitutionModal.jsx implementé el panel de las capturas. Permite seleccionar:

Un titular que sale.
Un suplente que entra.
Una tarjeta de resumen antes de confirmar.
También incluye estados vacíos, botón de cancelar y cierre con Escape o al hacer clic fuera del panel.

Los estilos y el diseño responsive están en SubstitutionModal.css.

3. Envío por WebSocket
En use_match_state.js agregué send_match_command, que envía el comando por la conexión WebSocket ya abierta. Si la conexión no está disponible, muestra un error en lugar de fallar silenciosamente.

Al confirmar, Match.jsx envía:


El servidor determina el club a partir de la sesión autenticada; el frontend no lo incluye en el comando.

4. Eventos y estado visual
En Match.jsx agregué el procesamiento de los eventos WebSocket:

SUBSTITUTION_SCHEDULED: muestra “Sustitución planificada para la siguiente pausa” y el badge “Cambio planificado para la próxima pausa: [titular] por [suplente]”.
SUBSTITUTION_APPLIED: muestra “Sustitución efectuada”, registra que se usó el cupo de la pausa y actualiza las listas localmente hasta que llegue el snapshot actualizado.
MATCH_RESUMED: limpia el bloqueo para la siguiente pausa. También detecto la reanudación si el snapshot cambia de paused a in_progress.
Error del servidor por límite agotado: se muestra el mensaje de error y se bloquea el cupo local.
5. Límite de un cambio por pausa
En el modal, si el estado indica que ya se utilizó el cupo:

Aparece “Límite alcanzado: 1 cambio por pausa”.
El botón “Confirmar cambio” queda deshabilitado.
Además, mientras hay una sustitución pendiente, no se puede enviar otra solicitud desde el modal.

6. Pruebas añadidas
En Match.test.jsx agregué pruebas para comprobar que:

El botón sigue habilitado durante in_progress y paused.
El comando se envía por WebSocket y aparece el badge al recibir SUBSTITUTION_SCHEDULED.
SUBSTITUTION_APPLIED bloquea el envío y MATCH_RESUMED habilita nuevamente el formulario.
Verificación: los tests del partido pasan (18/18), el build y el lint de los archivos del cambio pasan, y git diff --check no detecta problemas de formato. La suite completa tuvo un fallo en una prueba existente de navegación: esperaba el botón “Ir al partido”, pero la sala muestra “Ver partido”.

Límites a tener en cuenta
No hice cambios en el backend.
El frontend asume que el club de la sesión identifica al usuario que puede hacer la sustitución.
El bloqueo por DT requiere que el backend exponga ese estado; por ahora no lo hace.
Según las notas del proyecto, el backend actualiza el estado del motor, pero no persiste MatchPlayer.on_field en la base de datos.



Resumen técnico para estudiar: configuración de penales y tabla de posiciones
1. Objetivo del ticket
Permitir que al crear una liga se indique si los partidos empatados se definen por penales y calcular su tabla de posiciones con esta puntuación:

Victoria en tiempo regular: 3 puntos para el ganador y 0 para el perdedor.
Victoria por penales: 2 puntos para el ganador de la tanda y 0 para el otro club.
Empate sin ganador registrado por penales: 1 punto para cada club.

La regla que se pidió inicialmente para penales era 3-2-0. Durante la implementación se aclaró que un empate sin definición debía conservar 1 punto para cada equipo. Por eso el comportamiento final es 3-2-1-0, no 3-2-0 para todo resultado: el 0 corresponde al perdedor de una victoria regular o por penales.

2. Dónde se persiste la configuración
El modelo League del proyecto no es una tabla independiente: una liga es un registro de Room cuyo type es public o private. Por eso has_penalty_shootout se agregó a app/models/room.py, como columna booleana no nula y con default False tanto en Python como en la base de datos.

En app/schemas/league.py, CreateLeague declara has_penalty_shootout: bool = False. Si el cliente omite el parámetro en POST /api/leagues, Pydantic usa False. Si lo manda como true, create_league() en app/services/league_service.py copia el valor al nuevo objeto Room. La respuesta LeagueResponse también expone has_penalty_shootout para que el cliente pueda conocer la configuración guardada.

Ejemplo mínimo del fragmento de configuración del JSON:

{
  "has_penalty_shootout": true
}

Esto es solo el fragmento: el endpoint todavía requiere los demás campos de creación, como nombre, límites de clubes, duración, titulares y suplentes.

3. Campo que registra al ganador de penales
app/models/match.py define penalty_winner_club_id como una columna nullable que referencia clubs.id. Vale NULL si no se registró un ganador de tanda. Se agregó también un CheckConstraint llamado ck_matches_penalty_winner_participant para que el valor, cuando exista, sea home_club_id o away_club_id. La restricción protege la integridad del dato: un equipo ajeno al partido no puede aparecer como ganador por penales.

El CheckConstraint no verifica que la liga tenga penales habilitados, que el partido esté empatado ni que haya terminado. Esas reglas no se implementan con esa condición SQL. La función de posiciones solo usa el campo para partidos finalizados, y solo cuando Room.has_penalty_shootout es true.

Importante: el backend de este ticket agrega el campo que permite almacenar el ganador, pero no implementa la ejecución de la tanda ni el proceso que decide y escribe penalty_winner_club_id. Para que un partido empate efectivamente por penales, otro flujo debe persistir el ID del club ganador. Si el campo sigue en NULL, la tabla trata el partido como empate normal y asigna 1 punto a cada equipo, incluso si la liga tiene penales activados.

4. Actualización de bases ya existentes
app/db/init_db.py llama primero a Base.metadata.create_all(bind=engine). create_all crea tablas ausentes, pero no agrega columnas a una tabla existente. Para instalaciones cuyo esquema ya existía, crear_tablas() revisa mediante SQLAlchemy inspect si faltan las columnas rooms.has_penalty_shootout y matches.penalty_winner_club_id. Solo entonces ejecuta ALTER TABLE para agregarlas.

La columna has_penalty_shootout se agrega como BOOLEAN NOT NULL DEFAULT FALSE, por lo que las filas viejas quedan con la modalidad desactivada. penalty_winner_club_id se agrega como VARCHAR(36) y referencia clubs(id); se permite NULL porque los partidos existentes no tienen por qué contar con ganador de penales.

La comprobación hace que ejecutar la inicialización de nuevo no vuelva a intentar agregar columnas existentes. Esto es una actualización incremental simple, no un sistema general de migraciones como Alembic. La prueba test_la_inicializacion_agrega_columnas_a_tablas_existentes en tests/test_db.py crea tablas antiguas mínimas, ejecuta crear_tablas() y verifica las columnas y el default.

5. Cómo se calcula la tabla
El endpoint GET /api/leagues/{league_id}/standings está declarado en app/routers/leagues.py y llama a get_league_standings(db, league_id), en app/services/league_service.py. Requiere autenticación. Si el ID no corresponde a una sala pública o privada, la API responde 404.

La función primero busca los clubes inscritos en esa sala a través de Enrollment. Inicializa sus estadísticas en cero para que también aparezcan clubes que todavía no jugaron. Luego selecciona los Match con ese room_id y status == finished. Los encuentros scheduled, pre_match, in_progress o paused no afectan puntos, goles ni partidos jugados.

Para cada encuentro finalizado:

Se incrementan matches_played para ambos clubes y se actualizan goals_for y goals_against.
Si home_goals es mayor que away_goals, el local recibe 3 puntos, un partido ganado, y el visitante registra una derrota.
Si away_goals es mayor que home_goals, el visitante recibe 3 puntos y el local registra una derrota.
Si los goles son iguales y la liga tiene has_penalty_shootout == true, se compara penalty_winner_club_id con los IDs local y visitante. El ganador recibe 2 puntos y una victoria; el otro suma una derrota y 0 puntos.
Si los goles son iguales pero no hay ganador por penales válido (incluyendo el caso en que penales están desactivados o penalty_winner_club_id es NULL), ambos reciben 1 punto y suman un empate.

La función no escribe esos totales en Enrollment.points ni en otras columnas. La tabla se calcula nuevamente a partir de los partidos cada vez que se consulta el endpoint. Los campos acumulados existentes en Enrollment no forman parte de este cálculo.

6. Formato y orden de la respuesta
La respuesta es una lista JSON de filas LeagueStanding, definida en app/schemas/league.py. Cada fila contiene:

club_id y club_name: identidad del club.
points: puntos calculados.
matches_played, matches_won, matches_drawn y matches_lost: resumen de resultados.
goals_for y goals_against: goles anotados y recibidos.
goal_difference: goals_for - goals_against.

El orden de clasificación es puntos descendentes, diferencia de gol descendente, goles a favor descendentes y, para hacer determinista el orden final, nombre del club sin distinguir mayúsculas y club_id.

7. Pruebas y validación ejecutada
test_create_league_with_penalty_shootout en tests/test_leagues.py verifica POST /api/leagues con el flag true, su inclusión en la respuesta y su persistencia en Room. El test de creación habitual también verifica que si no se envía el campo quede en false.

test_league_standings_score_regular_wins_penalties_and_draws crea tres clubes y partidos con victoria regular, empate con ganador por penales, empate sin ganador por penales y un partido no finalizado. Comprueba puntos, estadísticas y que el fixture pendiente no se cuente.

En tests/test_db.py, el test de inicialización valida la actualización de columnas para una base con tablas previas. En la implementación se ejecutó la suite completa: 372 tests pasaron; tras el último ajuste se volvieron a ejecutar los tests enfocados de liga y base de datos: 32 pasaron. Ruff con selectores I y F no encontró problemas de imports ni errores de nombres en los archivos modificados. El chequeo Ruff completo todavía reporta cuestiones de estilo preexistentes en archivos tocados.

8. Archivos principales
app/schemas/league.py: campos de entrada y salida de liga, y esquema LeagueStanding.
app/models/room.py: configuración persistida has_penalty_shootout.
app/models/match.py: penalty_winner_club_id y restricción del club participante.
app/services/league_service.py: persistencia al crear liga y cálculo get_league_standings().
app/routers/leagues.py: endpoints de creación y consulta de posiciones.
app/db/init_db.py: actualización incremental de columnas.
tests/test_leagues.py y tests/test_db.py: pruebas de creación, cálculo y compatibilidad del esquema.