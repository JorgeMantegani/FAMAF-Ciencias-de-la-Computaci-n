"""Último snapshot por partido; compartido por motor y sockets del mismo proceso."""
from threading import RLock

from app.schemas.match_state import MatchState


class MatchStates:
    def __init__(self):
        self._states: dict[str, MatchState] = {}
        self._locks: dict[str, RLock] = {}
        self._registry_lock = RLock()

    def lock(self, match_id: str):
        with self._registry_lock:
            return self._locks.setdefault(match_id, RLock())

    def get(self, match_id: str) -> MatchState | None:
        with self.lock(match_id):
            state = self._states.get(match_id)
            return state.model_copy(deep=True) if state else None

    def put(self, state: MatchState):
        match_id = str(state.match_id)
        with self.lock(match_id):
            self._states[match_id] = state.model_copy(deep=True)

    def clear(self):
        """Solo al detener el proceso o en pruebas, sin publicaciones concurrentes."""
        with self._registry_lock:
            self._states.clear()
            self._locks.clear()


match_states = MatchStates()
