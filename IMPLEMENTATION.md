# Implementação Completa: Tabela de Usuários, Teste de Conexão e Rota de Login

Este documento contém a implementação completa do código necessário para criar uma tabela de usuários, testar a conexão com o banco PostgreSQL e implementar uma rota de login segura, seguindo princípios de Clean Code e Clean Architecture.

## Estrutura de Arquivos

O código está organizado em seções correspondendo aos arquivos do projeto. Copie o conteúdo de cada seção para o arquivo correspondente.

## 1. Atualizar requirements.txt

Adicione as seguintes dependências ao final do arquivo `requirements.txt`:

```
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0
python-multipart==0.0.6
```

## 2. Corrigir e Integrar Modelo Users (src/app/models/users/users.py)

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from sqlalchemy.ext.declarative import declarative_base
from app.core.connection import Base  # Importar Base centralizado

# Usar Base centralizado de connection.py
# Base = declarative_base()  # Remover esta linha duplicada

class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

## 3. Atualizar connection.py para Teste de Conexão (src/app/core/connection.py)

Adicione ao final do arquivo:

```python
def test_database_connection() -> bool:
    """Testar conexão com o banco de dados.

    Returns:
        bool: True se conexão bem-sucedida, False caso contrário.
    """
    try:
        # Criar uma sessão temporária para teste
        db = SessionLocal()
        db.execute("SELECT 1")  # Query simples para testar conexão
        db.close()
        return True
    except Exception as e:
        print(f"Erro na conexão com o banco: {e}")
        return False
```

## 4. Criar core/security.py (src/app/core/security.py)

```python
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from app.core.config import settings

# Configuração para hashing de senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configurações JWT
SECRET_KEY = "your-secret-key-here"  # Em produção, usar variável de ambiente
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar se a senha plain corresponde ao hash.

    Args:
        plain_password: Senha em texto plano
        hashed_password: Hash da senha armazenada

    Returns:
        bool: True se senha correta
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Gerar hash da senha.

    Args:
        password: Senha em texto plano

    Returns:
        str: Hash da senha
    """
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Criar token de acesso JWT.

    Args:
        data: Dados a incluir no token
        expires_delta: Tempo de expiração opcional

    Returns:
        str: Token JWT
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[str]:
    """Verificar e decodificar token JWT.

    Args:
        token: Token JWT

    Returns:
        Optional[str]: Username se válido, None caso contrário
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None
```

## 5. Criar core/dependencies.py (src/app/core/dependencies.py)

```python
from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from app.core.connection import get_database_session
from app.core.security import SECRET_KEY, ALGORITHM
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_db() -> Generator[Session, None, None]:
    """Dependência para obter sessão do banco de dados.

    Yields:
        Session: Sessão ativa do banco
    """
    db = next(get_database_session())
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Obter usuário atual a partir do token JWT.

    Args:
        token: Token JWT
        db: Sessão do banco

    Returns:
        Users: Usuário autenticado

    Raises:
        HTTPException: Se token inválido ou usuário não encontrado
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_repo = UserRepository(db)
    user = user_repo.get_user_by_email(username)
    if user is None:
        raise credentials_exception
    return user
```

## 6. Criar repositories/user_repository.py (src/app/repositories/user_repository.py)

```python
from typing import Optional
from sqlalchemy.orm import Session
from app.models.users.users import Users

class UserRepository:
    """Repositório para operações CRUD de usuários."""

    def __init__(self, db: Session):
        """Inicializar repositório com sessão do banco.

        Args:
            db: Sessão ativa do banco de dados
        """
        self.db = db

    def get_user_by_email(self, email: str) -> Optional[Users]:
        """Buscar usuário por email.

        Args:
            email: Email do usuário

        Returns:
            Optional[Users]: Usuário encontrado ou None
        """
        return self.db.query(Users).filter(Users.email == email).first()

    def get_user_by_id(self, user_id: int) -> Optional[Users]:
        """Buscar usuário por ID.

        Args:
            user_id: ID do usuário

        Returns:
            Optional[Users]: Usuário encontrado ou None
        """
        return self.db.query(Users).filter(Users.id == user_id).first()

    def create_user(self, name: str, email: str, hashed_password: str) -> Users:
        """Criar novo usuário.

        Args:
            name: Nome do usuário
            email: Email do usuário
            hashed_password: Senha hasheada

        Returns:
            Users: Usuário criado
        """
        db_user = Users(
            name=name,
            email=email,
            hashed_password=hashed_password
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def authenticate_user(self, email: str, password: str) -> Optional[Users]:
        """Autenticar usuário com email e senha.

        Args:
            email: Email do usuário
            password: Senha em texto plano

        Returns:
            Optional[Users]: Usuário se credenciais válidas, None caso contrário
        """
        from app.core.security import verify_password

        user = self.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
```

## 7. Criar schemas/user.py (src/app/schemas/user.py)

```python
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    """Schema base para usuário."""
    name: str
    email: EmailStr

class UserCreate(UserBase):
    """Schema para criação de usuário."""
    password: str

class User(UserBase):
    """Schema para retorno de usuário."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class UserInDB(User):
    """Schema para usuário no banco (com senha hasheada)."""
    hashed_password: str
```

## 8. Criar schemas/auth.py (src/app/schemas/auth.py)

```python
from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    """Schema para requisição de login."""
    email: EmailStr
    password: str

class Token(BaseModel):
    """Schema para resposta de token."""
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Schema para dados do token."""
    email: Optional[str] = None
```

## 9. Criar services/auth_service.py (src/app/services/auth_service.py)

```python
from datetime import timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, User
from app.schemas.auth import LoginRequest, Token

class AuthService:
    """Serviço para lógica de autenticação e usuários."""

    def __init__(self, db: Session):
        """Inicializar serviço com sessão do banco.

        Args:
            db: Sessão ativa do banco de dados
        """
        self.db = db
        self.user_repo = UserRepository(db)

    def authenticate_user(self, login_data: LoginRequest) -> Optional[Token]:
        """Autenticar usuário e gerar token.

        Args:
            login_data: Dados de login (email e senha)

        Returns:
            Optional[Token]: Token se autenticação bem-sucedida, None caso contrário
        """
        user = self.user_repo.authenticate_user(login_data.email, login_data.password)
        if not user:
            return None

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        return Token(access_token=access_token)

    def create_user(self, user_data: UserCreate) -> User:
        """Criar novo usuário.

        Args:
            user_data: Dados do usuário a criar

        Returns:
            User: Usuário criado

        Raises:
            ValueError: Se email já existe
        """
        # Verificar se email já existe
        existing_user = self.user_repo.get_user_by_email(user_data.email)
        if existing_user:
            raise ValueError("Email already registered")

        # Hash da senha
        hashed_password = get_password_hash(user_data.password)

        # Criar usuário
        user = self.user_repo.create_user(
            name=user_data.name,
            email=user_data.email,
            hashed_password=hashed_password
        )

        return User.from_orm(user)
```

## 10. Criar api/routes/auth.py (src/app/api/routes/auth.py)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_db
from app.services.auth_service import AuthService
from app.schemas.auth import LoginRequest, Token

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/login", response_model=Token)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Endpoint para login de usuário.

    Args:
        login_data: Dados de login (email e senha)
        db: Sessão do banco de dados

    Returns:
        Token: Token de acesso JWT

    Raises:
        HTTPException: Se credenciais inválidas
    """
    auth_service = AuthService(db)
    token = auth_service.authenticate_user(login_data)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token
```

## 11. Atualizar main.py (src/main.py)

Substitua o conteúdo completo do arquivo:

```python
"""Aplicação FastAPI principal.

Ponto de entrada da API, configuração inicial e roteamento.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.connection import test_database_connection
from app.api.routes.auth import router as auth_router

app = FastAPI(
    title="ClarIA Backend",
    description="API backend para ClarIA",
    version="1.0.0",
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar origens permitidas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth_router)

@app.on_event("startup")
async def startup_event():
    """Executado na inicialização da aplicação."""
    print("Iniciando aplicação ClarIA Backend...")

    # Testar conexão com o banco
    if test_database_connection():
        print("✅ Conexão com banco de dados estabelecida com sucesso!")
    else:
        print("❌ Falha na conexão com o banco de dados!")
        # Em produção, você pode querer encerrar a aplicação aqui

@app.get("/health")
def health_check() -> dict[str, str]:
    """Verificar saúde da aplicação.

    Returns:
        dict: Status da aplicação.
    """
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
    )
```

## 12. Inicializar Alembic e Criar Migração

Execute os seguintes comandos no terminal (no diretório raiz do projeto):

```bash
# Inicializar Alembic
alembic init alembic

# Editar alembic.ini para configurar a URL do banco
# Adicionar em [alembic]: sqlalchemy.url = postgresql://user:password@host:port/dbname

# Criar migração inicial
alembic revision --autogenerate -m "Create users table"

# Aplicar migração
alembic upgrade head
```

## 13. Arquivo de Ambiente (.env)

Crie um arquivo `.env` na raiz do projeto com:

```
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=claria_db
API_PORT=8000
API_HOST=0.0.0.0
```

## 14. Como Usar

1. Instale as dependências: `pip install -r requirements.txt`
2. Configure o banco PostgreSQL e variáveis de ambiente
3. Execute as migrações Alembic
4. Inicie a aplicação: `python src/main.py`
5. Teste o login: `POST /auth/login` com JSON `{"email": "user@example.com", "password": "password"}`

## 15. Testes

Para testar a implementação:

```bash
# Iniciar aplicação
python src/main.py

# Em outro terminal, testar health check
curl http://localhost:8000/health

# Testar login (credenciais inválidas)
curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "password": "wrong"}'

# Para testar com usuário válido, primeiro crie um usuário no banco
```

Esta implementação segue Clean Architecture com separação clara entre camadas: Models (entidades), Repositories (acesso a dados), Services (lógica de negócio), Schemas (validação), Routes (interface HTTP).</content>
<parameter name="filePath">/home/zenin/Documentos/Desenvolvimento/WORKS/ClarIA_backend/IMPLEMENTATION.md