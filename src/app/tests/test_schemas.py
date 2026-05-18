from uuid import uuid4
from app.schemas.auth import UserCreate, UserLogin, UserResponse


def test_user_create_validation():
    u = UserCreate(nome="Alice", email="alice@example.com", senha="password123", role="professor")
    assert u.email == "alice@example.com"


def test_user_response_accepts_uuid():
    ur = UserResponse(id=uuid4(), nome="Bob", email="bob@example.com", role="avaliador", setor=None, ativo=True)
    assert str(ur.id) != ""


def test_user_login_schema():
    cred = UserLogin(email="x@y.com", senha="password123")
    assert cred.email == "x@y.com"
