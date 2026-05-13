"""Funções de segurança: hash de senha e tokens JWT.

Módulo centralizado para gerenciar criptografia de senha
e geração/validação de tokens JWT.
"""

from datetime import datetime, timedelta
from typing import Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from app.core.config import settings

# Configuração de contexto para hash de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configurações de JWT
SECRET_KEY = settings.SECRET_KEY or "sua-chave-secreta-muito-segura-aqui"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def hash_password(password: str) -> str:
    """
    Gera hash de uma senha usando bcrypt.

    Args:
        password: Senha em texto plano.

    Returns:
        str: Hash da senha.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se uma senha em texto plano corresponde ao hash.

    Args:
        plain_password: Senha em texto plano.
        hashed_password: Hash armazenado no banco.

    Returns:
        bool: True se a senha está correta, False caso contrário.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Cria um JWT token com os dados fornecidos.

    Args:
        data: Dicionário com dados a serem codificados no token.
        expires_delta: Tempo de expiração personalizado (padrão: 30 minutos).

    Returns:
        str: Token JWT codificado.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    """
    Decodifica um JWT token e retorna os dados.

    Args:
        token: Token JWT a ser decodificado.

    Returns:
        dict: Dados decodificados do token, ou None se inválido/expirado.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
