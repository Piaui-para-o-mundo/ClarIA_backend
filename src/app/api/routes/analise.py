
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.process import StatusEnum
from app.services.processo_service import ProcessoService

router = APIRouter(prefix="/api/v1/analise", tags=["analise"])
bearer_scheme = HTTPBearer()


# ─────────────────────────────────────────────────────────────────────────────
# ROTA 1 — Resultado da análise IA (lê do banco, sem chamar o RAG)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/{processo_id}/resultado")
async def get_resultado_ia(
    processo_id: UUID,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna o resultado da análise de IA já salvo no banco de dados.

    Esta rota NÃO chama o RAG. Ela apenas lê o que o BackgroundTask
    persistiu após o upload dos documentos. O frontend deve fazer polling
    nesta rota até receber status 200 com os dados prontos.

    Args:
        processo_id: ID do processo.

    Returns:
        dict: resumo_ia, checklist_ia, despacho_automatico e status do processo.

    Raises:
        HTTPException 404: Processo não encontrado.
        HTTPException 202: Análise ainda em processamento.
    """
    await get_current_user(token.credentials, db)

    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)

    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado",
        )

    # IA ainda não terminou (background task em andamento)
    if not processo.resumo_ia and not processo.checklist_ia:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Análise de IA ainda em processamento. Tente novamente em alguns instantes.",
        )

    return {
        "processo_id": str(processo.id),
        "numero": processo.numero,
        "status": processo.status,
        "resumo_ia": processo.resumo_ia,
        "checklist_ia": processo.checklist_ia,
        "despacho_automatico": processo.despacho_automatico,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ROTA 2 — Avaliador aprova/edita o despacho e conclui o processo
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/{processo_id}/aprovar-despacho")
async def aprovar_despacho(
    processo_id: UUID,
    despacho_editado: str,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """
    Avaliador aprova ou edita o despacho automático e marca o processo como concluído.

    Args:
        processo_id: ID do processo.
        despacho_editado: Texto do despacho (automático ou editado pelo avaliador).

    Returns:
        dict: {"status": "concluido", "processo_id": str}

    Raises:
        HTTPException 404: Processo não encontrado.
    """
    await get_current_user(token.credentials, db)

    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado.",
        )

    processo.despacho_avaliador = despacho_editado

    await ProcessoService.update_status(
        db=db,
        processo_id=processo_id,
        novo_status=StatusEnum.CONCLUIDO,
    )

    await db.commit()

    return {
        "status": "concluido",
        "processo_id": str(processo_id),
    }