import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, status
from collections import namedtuple

FakePlayerRow = namedtuple("FakePlayerRow", ["name", "id"])

from app.services.friendly_service import FriendlyService, generate_room_code
from app.schemas.friendly_room import CreateFriendlyRoomRequest, PlayerSelection, RoomStatus
from app.models.squad_entry import STARTER_COUNT, SUBSTITUTE_COUNT


# ─── FIXTURES MOCK DE ENTRADA ───

@pytest.fixture
def valid_payload():
    """Genera un payload válido con 3 starters y 3 substitutes."""
    return CreateFriendlyRoomRequest(
        starters=[
            PlayerSelection(player_id=f"p-{i}", behavior_id=f"b-{i}")
            for i in range(1, 4)
        ],
        substitutes=[
            PlayerSelection(player_id=f"p-{i}", behavior_id=f"b-{i}")
            for i in range(4, 7)
        ]
    )


@pytest.fixture
def mock_db():
    """Mock de la sesión de SQLAlchemy."""
    return MagicMock()


# ─── TESTS UNITARIOS DE VALIDACIONES (VALIDATE_PLAYERS_AND_BEHAVIORS) ───

def test_validate_players_and_behaviors_success(mock_db, valid_payload):
    """Verifica que no lance excepciones cuando los datos son válidos."""
    service = FriendlyService(mock_db)
    club_id = "club-123"

    # Mock de respuesta de base de datos para jugadores válidos
    mock_player_results = [FakePlayerRow(name=f"p-{i}", id=f"uuid-{i}") for i in range(1, 7)]
    mock_behavior_results = [MagicMock(id=f"b-{i}") for i in range(1, 7)]

    # Mapeo de llamadas a db.query().filter().all()
    mock_db.query.return_value.filter.return_value.all.side_effect = [
        mock_player_results,
        mock_behavior_results
    ]

    # No debe lanzar ninguna excepción
    service.validate_players_and_behaviors(club_id, valid_payload)


def test_validate_invalid_starter_count(mock_db):
    """Lanza 400 Bad Request si los starters no son exactamente 3."""
    service = FriendlyService(mock_db)
    payload = CreateFriendlyRoomRequest(
        starters=[PlayerSelection(player_id="p-1", behavior_id="b-1")],  # Solo 1
        substitutes=[PlayerSelection(player_id=f"p-{i}", behavior_id="b-1") for i in range(2, 5)]
    )

    with pytest.raises(HTTPException) as exc_info:
        service.validate_players_and_behaviors("club-123", payload)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "titulares" in exc_info.value.detail.lower()


def test_validate_invalid_substitute_count(mock_db):
    """Lanza 400 Bad Request si los substitutes no son exactamente 3."""
    service = FriendlyService(mock_db)
    payload = CreateFriendlyRoomRequest(
        starters=[PlayerSelection(player_id=f"p-{i}", behavior_id="b-1") for i in range(1, 4)],
        substitutes=[]  # 0 substitutes
    )

    with pytest.raises(HTTPException) as exc_info:
        service.validate_players_and_behaviors("club-123", payload)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "suplentes" in exc_info.value.detail.lower()


def test_validate_duplicate_players_in_payload(mock_db):
    """Lanza 400 Bad Request si un jugador está repetido en el payload."""
    service = FriendlyService(mock_db)
    payload = CreateFriendlyRoomRequest(
        starters=[
            PlayerSelection(player_id="player-repetido", behavior_id="b-1"),
            PlayerSelection(player_id="p-2", behavior_id="b-2"),
            PlayerSelection(player_id="p-3", behavior_id="b-3"),
        ],
        substitutes=[
            PlayerSelection(player_id="player-repetido", behavior_id="b-4"),  # Repetido
            PlayerSelection(player_id="p-5", behavior_id="b-5"),
            PlayerSelection(player_id="p-6", behavior_id="b-6"),
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        service.validate_players_and_behaviors("club-123", payload)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "mismo jugador" in exc_info.value.detail.lower()


def test_validate_players_not_belonging_to_club(mock_db, valid_payload):
    """Lanza 400 Bad Request si la DB retorna menos jugadores válidos que los solicitados."""
    service = FriendlyService(mock_db)

    # Simular que solo 5 de los 6 jugadores pertenecen al club
    mock_player_results = [MagicMock(id=f"p-{i}") for i in range(1, 6)]
    mock_db.query.return_value.filter.return_value.all.return_value = mock_player_results

    with pytest.raises(HTTPException) as exc_info:
        service.validate_players_and_behaviors("club-123", valid_payload)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "no pertenece a tu club" in exc_info.value.detail.lower()


def test_validate_invalid_behaviors(mock_db, valid_payload):
    """Lanza 400 Bad Request si un comportamiento no pertenece al club ni es preprogramado."""
    service = FriendlyService(mock_db)

    mock_player_results = [FakePlayerRow(name=f"p-{i}", id=f"uuid-{i}") for i in range(1, 7)]
    # Solo 4 comportamientos resultan válidos en DB
    mock_behavior_results = [MagicMock(id=f"b-{i}") for i in range(1, 5)]

    mock_db.query.return_value.filter.return_value.all.side_effect = [
        mock_player_results,
        mock_behavior_results
    ]

    with pytest.raises(HTTPException) as exc_info:
        service.validate_players_and_behaviors("club-123", valid_payload)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "comportamiento" in exc_info.value.detail.lower()


# ─── TESTS UNITARIOS DE CREACIÓN DE SALA (CREATE_ROOM) ───

@patch("app.services.friendly_service.generate_room_code", return_value="ROOM12")
def test_create_room_unit_success(mock_code, mock_db, valid_payload):
    """Verifica que create_room cree y persista los objetos en la DB correctamente."""
    service = FriendlyService(mock_db)
    
    # Mockear la validación previa para aislar el test de creación
    service.validate_players_and_behaviors = MagicMock()

    # Mock de colisión de código: primero None (no existe en DB)
    mock_db.query.return_value.filter.return_value.first.return_value = None

    # Asignar un ID ficticio al new_room cuando se ejecuta db.flush
    def fake_flush():
        # Busca el objeto Room que fue agregado a la DB y le asigna un ID
        for call in mock_db.add.call_args_list:
            obj = call[0][0]
            if hasattr(obj, "id") and getattr(obj, "id") is None:
                obj.id = "room-uuid-123"

    mock_db.flush.side_effect = fake_flush

    club_id = "club-unit-test"
    result = service.create_room(club_id, valid_payload)

    # 1. Validar llamada a validación
    service.validate_players_and_behaviors.assert_called_once_with(club_id, valid_payload)

    # 2. Validar llamadas a la sesión de SQLAlchemy
    assert mock_db.add.call_count == 8  # 1 Room + 1 Enrollment + 6 SquadEntries
    mock_db.flush.assert_called_once()
    mock_db.commit.assert_called_once()

    # 3. Validar respuesta del servicio
    assert result.room_id == "room-uuid-123"
    assert result.room_code == "ROOM12"
    assert result.status == RoomStatus.WAITING_GUEST.value
    assert result.home_club == club_id


def test_generate_room_code_format():
    """Prueba unitaria auxiliar para la función generadora de códigos."""
    code = generate_room_code(length=6)
    assert len(code) == 6
    assert code.isalnum()
    assert code.isupper()