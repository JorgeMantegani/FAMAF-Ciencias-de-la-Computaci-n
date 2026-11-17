from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enrollment import Enrollment
from app.models.room import Room, ROOM_STATUS_WAITING_GUEST, ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_CANCELLED
from app.models.club import Club
from app.models.user import User
from app.ws.manager import room_manager as manager
from app.ws.manager import league_manager, active_rooms_manager
from app.services.league_orchestrator import get_league_lobby_payload, run_next_league_match



router = APIRouter()


@router.websocket("/ws/friendly/{room_id}")
async def friendly_ws(
    websocket: WebSocket,
    room_id: str,
    club_id: str,
    db: Session = Depends(get_db),
):
    await websocket.accept()

    room_exists = db.query(Room).filter(Room.id == room_id).first() is not None
    enrolled = room_exists and db.query(Enrollment).filter(
        Enrollment.room_id == room_id,
        Enrollment.club_id == club_id,
    ).first() is not None

    db.close()

    if not room_exists:
        await websocket.close(code=4404)
        return

    if not enrolled:
        await websocket.close(code=4403)
        return

    await manager.connect(room_id, club_id, websocket)
    await manager.broadcast(room_id, {
        "type": "club_connected",
        "club_id": club_id,
    })

    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager.disconnect(room_id, club_id)
        await manager.broadcast(room_id, {
            "type": "club_disconnected",
            "club_id": club_id,
        })


@router.websocket("/ws/league/{league_id}/waiting")
async def league_waiting_room_ws(websocket: WebSocket,
                    league_id: str,
                    club_id: str,
                    db: Session = Depends(get_db),
):
    await websocket.accept()

    # Validacion de sesion de usuario
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    # Validar usuario autenticado y coincidencia con el club_id
    user = None
    if token:
        try:
            from app.core.security import decode_access_token
            from app.models.auth_session import AuthSession
            from time import time
            claims = decode_access_token(token)
            session = db.get(AuthSession, claims.get("sid"))
            if session and not session.revoked and session.expires_at > time():
                user = db.get(User, claims.get("sub"))
        except Exception:
            pass

    club_obj = db.get(Club, club_id) if club_id else None

    if not user or not club_obj or club_obj.user_id != user.id:
        await websocket.close(code=4008, reason="No autorizado o token invalido.")
        db.close()
        return

    # Validar que la liga exista en BD
    room = db.query(Room).filter(Room.id == league_id).first()
    if not room or room.status != ROOM_STATUS_WAITING_GUEST:
        await websocket.close(code=4404, reason="La sala no existe o ya inició.")
        db.close()
        return

    # Validar que el usuario pertenece a la liga
    enrolled = db.query(Enrollment).filter(
        Enrollment.room_id == league_id,
        Enrollment.club_id == club_id,
    ).first() is not None

    if not enrolled:
        await websocket.close(code=4403, reason="El club no esta inscripto en esta liga.")
        db.close()
        return

    # Validar limite de clubs
    current_count = league_manager.get_rooms_user_count(league_id)
    if current_count >= room.max_clubs:
        await websocket.close(code=4008, reason="El lobby de espera esta lleno.")
        db.close()
        return

    # Registrar la conexion
    await league_manager.connect_waiting(league_id, club_id, websocket, room.max_clubs)

    # Funcion auxiliar para generar el payload fresco
    def get_room_payload(session: Session):
        r = session.query(Room).filter(Room.id == league_id).first()
        if not r:
            return None
        enrollments = session.query(Enrollment).filter(Enrollment.room_id == league_id).all()
        inscribed_clubs = [e.club_id for e in enrollments]

        creator_name = session.query(Club.name).filter(Club.id == r.creator_club_id).scalar() or "Desconocido"

        return{
            "type": "room_info",
            "league_id": r.id,
            "league_name": r.name,
            "creator_club_id": r.creator_club_id,
            "creator_club_name": creator_name,
            "inscribed_clubs": inscribed_clubs,
            "current_participants": len(inscribed_clubs),
            "min_clubs": r.min_clubs,
            "max_clubs": r.max_clubs,
            "status": r.status,
            "can_start": len(inscribed_clubs) >= r.min_clubs
        }

    initial_data = get_room_payload(db)
    db.close()

    if initial_data:
        # Envia informacion inicial al cliente conectado
        await websocket.send_json(initial_data)

        # Notificar a los demas que un club se unio
        await league_manager.broadcast_waiting(league_id, {
            "type": "club_joined_waiting",
            "club_id": club_id,
            "current_participants": initial_data["current_participants"]
        }, exclude_club_id=club_id)


    
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            bind = db.get_bind()
            # Acciones
            with Session(bind) as action_db:
                current_room = action_db.query(Room).filter(Room.id == league_id).first()

                # Validacion de estado de la liga
                if not current_room or current_room.status != ROOM_STATUS_WAITING_GUEST:
                    redirect_url = f"/league/{league_id}/live" if current_room and current_room.status == ROOM_STATUS_IN_PROGRESS else "/home"
                    event_type = "league_started" if current_room and current_room.status == ROOM_STATUS_IN_PROGRESS else "league_cancelled"

                    await websocket.send_json({
                        "type": event_type,
                        "redirect_url": redirect_url
                    })
                    await websocket.close(code=1000)
                    break


                if action == "leave_room":
                    # Abandono de liga para clubs que no son el creador
                    if current_room and club_id == current_room.creator_club_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "El creador no puede abandonar la liga, debe cancelarla."
                        })
                        continue

                    enrollment_to_delete = action_db.query(Enrollment).filter(
                        Enrollment.room_id == league_id,
                        Enrollment.club_id == club_id
                    ).first()

                    if enrollment_to_delete:
                        action_db.delete(enrollment_to_delete)
                        action_db.commit()

                    # Desconexion de sockets zombies
                    league_manager.disconnect_waiting(league_id, club_id)

                    # Notificar el abandono
                    updated_payload = get_room_payload(action_db)
                    await league_manager.broadcast_waiting(league_id, updated_payload)
                    await websocket.close(code=1000)
                    await active_rooms_manager.broadcast_to_user(user.id, club_id, action_db)
                    break

                elif action in ["start_league", "cancel_league"]:
                    if not current_room:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Liga inexistente"
                        })
                        continue

                    if club_id != current_room.creator_club_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Solo el creador puede realizar esta accion."
                        })
                        continue

                    # Inicio de Liga
                    if action == "start_league":
                        current_participants = action_db.query(Enrollment).filter(Enrollment.room_id == league_id).count()
                        if current_participants < current_room.min_clubs:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Se requiere al menos {current_room.min_clubs} clubes para iniciar."
                            })
                            continue

                        current_room.status = ROOM_STATUS_IN_PROGRESS
                        # Generar el fixture
                        from app.services.league_orchestrator import generate_league_fixture
                        generate_league_fixture(action_db, league_id)
                        action_db.commit()

                        # Disparar el orquestrador 
                        asyncio.create_task(run_next_league_match(action_db.get_bind(), league_id))

                        await league_manager.broadcast_waiting(league_id, {
                            "type": "league_started",
                            "redirect_url": f"/league/{league_id}/live"
                        })

                    elif action == "cancel_league":
                        current_room.status = ROOM_STATUS_CANCELLED
                        action_db.commit()
                        
                        await league_manager.broadcast_waiting(league_id, {
                            "type": "league_cancelled",
                            "redirect_url": "/home"
                        })
                        await active_rooms_manager.broadcast_to_user(user.id, club_id, action_db)

    except WebSocketDisconnect:
        league_manager.disconnect_waiting(league_id, club_id)
        bind = db.get_bind()
        with Session(bind) as disc_db:
            # Reconstruccion de payload por desconexion
            payload_disc = get_room_payload(disc_db)
            if payload_disc:
                await league_manager.broadcast_waiting(league_id, payload_disc)


@router.websocket("/ws/league/{league_id}/active")
async def league_active_room_ws(
    websocket: WebSocket,
    league_id: str,
    club_id: str,
    db: Session = Depends(get_db),
):
    await websocket.accept()

    # Validacion de token
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    user = None
    if token:
        try:
            from app.core.security import decode_access_token
            from app.models.auth_session import AuthSession
            from time import time
            claims = decode_access_token(token)
            session = db.get(AuthSession, claims.get("sid"))
            if session and not session.revoked and session.expires_at > time():
                user = db.get(User, claims.get("sub"))
        except Exception:
            pass

    club_obj = db.get(Club, club_id) if club_id else None
    if not user or not club_obj or club_obj.user_id != user.id:
        await websocket.close(code=4008, reason="No autorizado o token inválido.")
        db.close()
        return

    room = db.get(Room, league_id)
    if not room or room.status != ROOM_STATUS_IN_PROGRESS:
        await websocket.close(code=4404, reason="La liga no está activa.")
        db.close()
        return

    enrolled = db.execute(
        select(Enrollment).where(Enrollment.room_id == league_id, Enrollment.club_id == club_id)
    ).scalar_one_or_none() is not None

    if not enrolled:
        await websocket.close(code=4403, reason="El club no pertenece a esta liga.")
        db.close()
        return

    db.close()

    # Registra al cliente
    await league_manager.connect_active(league_id, club_id, websocket)

    # Envia foto inicial al cliente conectado
    initial_payload = get_league_lobby_payload(db, league_id)
    db.close()

    if initial_payload:
        await websocket.send_json(initial_payload)

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("action") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        league_manager.disconnect_active(league_id, club_id)



@router.websocket("/ws/rooms/active")
async def active_rooms_ws(
    websocket: WebSocket,
    db: Session = Depends(get_db)
    ):
    # Validacion de token
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    
    user = None
    if token:
        try:
            from app.core.security import decode_access_token
            from app.models.auth_session import AuthSession
            from time import time
            claims = decode_access_token(token)
            session = db.get(AuthSession, claims.get("sid"))
            if session and not session.revoked and session.expires_at > time():
                user = db.get(User, claims.get("sub"))
        except Exception:
            pass

    if not user or not user.club:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="No autorizado o token invalido.")
        db.close()
        return

    user_id = user.id
    club_id = user.club.id

    # Conectar y enviar listado inicial
    await active_rooms_manager.connect(user_id, websocket)
    await active_rooms_manager.send_active_rooms(user_id, club_id, db, websocket)
    db.close()

    try: 
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        active_rooms_manager.disconnect(user_id, websocket)
