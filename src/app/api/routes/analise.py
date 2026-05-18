
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.processo_service import ProcessoService
from app.services.rag_service import RagClient, get_rag_client

router = APIRouter(prefix="/api/v1/analise", tags=["analise"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")



@router.get("/{processo_id}/resumo")
async def get_resumo(
    processo_id: str,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db),
    rag_client: Annotated[RagClient, Depends(get_rag_client)] = None,
):
    """
    Gera resumo do processo usando RAG.

    args:
        processo_id: ID do processo.
    
    Returns:
        dict: {"resumo": str, "palavra_chave": list[str]}
    """

    user = await get_current_user(token, db)

    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)

    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado",
        )
    
    texto = await ProcessoService.get_documentos_text_concatenado(
        db=db,
        processo_id=processo_id,
    )

    if not texto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum documento encontrado para o processo",
        )
    
    result = await rag_client.gerar_resumo(texto)
    return result

@router.get("/{processo_id}/conformidade")
async def get_conformidade(
    processo_id: str,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db),
    rag_client: RagClient = Depends(get_rag_client),
):
    """
    Verifica conformidade do processo.
    
    Args:
        processo_id: ID do processo.
        
    Returns:
        dict: {"conformidade_pct": float, "pendencias": list[str]}
    """

    usuario = await get_current_user(token, db)
    
    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado.",
        )
    
    texto = await ProcessoService.get_documentos_texto_concatenado(
        db=db,
        processo_id=processo_id,
    )
    
    resultado = await rag_client.verificar_conformidade(
        texto_documento=texto,
        tipo_processo=processo.tipo,
    )
    return resultado

@router.get("/{processo_id}/despacho")
async def gerar_despacho(
    processo_id: str,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db),
    rag_client: RagClient = Depends(get_rag_client),
):
    """
    Gera sugestão de despacho via RAG.
    
    Args:
        processo_id: ID do processo.
        
    Returns:
        dict: {"despacho": str, "motivo": str}
    """

    user = await get_current_user(token, db)

    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado.",
        )

    texto = await ProcessoService.get_documentos_text_concatenado(
        db=db,
        processo_id=processo_id,
    )

    result = await rag_client.sugerir_despacho(
        texto_documento=texto,
        pendencias="", # TODO: passar pendências reais
    )

    return result

@router.post("/{processo_id}/aprovar-despacho")
async def aprovar_despacho(
    processo_id: str,
    despacho_editado: str,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Aprova/edita despacho e marca processo como concluído.
    
    Args:
        processo_id: ID do processo.
        despacho_editado: Texto do despacho (pode ser editado).
        
    Returns:
        dict: {"status": "concluido"}
    """

    from app.models.process import StatusEnum

    user = await get_current_user(token, db)

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
        novo_status=StatusEnum.concluido,
    )

    await db.commit()

    return {"status": "concluido"}