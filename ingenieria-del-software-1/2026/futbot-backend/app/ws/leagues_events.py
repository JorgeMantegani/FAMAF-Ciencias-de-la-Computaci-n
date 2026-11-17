import logging

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.enrollment import Enrollment
from app.models.room import Room
from app.ws.leagues_hub import leagues_hub
from app.ws.public_friendly_hub import public_friendly_hub

logger = logging.getLogger(__name__)

CHANGED_KEY = "leagues_changed"
WATCHED_MODELS = (Room, Enrollment)     # lo que puede cambiar el listado de ligas
_registered = False


def _mark_flush(session, flush_context):
    """Marca la sesión si en este flush se creó, modificó o borró una sala o inscripción."""
    if session.info.get(CHANGED_KEY):
        return
    for obj in (*session.new, *session.dirty, *session.deleted):
        if isinstance(obj, WATCHED_MODELS):
            session.info[CHANGED_KEY] = True
            return


def _mark_bulk(update_context):
    """Lo mismo para query.update() y query.delete(), que no pasan por el flush."""
    mapper = getattr(update_context, "mapper", None)
    if mapper is not None and issubclass(mapper.class_, WATCHED_MODELS):
        update_context.session.info[CHANGED_KEY] = True


def _notify_after_commit(session):
    if session.info.pop(CHANGED_KEY, False):
        for hub in (leagues_hub, public_friendly_hub):
            try:
                hub.notify_changed()
            except Exception:                # el commit ya se hizo: un fallo del aviso no debe romper el request
                logger.exception("No se pudo programar el aviso de cambio de ligas o amistosos")


def _forget_after_rollback(session):
    session.info.pop(CHANGED_KEY, None)


def register_league_events() -> None:
    """Activa la escucha (una sola vez, aunque se llame de nuevo)."""
    global _registered
    if _registered:
        return
    event.listen(Session, "after_flush", _mark_flush)
    event.listen(Session, "after_bulk_update", _mark_bulk)
    event.listen(Session, "after_bulk_delete", _mark_bulk)
    event.listen(Session, "after_commit", _notify_after_commit)
    event.listen(Session, "after_rollback", _forget_after_rollback)
    _registered = True