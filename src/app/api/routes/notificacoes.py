"""Rotas de Notificações in-app."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.notificacao import NotificacaoResponse, NotificacaoResumo
from app.services.notificacao_service import NotificacaoService

router = APIRouter(prefix="/api/v1/notificacoes", tags=["notificacoes"])
bearer_scheme = HTTPBearer()


@router.get("/", response_model=NotificacaoResumo)
async def listar_notificacoes(
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    apenas_nao_lidas: bool = False,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    Lista as notificações do usuário logado.

    Args:
        apenas_nao_lidas: Se True, retorna apenas notificações não lidas.
        limit: Limite de resultados.

    Returns:
        NotificacaoResumo: Total de não lidas + lista de notificações.
    """
    user = await get_current_user(token.credentials, db)

    notificacoes = await NotificacaoService.listar(
        db, user.id, apenas_nao_lidas=apenas_nao_lidas, limit=limit
    )
    total_nao_lidas = await NotificacaoService.contar_nao_lidas(db, user.id)

    return NotificacaoResumo(
        total_nao_lidas=total_nao_lidas,
        notificacoes=[NotificacaoResponse.model_validate(n) for n in notificacoes],
    )


@router.patch("/{notificacao_id}/lida")
async def marcar_como_lida(
    notificacao_id: UUID,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """Marca uma notificação como lida."""
    await get_current_user(token.credentials, db)

    notificacao = await NotificacaoService.marcar_como_lida(db, notificacao_id)
    if not notificacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificação não encontrada.",
        )

    await db.commit()
    return {"ok": True, "mensagem": "Notificação marcada como lida."}


@router.patch("/ler-todas")
async def marcar_todas_como_lidas(
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """Marca todas as notificações do usuário como lidas."""
    user = await get_current_user(token.credentials, db)

    quantidade = await NotificacaoService.marcar_todas_como_lidas(db, user.id)
    await db.commit()

    return {"ok": True, "quantidade_lidas": quantidade}
