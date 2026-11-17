import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.routers.behaviors import _ws_tickets
from app.services.behavior_simulation import run_simulation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["behavior_simulation"])

@router.websocket("/simulate")
async def ws_simulate_behavior(
    websocket: WebSocket,
    ticket: str,
    db: Session = Depends(get_db),
):
  ticket_data = _ws_tickets.pop(ticket, None)
  if not ticket_data:
    await websocket.close(code=4401, reason="Ticket is invalid")  # Policy Violation
    return
  
  user_id = ticket_data["user_id"]
  await websocket.accept()

  try:
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.club:
      await websocket.close(code=4403, reason="User not found or club not found")  # Policy Violation
      return

    if ticket_data["expires_at"] < datetime.now(timezone.utc):
      await websocket.close(code=4403, reason="Ticket has expired")  # Policy Violation
      return
    
    club_id = user.club.id
    # Funcion puente para el motor
    async def send_tick(snapshot: dict):
      await websocket.send_json(snapshot)
    
    await run_simulation(
      db=db,
      player_id=ticket_data["player_id"],
      behavior_id=ticket_data["behavior_id"],
      club_id=club_id,
      send_tick_callback=send_tick
    )
    # Si la simulación termina normalmente, enviamos un mensaje final
    await websocket.send_json({"type": "simulation_finished", "reason": "timeout"})
  except WebSocketDisconnect:
    logger.info("WebSocket disconnected")
  except ValueError as e:
    logger.error(f"Simulation error: {e}")
    await websocket.send_json({"type": "error", "status": 404, "message": str(e)})
    await websocket.close(code=4404, reason=str(e))  # Not Found
  except Exception as e:
    logger.exception("Unexpected error during simulation")
    await websocket.send_json({"type": "error", "status": 500, "message": "Unexpected error occurred"})
    await websocket.close(code=1011, reason="Unexpected error")  # Internal Error
