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
