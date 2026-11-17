from fastapi import status
from app.main import app
from app.core.dependencies import get_current_user
from app.models import Behavior

# 1. Test: Rechazo con código 401 ante token inexistente
def test_consulta_behaviors_sin_token(client):
    response = client.get("/api/behaviors")
    assert response.status_code == 401
    assert response.json()["detail"] == "Sesión inválida o vencida"

# 2. Test: Rechazo con código 401 ante token inválido
def test_consulta_behaviors_con_token_invalido(client):
    token_invalido = "token_invalido"
    response = client.get("/api/behaviors", headers={"Authorization": f"Bearer {token_invalido}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Sesión inválida o vencida"


# 3. Test: Consulta exitosa con token válido
def test_consulta_behaviors_con_token_valido(client, club, db):
    # Crea el comportamiento
    behavior_test = Behavior(
        name="Defensa fuerte",
        code="def run(): pass",
        club_id=club.id
    )
    db.add(behavior_test)
    db.commit()

    def usuario_autenticado():
        return club.user
    # Le dice a la app que reemplace la seguridad real por la función falsa
    app.dependency_overrides[get_current_user] = usuario_autenticado
    
    try:
        # Ejecuta la consulta con el token válido (simulado)
        response = client.get("/api/behaviors")
        
        # Verifica el contrato
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

        assert len(data) > 0, "Se esperaba al menos un comportamiento en la respuesta"
        assert "id" in data[0]
        assert "name" in data[0]
        assert "code" in data[0]
        assert "isDefault" in data[0]
            
        # Asegura que NO se filtren datos privados
        assert "description" not in data[0]
        assert "club_id" not in data[0]
            
    finally:
            app.dependency_overrides.clear()

def test_crear_comportamiento_exitoso(client, club, db, auth_headers):
    payload = {
        "name": "Comportamiento de prueba",
        "code": "def behavior(player):\n    player.correr((10, 10))"
    }
    response = client.post("/api/behaviors", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["code"] == payload["code"]
    assert data["isDefault"] is False

    # Verifica que el comportamiento se haya guardado en la base de datos
    behavior_in_db = db.query(Behavior).filter_by(id=data["id"]).first()
    assert behavior_in_db is not None
    assert behavior_in_db.name == payload["name"]
    assert behavior_in_db.code == payload["code"]
    assert behavior_in_db.club_id == club.id
    assert behavior_in_db.is_preprogrammed is False


def test_crear_comportamiento_malicioso_devuelve_422(client, auth_headers):
    payload = {
        "name":"Estrategia Hack",
        "code": "import os\ndef behavior(player):\n    pass"
    }
    response = client.post("/api/behaviors", json=payload, headers=auth_headers)
    assert response.status_code == 422
    assert "detail" in response.json()

def test_crear_comportamiento_duplicado_devuelve_409(client, club, db, auth_headers):
    # Crea un comportamiento inicial
    behavior_test = Behavior(
        name="Comportamiento Duplicado",
        code="def behavior(player): pass",
        club_id=club.id
    )
    db.add(behavior_test)
    db.commit()

    payload = {
        "name": "Comportamiento Duplicado",
        "code": "def behavior(player): pass"
    }
    response = client.post("/api/behaviors", json=payload, headers=auth_headers)
    assert response.status_code == 409
    assert "detail" in response.json()

def test_crear_comportamiento_con_bucle_infinito(client, club,db, auth_headers):
    payload = {
        "name":"Estrategia Infinita",
        "code": "def behavior(player):\n    while True:\n        player.correr((10, 10))"
    }
    response = client.post("/api/behaviors", json=payload, headers=auth_headers)
    assert response.status_code == 422
    assert "detail" in response.json()

def test_crear_comportamiento_con_campos_extra_devuelve_422(client, club, db, auth_headers):
    payload = {
        "name": "Comportamiento con campos extra",
        "code": "def behavior(player): pass",
        "admin": True
    }
    response = client.post("/api/behaviors", json=payload, headers=auth_headers)
    assert response.status_code == 422
    assert "detail" in response.json()

def test_editar_comportamiento_exitoso(client, club, db, auth_headers):
    # Crea un comportamiento inicial
    behavior_test = Behavior(
        name="Comportamiento a Editar",
        code="def behavior(player): pass",
        club_id=club.id
    )
    db.add(behavior_test)
    db.commit()

    payload = {
        "name": "Comportamiento Editado",
        "code": "def behavior(player):\n    player.correr((0,0))"
    }
    response = client.put(f"/api/behaviors/{behavior_test.id}", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["code"] == payload["code"]

    # Verifica que el comportamiento se haya actualizado en la base de datos
    behavior_in_db = db.query(Behavior).filter_by(id=behavior_test.id).first()
    assert behavior_in_db.name == payload["name"]
    assert behavior_in_db.code == payload["code"]
    assert behavior_in_db.club_id == club.id
    assert behavior_in_db.is_preprogrammed is False
    
def test_editar_comportamiento_de_otro_club_devuelve_404(client, club, db, other_club, auth_headers):
    # Crea un comportamiento en otro club
    behavior = Behavior(
        name="Comportamiento de Otro Club",
        code="def behavior(player): pass",
        club_id=other_club.id
    )
    db.add(behavior)
    db.commit()
    db.refresh(behavior)

    payload = {
        "name": "Intento de Edición",
        "code": "def behavior(player):\n    player.correr((0,0))"
    }
    response = client.put(f"/api/behaviors/{behavior.id}", json=payload, headers=auth_headers)
    assert response.status_code == 404
    assert "detail" in response.json()

def test_editar_comportamiento_inexistente_devuelve_404(client, auth_headers):
    response = client.put("/api/behaviors/nonexistent-id", json={
        "name": "Nuevo Nombre",
        "code": "def behavior(player): pass"
    }, headers=auth_headers)
    assert response.status_code == 404
    assert "detail" in response.json()

def test_crear_comportamiento_con_sintaxis_invalida_devuelve_422(client, auth_headers):
    response = client.post("/api/behaviors", json={
        "name": "Sintaxis invalida",
        "code": "def behavior(player):"
    }, headers=auth_headers)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_editar_comportamiento_con_sintaxis_invalida_devuelve_422(client, club, db, auth_headers):
    # Creo comportamiento para despues editarlo
    behavior = Behavior(
        name="Comportamiento editable",
        code="def behavior(player): pass",
        club_id=club.id,
    )
    db.add(behavior)
    db.commit()
    db.refresh(behavior)

    response = client.put(f"/api/behaviors/{behavior.id}", json={
        "name": "Sintaxis invalida",
        "code": "def behavior(player):"
    }, headers=auth_headers)
    assert response.status_code == 422
    assert "detail" in response.json()
    # Compruebo que no se cambio
    db.refresh(behavior)
    assert behavior.code == "def behavior(player): pass"

def test_crear_comportamiento_con_metodo_inventado_devuelve_422(client, auth_headers):
    response = client.post("/api/behaviors", json={
        "name": "Metodo inventado",
        "code": "def behavior(player):\n    player.volar((10, 10))"
    }, headers=auth_headers)
    assert response.status_code == 422
    assert "detail" in response.json()