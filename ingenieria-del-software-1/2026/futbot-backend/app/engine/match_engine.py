import asyncio
import logging
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Awaitable, Callable
from app.engine.collisions import resolve_player_collisions
from app.engine.constants import PLAYER_RADIUS

from app.engine.action import NULL_ACTION, Action
from app.engine.tick_context import TickContext
from app.behaviors import executor
from app.engine.physics import (
    apply_kick, check_goal, move_player, resolve_possession, step_ball,
)
from app.engine.schedule import Segment, build_schedule
from app.engine.setup import reset_to_kickoff
from app.engine.state import GoalEvent, MatchPhase, MatchState, PlayerState, Team, Vec2

logger = logging.getLogger(__name__)
PENALTIES_PER_TEAM = 5
PENALTY_MAX_SECONDS = 10


class MatchEngine:
    def __init__(self,
                 state: MatchState,
                 field,
                 cfg,
                 behavior_ids: dict[str, str],
                 schedule: list[Segment] | None = None,
                 rng: random.Random | None = None,
                 controllable_player_ids: set[str] | None = None,
        on_finish: Callable[[MatchState], Awaitable[None]] | None = None,
        realtime: bool = True,
        has_penalty_shootout: bool = False,
        club_ids: dict[Team, str] | None = None,) -> None:
        self.state = state
        self.field = field
        self.cfg = cfg
        self.behavior_ids = behavior_ids
        self.dt = 1.0 / cfg.match_tick_rate
        self.schedule = schedule or build_schedule(
            cfg.friendly_match_duration_seconds, cfg.match_tick_rate
        )
        self.rng = rng or random.Random()
        self.controllable_player_ids = set(controllable_player_ids) if controllable_player_ids is not None else None
        self.on_finish = on_finish
        self.realtime = realtime          # False en tests: sin esperas
        self.has_penalty_shootout = has_penalty_shootout
        self._segment_index = 0
        self._pool = ThreadPoolExecutor(
            max_workers=len(state.players), thread_name_prefix="bot"
        )
        self._busy: dict[str, asyncio.Future] = {}

        self._club_ids = club_ids or {}
        self._pending_behavior_changes: list[tuple[str, str]] = []

        self.pending_substitution = {Team.HOME: None, Team.AWAY: None}
        self.changes_used_this_pause = {Team.HOME: 0, Team.AWAY: 0}
        self.ws_events: list[dict] = []
        self.on_ws_event: Callable[[dict], None] | None = None
        self.coach_active = {Team.HOME: False, Team.AWAY: False}
        self._starters_by_team = {
            Team.HOME: {p.id for p in state.players if p.team == Team.HOME},
            Team.AWAY: {p.id for p in state.players if p.team == Team.AWAY},
        }
        self._bench_by_team = {Team.HOME: set(), Team.AWAY: set()}
        self._bench_players: dict[Team, dict[str, PlayerState]] = {
            Team.HOME: {},
            Team.AWAY: {},
        }
        self.penalty_score = {Team.HOME: 0, Team.AWAY: 0}
        self.penalty_attempts = {Team.HOME: 0, Team.AWAY: 0}
        self.penalty_winner: Team | None = None
        self._penalty_attempt_team: Team | None = None
        self._penalty_shooter: PlayerState | None = None
        self._penalty_goalkeeper: PlayerState | None = None
        self._penalty_full_roster: list[PlayerState] | None = None
        self._penalty_ticks = 0


    async def _collect_actions(self) -> dict[str, Action]:
        ctx = TickContext(self.state, self.field, self.behavior_ids)
        loop = asyncio.get_running_loop()

        # 1. Lanzar los bots que no estén ocupados del tick anterior
        launched: dict[str, asyncio.Future] = {}
        for p in self.state.players:
            if (
                self.controllable_player_ids is not None
                and p.id not in self.controllable_player_ids
            ):
                continue  # este jugador no es controlable por bots
            if p.id in self._busy:
                continue                      # sigue colgado: acción nula
            fut = loop.run_in_executor(
                self._pool, executor.ejecutar_comportamiento, p.id, ctx
            )
            self._busy[p.id] = fut
            fut.add_done_callback(lambda _f, pid=p.id: self._busy.pop(pid, None))
            launched[p.id] = fut

        # 2. Esperar a todos con UN solo presupuesto de tiempo
        if launched:
            await asyncio.wait(
                launched.values(), timeout=self.cfg.behavior_timeout_seconds
            )

        # 3. Leer solo lo que terminó a tiempo
        actions: dict[str, Action] = {}
        for p in self.state.players:
            if (
                self.controllable_player_ids is not None
                and p.id not in self.controllable_player_ids
            ):
                actions[p.id] = NULL_ACTION
                continue  # este jugador no es controlable por bots
            fut = launched.get(p.id)
            if fut is not None and fut.done() and not fut.cancelled() \
                    and fut.exception() is None:
                actions[p.id] = ctx.action_for(p.id)
            else:
                if fut is not None and fut.done() and not fut.cancelled():
                    logger.warning("Bot %s lanzó excepción", p.id,
                                   exc_info=fut.exception())
                actions[p.id] = NULL_ACTION   # timeout, ocupado o falló

        for pid, msg in ctx.errors:
            logger.warning("Bot %s registró error: %s", pid, msg)
        return actions

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        
     # ---------- Cronograma ----------
    def start(self) -> None:
        self._enter_segment(0)

    def _normalize_team(self, team: Team | str) -> Team:
        return team if isinstance(team, Team) else Team(team)

    def _emit_ws_event(self, event_type: str, *, ok: bool | None = None, status: str | None = None, **payload) -> dict:
        message = {"type": event_type}
        if ok is not None:
            message["ok"] = ok
        if status is not None:
            message["status"] = status
        message.update(payload)
        self.ws_events.append(message)
        if self.on_ws_event is not None and event_type != "error":
            self.on_ws_event(message)
        return message

    def set_substitute(
        self,
        team: Team | str,
        player_id: str | int,
        player_state: PlayerState,
    ) -> None:
        team = self._normalize_team(team)
        pid = str(player_id)
        if pid in self._starters_by_team[team] or pid in self._bench_by_team[team]:
            raise ValueError(f"Jugador {player_id} ya está registrado en el equipo {team}")
        if player_state.id != pid or player_state.team != team:
            raise ValueError("El estado del suplente no coincide con el equipo y jugador")
        self._bench_players[team][pid] = player_state
        self._bench_by_team[team].add(pid)

    def _apply_single_substitution(self, team: Team, out_player_id: str, in_player_id: str) -> None:
        team = self._normalize_team(team)
        if out_player_id not in self._starters_by_team[team]:
            raise ValueError(f"Jugador titular no válido: {out_player_id}")
        if in_player_id not in self._bench_by_team[team]:
            raise ValueError(f"Jugador suplente no válido: {in_player_id}")

        out_player = next((p for p in self.state.players if p.team == team and p.id == out_player_id), None)
        in_player = self._bench_players[team][in_player_id]
        if out_player is None:
            raise ValueError(f"Jugador titular no válido: {out_player_id}")

        out_index = self.state.players.index(out_player)
        out_position = out_player.pos
        out_velocity = out_player.vel
        out_player.pos = in_player.pos
        in_player.pos = out_position
        in_player.vel = out_velocity
        self.state.players[out_index] = in_player

        if self.state.ball.owner_id == out_player_id:
            self.state.ball.owner_id = None
            self.state.ball.last_kicker_id = None

        self._starters_by_team[team].remove(out_player_id)
        self._starters_by_team[team].add(in_player_id)
        self._bench_by_team[team].remove(in_player_id)
        self._bench_by_team[team].add(out_player_id)
        del self._bench_players[team][in_player_id]
        self._bench_players[team][out_player_id] = out_player

    def request_substitution(self, team: Team | str, out_player_id: str | int, in_player_id: str | int) -> dict:
        team = self._normalize_team(team)
        out = str(out_player_id)
        inn = str(in_player_id)

        if self.coach_active.get(team, False):
            return self._emit_ws_event(
                "error",
                ok=False,
                error_code="SUBSTITUTION_COACH_ACTIVE",
                message="No se permiten sustituciones mientras el DT está activo",
                team=team.value,
                outPlayerId=out,
                inPlayerId=inn,
            )

        if out not in self._starters_by_team[team]:
            return self._emit_ws_event(
                "error",
                ok=False,
                error_code="SUBSTITUTION_INVALID_OUT_PLAYER",
                message="El jugador de salida debe ser titular",
                team=team.value,
                outPlayerId=out,
                inPlayerId=inn,
            )

        if inn not in self._bench_by_team[team]:
            return self._emit_ws_event(
                "error",
                ok=False,
                error_code="SUBSTITUTION_INVALID_IN_PLAYER",
                message="El jugador de entrada debe ser suplente",
                team=team.value,
                outPlayerId=out,
                inPlayerId=inn,
            )

        if self.state.phase == MatchPhase.PLAY:
            has_future_pause = any(
                segment.phase in (MatchPhase.HYDRATION, MatchPhase.HALFTIME)
                for segment in self.schedule[self._segment_index + 1:]
            )
            if not has_future_pause:
                return self._emit_ws_event(
                    "error",
                    ok=False,
                    error_code="SUBSTITUTION_NO_FUTURE_PAUSE",
                    message="No quedan pausas para realizar una sustitución",
                    team=team.value,
                    outPlayerId=out,
                    inPlayerId=inn,
                )
            if self.pending_substitution[team] is not None:
                return self._emit_ws_event(
                    "error",
                    ok=False,
                    error_code="SUBSTITUTION_ALREADY_PENDING",
                    message="Ya hay una sustitución pendiente para este club",
                    team=team.value,
                    outPlayerId=out,
                    inPlayerId=inn,
                )
            self.pending_substitution[team] = {"outPlayerId": out, "inPlayerId": inn}
            return self._emit_ws_event(
                "SUBSTITUTION_SCHEDULED",
                ok=True,
                status="scheduled",
                team=team.value,
                outPlayerId=out,
                inPlayerId=inn,
            )

        if self.state.phase in (MatchPhase.HYDRATION, MatchPhase.HALFTIME):
            if self.changes_used_this_pause.get(team, 0) > 0:
                return self._emit_ws_event(
                    "error",
                    ok=False,
                    error_code="SUBSTITUTION_LIMIT_REACHED",
                    message="Solo se permite 1 cambio por pausa",
                    team=team.value,
                    outPlayerId=out,
                    inPlayerId=inn,
                )
            self._apply_single_substitution(team, out, inn)
            self.changes_used_this_pause[team] = 1
            return self._emit_ws_event(
                "SUBSTITUTION_APPLIED",
                ok=True,
                status="applied",
                team=team.value,
                outPlayerId=out,
                inPlayerId=inn,
            )

        return self._emit_ws_event(
            "error",
            ok=False,
            error_code="SUBSTITUTION_INVALID_PHASE",
            message="La sustitución solo se admite en juego o pausa activa",
            team=team.value,
            outPlayerId=out,
            inPlayerId=inn,
        )

    def _enter_segment(self, index: int) -> None:
        prev_phase = self.state.phase
        seg = self.schedule[index]
        self._segment_index = index
        self.state.phase = seg.phase
        self.state.period = seg.period
        self.state.phase_tick = 0
        if seg.phase == MatchPhase.PLAY and prev_phase in (MatchPhase.HYDRATION, MatchPhase.HALFTIME):
            self.changes_used_this_pause = {Team.HOME: 0, Team.AWAY: 0}
        if seg.phase != MatchPhase.PLAY:
            self._apply_substitutions()

    def _advance_segment(self) -> None:
        nxt = self._segment_index + 1
        if nxt >= len(self.schedule):
            if (
                self.has_penalty_shootout
                and self.state.score[Team.HOME] == self.state.score[Team.AWAY]
            ):
                self._start_penalties()
            else:
                self.state.phase = MatchPhase.FINISHED
        else:
            self._enter_segment(nxt)

    def _start_penalties(self) -> None:
        self.state.phase = MatchPhase.PENALTIES
        self.state.phase_tick = 0
        self.penalty_score = {Team.HOME: 0, Team.AWAY: 0}
        self.penalty_attempts = {Team.HOME: 0, Team.AWAY: 0}
        self._penalty_full_roster = self.state.players
        self._emit_ws_event(
            "PENALTIES_STARTED",
            ok=True,
            status="started",
            maxAttemptsPerTeam=PENALTIES_PER_TEAM,
            maxSecondsPerAttempt=PENALTY_MAX_SECONDS,
            tickRate=self.cfg.match_tick_rate,
        )
        self._start_penalty_attempt()

    def _start_penalty_attempt(self) -> None:
        if self._penalty_full_roster is None:
            raise RuntimeError("No hay plantel disponible para iniciar los penales")

        attempt_number = sum(self.penalty_attempts.values())
        team = Team.HOME if attempt_number % 2 == 0 else Team.AWAY
        shooters = [p for p in self._penalty_full_roster if p.team == team]
        goalkeepers = [p for p in self._penalty_full_roster if p.team != team]
        if not shooters or not goalkeepers:
            raise RuntimeError("Cada club necesita jugadores en cancha para los penales")

        shooter = self.rng.choice(shooters)
        goalkeeper = self.rng.choice(goalkeepers)
        self._penalty_attempt_team = team
        self._penalty_shooter = shooter
        self._penalty_goalkeeper = goalkeeper
        self._penalty_ticks = 0
        self.state.players = [shooter, goalkeeper]

        center = self.field.center
        shooter.pos = center
        shooter.vel = Vec2()
        goalkeeper.pos = Vec2(
            self.field.own_goal_x(goalkeeper.team)
            + (0.5 if goalkeeper.team == Team.HOME else -0.5),
            center.y,
        )
        goalkeeper.vel = Vec2()
        self.state.ball.pos = center
        self.state.ball.vel = Vec2()
        self.state.ball.owner_id = shooter.id
        self.state.ball.last_kicker_id = None
        self.state.ball.cooldown_ticks = 0

    async def _penalty_tick(self) -> None:
        if self._penalty_attempt_team is None:
            raise RuntimeError("No hay penal activo")

        players = self.state.players
        actions = await self._collect_actions()

        for player in players:
            move_to = actions[player.id].move_to
            if move_to is not None:
                move_player(player, move_to, self.dt, self.field)
            else:
                player.vel = Vec2()
        resolve_player_collisions(players, self.field, PLAYER_RADIUS)

        owner = next(
            (player for player in players if player.id == self.state.ball.owner_id),
            None,
        )
        if owner is not None:
            self.state.ball.pos = owner.pos

        for player in players:
            kick = actions[player.id].kick
            if kick is not None:
                apply_kick(self.state.ball, player, kick)

        scored_for: Team | None = None
        if self.state.ball.owner_id is None:
            previous = self.state.ball.pos
            step_ball(self.state.ball, self.dt, self.field)
            scored_for = check_goal(previous, self.state.ball.pos, self.field)

        if scored_for is not None:
            await self._finish_penalty_attempt(scored_for == self._penalty_attempt_team)
            return

        resolve_possession(self.state.ball, players, self.rng)
        self._penalty_ticks += 1
        max_ticks = max(1, math.floor(PENALTY_MAX_SECONDS / self.dt + 1e-9))
        if self._penalty_ticks >= max_ticks:
            await self._finish_penalty_attempt(False)

    async def _finish_penalty_attempt(self, scored: bool) -> None:
        team = self._penalty_attempt_team
        shooter = self._penalty_shooter
        goalkeeper = self._penalty_goalkeeper
        if team is None or shooter is None or goalkeeper is None:
            raise RuntimeError("El penal activo no tiene jugadores asignados")

        self.penalty_attempts[team] += 1
        if scored:
            self.penalty_score[team] += 1
        self.state.players = self._penalty_full_roster or self.state.players
        reset_to_kickoff(self.state, self.field)
        self._emit_ws_event(
            "PENALTY_SHOT_RESULT",
            ok=True,
            status="scored" if scored else "missed",
            team=team.value,
            shooterId=shooter.id,
            goalkeeperId=goalkeeper.id,
            attempts={
                Team.HOME.value: self.penalty_attempts[Team.HOME],
                Team.AWAY.value: self.penalty_attempts[Team.AWAY],
            },
            score={
                Team.HOME.value: self.penalty_score[Team.HOME],
                Team.AWAY.value: self.penalty_score[Team.AWAY],
            },
        )

        if sum(self.penalty_attempts.values()) == 2 * PENALTIES_PER_TEAM:
            if self.penalty_score[Team.HOME] == self.penalty_score[Team.AWAY]:
                self.penalty_winner = self.rng.choice((Team.HOME, Team.AWAY))
                self._emit_ws_event(
                    "PENALTIES_TIEBREAK",
                    ok=True,
                    status="random",
                    winner=self.penalty_winner.value,
                )
            else:
                self.penalty_winner = max(
                    Team,
                    key=lambda candidate: self.penalty_score[candidate],
                )
            self.state.phase = MatchPhase.FINISHED
            self._emit_ws_event(
                "PENALTIES_FINISHED",
                ok=True,
                status="finished",
                winner=self.penalty_winner.value,
                score={
                    Team.HOME.value: self.penalty_score[Team.HOME],
                    Team.AWAY.value: self.penalty_score[Team.AWAY],
                },
            )
        else:
            self._start_penalty_attempt()

    def _pause_segment(self) -> Segment | None:
        """Current segment if it is a hydration or halftime pause."""
        if self.state.phase not in (MatchPhase.HYDRATION, MatchPhase.HALFTIME):
            return None
        return self.schedule[self._segment_index]

    @property
    def pause_seconds(self) -> int | None:
        """Total length of the current pause, or None outside a pause."""
        segment = self._pause_segment()
        return None if segment is None else round(segment.ticks / self.cfg.match_tick_rate)

    @property
    def pause_remaining_seconds(self) -> float | None:
        """Seconds left in the current pause as of this tick, or None outside a pause."""
        segment = self._pause_segment()
        if segment is None:
            return None
        return (segment.ticks - self.state.phase_tick) / self.cfg.match_tick_rate

    def _apply_substitutions(self) -> None:
        for team in (Team.HOME, Team.AWAY):
            payload = self.pending_substitution[team]
            if payload is None:
                continue
            self._apply_single_substitution(team, payload["outPlayerId"], payload["inPlayerId"])
            self.pending_substitution[team] = None
            self.changes_used_this_pause[team] = 1
            self._emit_ws_event(
                "SUBSTITUTION_APPLIED",
                ok=True,
                status="applied",
                team=team.value,
                outPlayerId=payload["outPlayerId"],
                inPlayerId=payload["inPlayerId"],
            )
    
    # ---------- Un tick ----------
    async def tick(self) -> None:
        s = self.state
        self._apply_pending_behavior_changes()
        if s.phase == MatchPhase.FINISHED:
            return
        if s.phase == MatchPhase.PENALTIES:
            await self._penalty_tick()
            s.tick_count += 1
            s.phase_tick += 1
            return
        if s.phase == MatchPhase.PLAY:
            await self._play_step()
            s.play_ticks += 1
        s.tick_count += 1
        s.phase_tick += 1
        if s.phase_tick >= self.schedule[self._segment_index].ticks:
            self._advance_segment()

    async def _play_step(self) -> None:
        s = self.state
        players = {p.id: p for p in s.players}

        # 1. Decisiones de los bots
        actions = await self._collect_actions()

        # 2. Movimiento
        for p in s.players:
            move_to = actions[p.id].move_to
            if move_to is not None:
                move_player(p, move_to, self.dt, self.field)
            else:
                p.vel = Vec2()

        # 2b. Colisiones entre jugadores
        resolve_player_collisions(s.players, self.field, PLAYER_RADIUS)

        # La pelota acompaña a su dueño antes de patear
        owner = players.get(s.ball.owner_id)
        
        # La pelota acompaña a su dueño antes de patear
        owner = players.get(s.ball.owner_id)
        if owner is not None:
            s.ball.pos = owner.pos

        # 3. Remates (apply_kick revalida la posesión)
        for p in s.players:
            kick = actions[p.id].kick
            if kick is not None:
                apply_kick(s.ball, p, kick)

        # 4. Pelota libre: física y detección de gol
        scorer = None
        if s.ball.owner_id is None:
            prev = s.ball.pos
            step_ball(s.ball, self.dt, self.field)
            scorer = check_goal(prev, s.ball.pos, self.field)

        # 5. Gol: evento, marcador y saque de centro
        if scorer is not None:
            kicker = players.get(s.ball.last_kicker_id)
            author = kicker.id if kicker is not None and kicker.team == scorer else None
            s.goals.append(GoalEvent(
                team=scorer,
                player_id=author,
                second=s.play_ticks // self.cfg.match_tick_rate,
            ))
            s.score[scorer] += 1
            reset_to_kickoff(s, self.field)
            s.ball.last_kicker_id = None
            s.ball.cooldown_ticks = 0
            return
        
        # 6. Posesión
        resolve_possession(s.ball, s.players, self.rng)

    # ---------- Loop ----------
    async def run(self) -> None:
        try:
            self.start()
            next_t = time.monotonic()
            while self.state.phase != MatchPhase.FINISHED:
                await self.tick()
                if not self.realtime:
                    await asyncio.sleep(0)
                    continue
                next_t += self.dt
                delay = next_t - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
                else:                       # nos atrasamos: no acumular deuda
                    next_t = time.monotonic()
                    await asyncio.sleep(0)
            await self._finalize()
        finally:                            # también si se cancela el task
            self.close()

    async def _finalize(self) -> None:
        logger.info("Partido terminado: %s", self.state.score)
        if self.on_finish is not None:
            try:
                await self.on_finish(self.state)
            except Exception:
                logger.exception("Falló on_finish (persistencia/WebSocket)")    
    
    def team_of_club(self, club_id: str) -> Team | None:
        for team, cid in self._club_ids.items():
            if cid == club_id:
                return team
        return None

    def request_behavior_change(self, club_id: str, player_id: str, behavior_id: str) -> None:
        team = self.team_of_club(club_id)
        if team is None:
            raise ValueError("El club no juega este partido")
        if not any(p.id == player_id and p.team == team for p in self.state.players):
            raise ValueError("El jugador no pertenece a tu club.")
        self._pending_behavior_changes.append((player_id, behavior_id))

    def _apply_pending_behavior_changes(self) -> None:
        pending, self._pending_behavior_changes = self._pending_behavior_changes, []
        for player_id, behavior_id in pending:
            self.behavior_ids[player_id] = behavior_id