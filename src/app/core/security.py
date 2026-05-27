from datetime import timedelta, datetime, timezone
from typing import Any, Dict

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings


pwd_context = CryptContext(
    schemes=['bcrypt_sha256'],
    deprecated='auto',
    bcrypt_sha256__rounds=12,
)


def hash_password(password: str) -> str:
    """
    Hash de senha usando bcrypt_sha256.

    Args:
        password: Senha em plaintext.

    Returns:
        str: Hash da senha.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a senha em plaintext corresponde ao hash.

    Args:
        plain_password: Senha em plaintext.
        hashed_password: Hash bcrypt da senha.

    Returns:
        bool: True se a senha for válida, False caso contrário.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    """
     Cria JWT access token.

     Args:
        data: Payload a encodar (ex: {"sub": user_id}).
        expires_delta: Duracao do token. Se None, usa settings.

    Returns:
        str: Token JWT encodado.
    """

    settings = get_settings()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({'exp': expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodifica JWT acess token.

    Args:
        token: Token JWT.
    Returns:
        Dict: Payload decodificado.

    Raises:
        JWTError: Se token for invalido ou expirado.
    """

    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError as e:
        raise JWTError(f'Token inválido ou expirado: {str(e)}')
