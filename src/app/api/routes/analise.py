
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.process import AnaliseStatusEnum, StatusEnum
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

    analise_status = processo.analise_status or AnaliseStatusEnum.PENDING.value

    if analise_status == AnaliseStatusEnum.ERROR.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "mensagem": "A análise de IA falhou para este processo.",
                "analise_status": analise_status,
                "analise_erro": processo.analise_erro,
            },
        )

    # IA ainda não terminou (background task em andamento)
    if not processo.resumo_ia and not processo.checklist_ia:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail={
                "mensagem": "Análise de IA ainda em processamento. Tente novamente em alguns instantes.",
                "analise_status": analise_status,
            },
        )

    return {
        "processo_id": str(processo.id),
        "numero": processo.numero,
        "status": processo.status,
        "analise_status": analise_status,
        "analise_erro": processo.analise_erro,
        "resumo_ia": processo.resumo_ia,
        "checklist_ia": processo.checklist_ia,
        "despacho_automatico": processo.despacho_automatico,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ROTA 2 — Geração de Resumo sob demanda
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/{processo_id}/gerar-resumo")
async def gerar_resumo(
    processo_id: UUID,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """
    Gera o resumo executivo sob demanda.
    Requer que a análise de conformidade já tenha sido concluída.

    Args:
        processo_id: ID do processo.

    Returns:
        dict: O resumo_ia gerado.

    Raises:
        HTTPException 404: Processo não encontrado.
        HTTPException 400: Se a conformidade ainda não foi processada.
        HTTPException 500: Se houver falha na comunicação com a IA.
    """
    await get_current_user(token.credentials, db)

    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado.",
        )

    if not processo.checklist_ia:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A análise de conformidade ainda não foi concluída. Aguarde o processamento automático.",
        )

    from app.core.config import get_settings
    from app.services.rag_service import RagClient
    from app.services.analise_service import AnaliseService

    settings = get_settings()
    rag_client = RagClient(
        base_url=settings.rag_service_url,
        timeout=settings.rag_service_timeout,
    )

    try:
        processo_atualizado = await AnaliseService.gerar_resumo(
            db=db,
            processo_id=processo_id,
            rag_client=rag_client,
        )
        if not processo_atualizado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Processo não encontrado.",
            )
        return {
            "processo_id": str(processo_atualizado.id),
            "resumo_ia": processo_atualizado.resumo_ia,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao gerar resumo: {str(e)}")
    finally:
        await rag_client.close()

# ─────────────────────────────────────────────────────────────────────────────
# ROTA 3 — Geração de Despacho sob demanda
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/{processo_id}/gerar-despacho")
async def gerar_despacho(
    processo_id: UUID,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """
    Gera a sugestão de despacho sob demanda.
    Requer que a análise de conformidade já tenha sido concluída.

    Args:
        processo_id: ID do processo.

    Returns:
        dict: O despacho_automatico gerado.

    Raises:
        HTTPException 404: Processo não encontrado.
        HTTPException 400: Se a conformidade ainda não foi processada.
        HTTPException 500: Se houver falha na comunicação com a IA.
    """
    await get_current_user(token.credentials, db)

    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado.",
        )

    if not processo.checklist_ia:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A análise de conformidade ainda não foi concluída. Aguarde o processamento automático.",
        )

    from app.core.config import get_settings
    from app.services.rag_service import RagClient
    from app.services.analise_service import AnaliseService

    settings = get_settings()
    rag_client = RagClient(
        base_url=settings.rag_service_url,
        timeout=settings.rag_service_timeout,
    )

    try:
        processo_atualizado = await AnaliseService.gerar_despacho(
            db=db,
            processo_id=processo_id,
            rag_client=rag_client,
        )
        if not processo_atualizado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Processo não encontrado.",
            )
        return {
            "processo_id": str(processo_atualizado.id),
            "despacho_automatico": processo_atualizado.despacho_automatico,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao gerar despacho: {str(e)}")
    finally:
        await rag_client.close()


# ─────────────────────────────────────────────────────────────────────────────
# ROTA 4 — Avaliador aprova/edita o despacho e conclui o processo
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