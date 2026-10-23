
def test_registro_usuario_exitoso(client):
    # Usa datos que NO existen en la base
    payload = {
        "username": "nuevo_jugador",
        "email": "nuevo@mail.com",
        "password": "password123",
        "clubName": "Club Nuevo",
        "avatar": "1"
    }

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 201, response.json()
    body = response.json()
    assert "id" in body
    assert body["username"] == "nuevo_jugador"
    assert body["email"] == "nuevo@mail.com"
    assert body["club"]["name"] == "Club Nuevo"

def test_registro_usuario_duplicado_devuelve_409(client, club):
    # Usa el mismo username que el fixture
    payload = {
        "username": "tester",
        "email": "otroemail@mail.com",
        "password": "password123",
        "clubName": "Club Distinto",
        "avatar": None
    }

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "El usuario, email o nombre del club ya existe"