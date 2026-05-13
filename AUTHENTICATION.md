# Guia de Autenticação - ClarIA Backend

Este documento descreve o sistema completo de autenticação implementado com FastAPI, JWT e SQLAlchemy.

## 📋 Índice

- [Estrutura](#estrutura)
- [Tecnologias](#tecnologias)
- [Configuração](#configuração)
- [Endpoints](#endpoints)
- [Como Testar](#como-testar)
- [Roles e Permissões](#roles-e-permissões)

---

## 🏗️ Estrutura

```
src/app/
├── api/routes/
│   └── auth.py                 # Endpoints de autenticação
├── core/
│   ├── config.py               # Configurações da aplicação
│   ├── connection.py           # Conexão com banco de dados
│   ├── security.py             # Hash de senha e JWT
│   └── dependencies.py         # Validação de tokens e roles
├── models/
│   └── user.py                 # Modelo User (ORM)
├── schemas/
│   ├── auth.py                 # Schemas de autenticação
│   └── user.py                 # Schemas de usuário
└── services/
    └── auth_service.py         # Lógica de autenticação
```

---

## 🔐 Tecnologias

- **FastAPI**: Framework web assíncrono
- **SQLAlchemy 2.0**: ORM e queries de banco
- **JWT (Python-José)**: Tokens JSON Web Token
- **Passlib + Bcrypt**: Hash seguro de senhas
- **PostgreSQL**: Banco de dados

---

## ⚙️ Configuração

### 1. Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```bash
# Banco de dados
DB_USER=postgres
DB_PASSWORD=sua_senha
DB_HOST=localhost
DB_PORT=5432
DB_NAME=appdb

# API
API_HOST=0.0.0.0
API_PORT=8000

# Segurança (IMPORTANTE: gerar chave segura em produção)
SECRET_KEY=sua-chave-secreta-muito-segura-aqui
```

### 2. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 3. Executar Migrations

```bash
alembic upgrade head
```

---

## 🔌 Endpoints

### POST `/auth/register`

Registra um novo usuário no sistema.

**Request:**
```json
{
  "name": "João Silva",
  "email": "joao@exemplo.com",
  "password": "senha123",
  "role": "professor"
}
```

**Response (201):**
```json
{
  "id": 1,
  "name": "João Silva",
  "email": "joao@exemplo.com",
  "role": "professor",
  "is_active": true,
  "created_at": "2026-05-12T21:50:00"
}
```

---

### POST `/auth/login`

Realiza login e retorna JWT token.

**Request:**
```json
{
  "email": "joao@exemplo.com",
  "password": "senha123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "name": "João Silva",
    "email": "joao@exemplo.com",
    "role": "professor",
    "is_active": true,
    "created_at": "2026-05-12T21:50:00"
  }
}
```

---

### GET `/auth/me`

Retorna dados do usuário autenticado.

**Headers:**
```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

**Response (200):**
```json
{
  "id": 1,
  "name": "João Silva",
  "email": "joao@exemplo.com",
  "role": "professor",
  "is_active": true,
  "created_at": "2026-05-12T21:50:00"
}
```

---

## 🧪 Como Testar

### Usando cURL

```bash
# 1. Registrar novo usuário
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Maria Santos",
    "email": "maria@exemplo.com",
    "password": "senha456",
    "role": "admin"
  }'

# 2. Fazer login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "maria@exemplo.com",
    "password": "senha456"
  }'

# 3. Obter dados do usuário (substituir TOKEN pelo access_token retornado)
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer TOKEN"
```

### Usando Swagger UI

1. Inicie a aplicação:
   ```bash
   uvicorn src.main:app --reload
   ```

2. Acesse: http://localhost:8000/docs

3. Execute os endpoints diretamente na interface

---

## 👥 Roles e Permissões

### Roles Disponíveis

| Role | Descrição | Permissões |
|------|-----------|-----------|
| `admin` | Administrador | Acesso total a recursos administrativos |
| `professor` | Professor | Acesso a rotas pedagógicas e recursos limitados |

### Usando Roles em Rotas

```python
from fastapi import Depends, APIRouter
from app.core.dependencies import require_admin, require_professor_or_admin
from app.models.user import User

router = APIRouter()

# Apenas admin pode acessar
@router.delete("/users/{user_id}")
async def delete_user(user_id: int, current_user: User = Depends(require_admin)):
    # lógica de exclusão
    pass

# Apenas professor e admin
@router.get("/classes")
async def list_classes(current_user: User = Depends(require_professor_or_admin)):
    # listar turmas
    pass
```

---

## 🔑 Fluxo de Autenticação

```mermaid
sequenceDiagram
    participant Cliente
    participant API
    participant DB
    
    Cliente->>API: POST /auth/login (email, senha)
    API->>DB: Buscar usuário por email
    DB-->>API: Usuário encontrado
    API->>API: Verificar senha
    API->>API: Gerar JWT token
    API-->>Cliente: access_token + user data
    
    Cliente->>API: GET /auth/me (com token)
    API->>API: Decodificar JWT
    API->>DB: Buscar usuário pelo ID do token
    DB-->>API: Usuário encontrado
    API-->>Cliente: user data
```

---

## 🛠️ Desenvolvimento

### Estrutura de Componentes

**Model (User.py)**
- Define a tabela de usuários no PostgreSQL
- Campos: id, name, email, hashed_password, role, is_active, created_at

**Service (AuthService)**
- Lógica pura de autenticação
- Métodos: create_user, authenticate_user, login

**Security (security.py)**
- hash_password: criptografa senhas
- verify_password: valida senhas
- create_access_token: gera JWT
- decode_token: valida JWT

**Dependencies (dependencies.py)**
- get_current_user: extrai usuário do token
- require_admin: valida se é admin
- require_professor_or_admin: valida roles

**Routes (auth.py)**
- Endpoints HTTP
- Integra service e schemas

---

## ⚠️ Segurança em Produção

1. **Gerar SECRET_KEY forte:**
   ```python
   import secrets
   print(secrets.token_urlsafe(32))
   ```

2. **Configurar CORS corretamente:**
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://seu-dominio.com"],
       allow_credentials=True,
       allow_methods=["GET", "POST"],
       allow_headers=["*"],
   )
   ```

3. **Usar HTTPS**: Sempre em produção

4. **Validar inputs**: Pydantic já faz isso automaticamente

5. **Rate limiting**: Considerar implementar para endpoints de login

---

## 📚 Referências

- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc7519)
- [Passlib Documentation](https://passlib.readthedocs.io/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/)
