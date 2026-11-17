"""Estados de partido por WebSocket autenticado, con snapshots completos."""
import asyncio

import anyio
import json
import logging
from time import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.club import Club
from app.services.match_runner import (
    get_match_substitution_state,
    request_match_substitution,
    get_live_engine,
)
from app.ws.behavior_change import handle_change_behavior
from app.services.match_state import MatchAccessDenied, MatchNotFound, MatchStateUnavailable, authorize_match, get_match_state
from app.ws.manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 15


def read_authorized_state(bind, match_id, token):
    # Una sesión corta para la autenticación y el snapshot inicial.
    with Session(bind) as db:
        user = get_current_user(HTTPAuthorizationCredentials(scheme='Bearer', credentials=token), db)
        expires_at = decode_access_token(token, verify_exp=False)['exp']
        try:
            state = get_match_state(db, match_id, user).model_dump(mode='json')
        except MatchStateUnavailable:
            state = None
        return state, expires_at


def validate_access(bind, match_id, token):
    with Session(bind) as db:
        user = get_current_user(HTTPAuthorizationCredentials(scheme='Bearer', credentials=token), db)
        authorize_match(db, match_id, user)


def authorized_club_id(bind, match_id, token):
    with Session(bind) as db:
        user = get_current_user(HTTPAuthorizationCredentials(scheme='Bearer', credentials=token), db)
        authorize_match(db, match_id, user)
        return db.scalar(select(Club.id).where(Club.user_id == user.id))


async def error_message(socket, status, message):
    await socket.send_json({'type': 'error', 'status': status, 'message': message})
    if status != 409:
        await socket.close(code={401: 4401, 403: 4403, 404: 4404, 422: 4422}.get(status, 1011))


@router.websocket('/api/matches/{match_id}/ws')
async def match_stream(socket: WebSocket, match_id: str, db: Session = Depends(get_db)):
    origin = socket.headers.get('origin')
    if origin and origin not in get_settings().cors_origins_list:
        await socket.close(code=1008)
        return
    await socket.accept()
    subscription = None
    received = changed = event_changed = None
    try:
        # El navegador no permite Authorization en el handshake. El JWT viaja
        # en el primer mensaje, nunca en la URL ni en los logs de acceso.
        try:
            raw = await asyncio.wait_for(socket.receive_text(), timeout=10)
            if len(raw) > 4096:
                raise ValueError('Mensaje demasiado grande')
            auth = json.loads(raw)
            if not isinstance(auth, dict) or auth.get('type') != 'auth' or not isinstance(auth.get('token'), str):
                raise ValueError('Autenticación requerida')
            token = auth['token']
        except (ValueError, TimeoutError):
            await error_message(socket, 401, 'Sesión inválida o vencida')
            return
        try:
            match_id = str(UUID(match_id))
        except ValueError:
            await error_message(socket, 422, 'El ID del partido no es válido.')
            return
        bind = db.get_bind()
        # Suscribir antes de leer el snapshot inicial evita perder un tick.
        claims = decode_access_token(token)
        subscription = manager.subscribe(match_id, claims['sid'])
        state, expires_at = await run_in_threadpool(read_authorized_state, bind, match_id, token)
        club_id = await run_in_threadpool(authorized_club_id, bind, match_id, token)
        substitution_state = get_match_substitution_state(match_id, club_id)
        revision = 0
        if state is None:
            await error_message(socket, 409, 'Esperando el estado inicial del partido. Se actualizará automáticamente.')
        else:
            await socket.send_json({'type': 'state', 'state': state})
            revision = state['revision']
            if state['status'] == 'finished':
                await socket.close(code=1000)
                return
        if substitution_state is not None:
            await socket.send_json(substitution_state)
        received = asyncio.create_task(socket.receive_text())
        changed = asyncio.create_task(subscription.queue.get())
        event_changed = asyncio.create_task(subscription.event_queue.get())
        next_ping = time() + HEARTBEAT_SECONDS
        pong_deadline = None
        while True:
            deadline = min(expires_at, pong_deadline or next_ping)
            done, _ = await asyncio.wait(
                {received, changed, event_changed},
                timeout=max(0, deadline - time()),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if time() >= expires_at:
                await error_message(socket, 401, 'Sesión inválida o vencida')
                return
            if pong_deadline and time() >= pong_deadline:
                await socket.close(code=1011, reason='Sin respuesta al heartbeat')
                return
            if received in done:
                raw = received.result()
                if len(raw) > 4096:
                    await socket.send_json({
                        'type': 'error', 'ok': False,
                        'message': 'Mensaje demasiado grande',
                    })
                else:
                    try:
                        command = json.loads(raw)
                    except json.JSONDecodeError:
                        command = None
                    if isinstance(command, dict) and command.get('type') == 'pong':
                        pong_deadline = None
                        next_ping = time() + HEARTBEAT_SECONDS
                    elif (
                        isinstance(command, dict)
                        and command.get('type') == 'SUBSTITUTE_PLAYER'
                    ):
                        out_player_id = command.get('outPlayerId')
                        in_player_id = command.get('inPlayerId')
                        valid_ids = all(
                            isinstance(value, (str, int))
                            and not isinstance(value, bool)
                            and bool(str(value))
                            for value in (out_player_id, in_player_id)
                        )
                        if valid_ids:
                            result = request_match_substitution(
                                match_id, club_id, out_player_id, in_player_id
                            )
                            if not result.get('ok'):
                                await socket.send_json(result)
                        else:
                            await socket.send_json({
                                'type': 'error', 'ok': False,
                                'error_code': 'SUBSTITUTION_INVALID_REQUEST',
                                'message': 'outPlayerId e inPlayerId son obligatorios',
                            })
                    elif isinstance(command, dict) and command.get('action') == 'CHANGE_BEHAVIOR':
                        await handle_change_behavior(
                            socket, bind, get_live_engine(match_id), club_id, command.get('payload'), match_id
                        )
                    else:
                        await socket.send_json({
                            'type': 'error', 'ok': False,
                            'message': 'Evento WebSocket no reconocido',
                        })
                received = asyncio.create_task(socket.receive_text())
            if event_changed in done:
                event = event_changed.result()
                await socket.send_json(event)
                event_changed = asyncio.create_task(subscription.event_queue.get())
            if changed in done:
                message = changed.result()
                if message['type'] == 'revoked' or subscription.revoked:
                    await error_message(socket, 401, 'Sesión inválida o vencida')
                    return
                changed = asyncio.create_task(subscription.queue.get())
                state = message['state']
                if state['revision'] > revision:
                    revision = state['revision']
                    if state['status'] == 'finished':
                        # Event delivery callbacks for this tick may still be queued.
                        await asyncio.sleep(0)
                        if event_changed.done():
                            await socket.send_json(event_changed.result())
                            event_changed = None
                        while not subscription.event_queue.empty():
                            await socket.send_json(
                                subscription.event_queue.get_nowait()
                            )
                        await socket.send_json(message)
                        await socket.close(code=1000)
                        return
                    await socket.send_json(message)
            if not pong_deadline and time() >= next_ping:
                # Revalidación de permisos; no consulta ni sondea snapshots.
                await run_in_threadpool(validate_access, bind, match_id, token)
                await socket.send_json({'type': 'ping'})
                pong_deadline = time() + HEARTBEAT_SECONDS
    except (HTTPException, JWTError):
        await error_message(socket, 401, 'Sesión inválida o vencida')
    except MatchAccessDenied:
        await error_message(socket, 403, 'No tenés acceso a este partido.')
    except MatchNotFound:
        await error_message(socket, 404, 'El partido no existe.')
    except WebSocketDisconnect:
        pass
    except (SQLAlchemyError, OSError, ValueError):
        logger.exception('No se pudo transmitir el estado del partido')
        await error_message(socket, 503, 'No se pudo actualizar el partido. Reintentando automáticamente…')
    finally:
        if subscription:
            manager.unsubscribe(subscription)
        with anyio.CancelScope(shield=True):
            for task in (received, changed, event_changed):
                if task:
                    task.cancel()
            await asyncio.gather(
                *(task for task in (received, changed, event_changed) if task),
                return_exceptions=True,
            )
