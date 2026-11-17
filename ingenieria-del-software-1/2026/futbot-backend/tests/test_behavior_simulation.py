from fastapi import status
import pytest
from starlette.websockets import WebSocketDisconnect
from app.routers.behaviors import _ws_tickets
from unittest.mock import patch
import copy
from app.core.config import get_settings

def test_probar_simulacion_comportamiento(client, club_players, auth_headers, comportamiento_prueba):
    player_id = club_players[0].id
    payload = {
        "player_id": club_players[0].id,
        "behavior_id": comportamiento_prueba.id
    }
    response = client.post("/api/behaviors/simulate", json=payload, headers=auth_headers)
    
    # Verifica el contrato
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "ticket" in data
    # verifica que el ticket se haya almacenado en _ws_tickets
    ticket = data["ticket"]
    assert ticket in _ws_tickets
    assert _ws_tickets[ticket]["player_id"] == player_id
    assert _ws_tickets[ticket]["behavior_id"] == comportamiento_prueba.id

def test_crear_ticket_simulacion_invalido(client, auth_headers):
    payload = {
        "player_id": "9999",  # ID de jugador que no existe
        "behavior_id": "1"     
    }
    response = client.post("/api/behaviors/simulate", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Jugador no encontrado o no pertenece al club"

def test_crear_ticket_con_jugador_de_otro_club(client, auth_headers, other_club_players):
    other_player = other_club_players[0]
    payload = {
        "player_id": other_player.id,
        "behavior_id": "1"  # Asumiendo que este comportamiento existe
    }
    response = client.post("/api/behaviors/simulate", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Jugador no encontrado o no pertenece al club"

def test_websocket_rechaza_ticket_invalido(client):
    """Verifica que el WS corte la conexión si el ticket no existe."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/simulate?ticket=ticket-falso"):
            pass 
    assert exc_info.value.code == 4401  

def test_websocket_simulacion_streaming_exitoso(client, add_default_behaviors, auth_headers, club_players, comportamiento_prueba):
    """Flujo completo E2E: Crea ticket, conecta al WS, recibe los ticks de simulación y consume el ticket."""
    add_default_behaviors  # Asegura que los comportamientos por defecto estén en la DB
    player = club_players[0]
    payload = {
        "player_id": player.id,
        "behavior_id": comportamiento_prueba.id
    }
    res = client.post("/api/behaviors/simulate", json=payload, headers=auth_headers)
    ticket = res.json()["ticket"]

    with client.websocket_connect(f"/ws/simulate?ticket={ticket}") as websocket:
        
        # Lee el primer tick enviado por el motor
        primer_tick = websocket.receive_json()
        
        # Valida la estructura devuelta 
        assert primer_tick["type"] == "tick"
        assert "players" in primer_tick
        assert "ball" in primer_tick
        # Extrae al jugador principal del array de players
        jugador_simulado = next(p for p in primer_tick["players"] if p["id"] == player.id)        
        # Valida que los atributos inyectados coinciden con la DB
        assert jugador_simulado["attributes"]["speed"] == player.speed
        assert jugador_simulado["attributes"]["control"] == player.control
        assert jugador_simulado["attributes"]["strength"] == player.strength
        
        # Valida que el jugador inyectado esté en el estado inicial
        jugadores_ids = [p["id"] for p in primer_tick["players"]]
        assert player.id in jugadores_ids
        
        # Lee un segundo tick para confirmar que el bucle while del motor avanza
        segundo_tick = websocket.receive_json()
        assert segundo_tick["type"] == "tick"
        assert len(primer_tick["players"]) == 6
        assert len(segundo_tick["players"]) == 6
        assert primer_tick["ball"]

    assert ticket not in _ws_tickets

def test_websocket_rechaza_ticket_expirado(client, add_default_behaviors, auth_headers, club_players, comportamiento_prueba):
    """Verifica que el WS corte la conexión si el ticket ha expirado."""
    add_default_behaviors
    player = club_players[0]
    payload = {
        "player_id": player.id,
        "behavior_id": comportamiento_prueba.id
    }
    res = client.post("/api/behaviors/simulate", json=payload, headers=auth_headers)
    ticket = res.json()["ticket"]

    # Simula la expiración del ticket
    _ws_tickets[ticket]["expires_at"] = _ws_tickets[ticket]["expires_at"].replace(year=2000)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/simulate?ticket={ticket}") as websocket:
            websocket.receive_text()
    assert exc_info.value.code == 4403
    assert ticket not in _ws_tickets

def test_crear_ticket_con_comportamiento_invalido(client, auth_headers, club_players):
    payload = {
        "player_id": club_players[0].id,
        "behavior_id": "9999"  # ID de comportamiento que no existe
    }
    response = client.post("/api/behaviors/simulate", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_websocket_simulacion_finaliza_por_timeout(client, add_default_behaviors, auth_headers, club_players, comportamiento_prueba):
    """Verifica que tras cumplir el límite de ticks, se envíe el mensaje final y se cierre el motor."""
    add_default_behaviors
    payload = {
        "player_id": club_players[0].id,
        "behavior_id": comportamiento_prueba.id
    }
    res = client.post("/api/behaviors/simulate", json=payload, headers=auth_headers)
    ticket = res.json()["ticket"]
    config_real = copy.copy(get_settings())
        
    # Modifica SOLO lo que se necesita para el timeout
    config_real.match_tick_rate = 0.1
    with patch("app.services.behavior_simulation.get_settings") as mock_settings, \
         patch("app.engine.match_engine.MatchEngine.close") as mock_close:
        
        # Para que el mock use la configuracion clonada
        mock_settings.return_value = config_real
        with client.websocket_connect(f"/ws/simulate?ticket={ticket}") as websocket:
            # Consume los 3 ticks de simulación
            for _ in range(3):
                tick = websocket.receive_json()
                assert tick["type"] == "tick"
            
            # El siguiente mensaje debe ser el de finalización
            final_msg = websocket.receive_json()
            assert final_msg["type"] == "simulation_finished"
            assert final_msg["reason"] == "timeout"
            
        mock_close.assert_called_once()

def test_comportamiento_asignado_modifica_al_jugador(client, add_default_behaviors, auth_headers, club_players, comportamiento_prueba):
    """Verifica que el script custom se ejecuta evaluando el cambio de posición/velocidad."""
    add_default_behaviors 
    player = club_players[0]
    payload = {
        "player_id": player.id,
        "behavior_id": comportamiento_prueba.id
    }
    res = client.post("/api/behaviors/simulate", json=payload, headers=auth_headers)
    ticket = res.json()["ticket"]

    with client.websocket_connect(f"/ws/simulate?ticket={ticket}") as websocket:
        tick_1 = websocket.receive_json()
        tick_2 = websocket.receive_json()
        
        jugador_t1 = next(p for p in tick_1["players"] if p["id"] == player.id)
        jugador_t2 = next(p for p in tick_2["players"] if p["id"] == player.id)
        
        # Si el código se ejecutó, la posición en X en el tick 2 debe ser mayor que en el tick 1
        assert jugador_t2["position"]["x"] != jugador_t1["position"]["x"]