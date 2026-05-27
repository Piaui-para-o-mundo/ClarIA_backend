"""
Testes para rotas de autenticação.

Testa registro, login, validação de tokens e recuperação de dados do usuário.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.core.database as _db

# Previne inicialização real do BD durante testes
async def _noop():
    return None

_db.init_db = _noop
_db.close_db = _noop

from src.main import create_app
from app.core.security import hash_password

app = create_app()
client = TestClient(app)


class TestRegister:
    """Testes para endpoint de registro."""
    
    def test_register_success(self):
        """Deve registrar novo usuário com sucesso."""
        payload = {
            "nome": "João Silva",
            "email": "joao@example.com",
            "senha": "senha_forte_123",
            "role": "professor",
            "setor": "Educação"
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "joao@example.com"
        assert data["nome"] == "João Silva"
        assert data["role"] == "professor"
        # Senha não deve ser retornada
        assert "senha" not in data
    
    def test_register_duplicate_email(self):
        """Deve retornar erro ao registrar email duplicado."""
        payload = {
            "nome": "João",
            "email": "duplicate@example.com",
            "senha": "senha_123",
            "role": "professor"
        }
        # Primeiro registro
        client.post("/api/v1/auth/register", json=payload)
        
        # Segundo registro com mesmo email
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 400
        assert "Email já registrado" in response.json()["detail"]
    
    def test_register_missing_fields(self):
        """Deve validar campos obrigatórios."""
        payload = {
            "nome": "José",
            "email": "jose@example.com"
            # Faltam senha e role
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422


class TestLogin:
    """Testes para endpoint de login."""
    
    def test_login_success(self):
        """Deve fazer login com credenciais válidas."""
        # Registra usuário
        register_payload = {
            "nome": "Maria",
            "email": "maria@example.com",
            "senha": "senha_123",
            "role": "professor"
        }
        client.post("/api/v1/auth/register", json=register_payload)
        
        # Faz login
        login_payload = {
            "email": "maria@example.com",
            "senha": "senha_123"
        }
        response = client.post("/api/v1/auth/login", json=login_payload)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_email(self):
        """Deve retornar erro com email inexistente."""
        payload = {
            "email": "inexistente@example.com",
            "senha": "qualquer_senha"
        }
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 401
        assert "Credenciais inválidas" in response.json()["detail"]
    
    def test_login_wrong_password(self):
        """Deve retornar erro com senha incorreta."""
        # Registra usuário
        register_payload = {
            "nome": "Pedro",
            "email": "pedro@example.com",
            "senha": "senha_correta",
            "role": "avaliador"
        }
        client.post("/api/v1/auth/register", json=register_payload)
        
        # Tenta login com senha errada
        login_payload = {
            "email": "pedro@example.com",
            "senha": "senha_errada"
        }
        response = client.post("/api/v1/auth/login", json=login_payload)
        assert response.status_code == 401
        assert "Credenciais inválidas" in response.json()["detail"]
    
    def test_login_inactive_user(self):
        """Deve retornar erro ao logar como usuário inativo."""
        # Implementar quando houver campo ativo no modelo
        pass


class TestGetCurrentUser:
    """Testes para endpoint de dados do usuário logado."""
    
    def test_get_current_user_success(self):
        """Deve retornar dados do usuário autenticado."""
        # Registra e faz login
        register_payload = {
            "nome": "Ana",
            "email": "ana@example.com",
            "senha": "senha_123",
            "role": "professor",
            "setor": "Recursos Humanos"
        }
        client.post("/api/v1/auth/register", json=register_payload)
        
        login_response = client.post("/api/v1/auth/login", json={
            "email": "ana@example.com",
            "senha": "senha_123"
        })
        token = login_response.json()["access_token"]
        
        # Chama endpoint /me
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "ana@example.com"
        assert data["nome"] == "Ana"
        assert data["setor"] == "Recursos Humanos"
    
    def test_get_current_user_without_token(self):
        """Deve retornar erro sem token."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 403
    
    def test_get_current_user_invalid_token(self):
        """Deve retornar erro com token inválido."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code in [401, 403]
