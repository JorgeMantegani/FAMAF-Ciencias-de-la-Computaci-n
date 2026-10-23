from uuid import uuid4

import pytest
from starlette.websockets import WebSocketDisconnect

from app.ws.manager import manager, room_manager
from scripts.demo_match import create_demo, make_tick
from app.services.match_state import publish_match_state


def test_room_connections_and_match_publication_coexist(client, db):
    demo = create_demo(db)
    home_id, away_id = demo.club_ids
    url = f'/ws/friendly/{demo.room_id}'
    with client.websocket_connect(f'{url}?club_id={home_id}') as home:
        assert home.receive_json() == {'type': 'club_connected', 'club_id': home_id}
        with client.websocket_connect(f'{url}?club_id={away_id}') as away:
            event = {'type': 'club_connected', 'club_id': away_id}
            assert home.receive_json() == event
            assert away.receive_json() == event
            assert room_manager.full_room(demo.room_id, 'third-club')
            assert manager is not room_manager
            publish_match_state(db, demo.match_id, make_tick(demo, 1), expected_revision=1)
        # A match snapshot must not be delivered to the room socket.
        assert home.receive_json() == {'type': 'club_disconnected', 'club_id': away_id}
    assert demo.room_id not in room_manager.rooms


@pytest.mark.parametrize('missing_room,code', [(True, 4404), (False, 4403)])
def test_room_socket_rejects_missing_room_or_unenrolled_club(client, db, missing_room, code):
    demo = create_demo(db)
    room_id = str(uuid4()) if missing_room else demo.room_id
    with client.websocket_connect(f'/ws/friendly/{room_id}?club_id={uuid4()}') as socket:
        with pytest.raises(WebSocketDisconnect) as error:
            socket.receive_json()
        assert error.value.code == code
    assert room_id not in room_manager.rooms
