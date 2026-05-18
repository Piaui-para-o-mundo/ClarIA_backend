
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    status,    
)

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.schemas.processo import (
    ProcessoCreate,
    ProcessoResponse,
    ProcessoResumo,
)

from app.services.processo_service import ProcessoService
from app.services.rag_service import RagClient, get_rag_client

router = APIRouter(prefix="/api/v1/processos", tags=["processos"])
bearer_scheme = HTTPBearer()

@router.post("/", response_model=ProcessoResponse)
async def criar_processo(
    processo_data: ProcessoCreate,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """
    Cria novo processo (professor).
    
    Args:
        processo_data: Tipo de processo.
        token: JWT.
        db: Sessão de banco.
        
    Returns:
        ProcessoResponse: Processo criado.
    """
    user = await get_current_user(token.credentials, db)

    processo = await ProcessoService.criar_processo(
        db=db,
        user=user,
        tipo=processo_data.tipo,
    )
    await db.commit()

    return ProcessoResponse.from_orm(processo)


@router.get("", response_model=list[ProcessoResumo])
async def listar_processos(
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """
    Lista todos os processos (avaliador).
    
    Args:
        skip: Offset de paginação.
        limit: Limite de resultados.
        
    Returns:
        list[ProcessoResumo]: Processos resumidos.
    """
    processos = await ProcessoService.listar_processos(
        db=db,
        skip=skip,
        limit=limit,
    )

    return [ProcessoResumo.from_orm(p) for p in processos]

@router.get("/my", response_model=list[ProcessoResumo])
async def list_my_processos(
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
): 
    """
    Lista processos do professor logado.

    Args:
        skip: Offset de paginação.
        limit: Limite de resultados.

    Returns:
        list[ProcessoResumo]: Processos resumidos do professor.
    """

    user = await get_current_user(token.credentials, db)

    processos = await ProcessoService.listar_processos_user(
        db=db,
        usuario_id=user.id,
        skip=skip,
        limit=limit,
    )

    return [ProcessoResumo.from_orm(p) for p in processos]

@router.get("/{processo_id}", response_model=ProcessoResponse)
async def get_processo(
    processo_id: UUID,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna detalhes de um processo.
    
    Args:
        processo_id: ID do processo.
        
    Returns:
        ProcessoResponse: Processo com documentos.
        
    Raises:
        HTTPException: Se processo não encontrado.
    """
    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)

    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado",
        )

    return ProcessoResponse.from_orm(processo)


@router.post("/{processo_id}/documentos")
async def upload_documentos(
    processo_id: UUID,
    background_tasks: BackgroundTasks,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    arquivos: list[str] = Form(...),
    tipos_doc: list[str] = Form(...),
    db: AsyncSession = Depends(get_db),
    rag_client: RagClient = Depends(get_rag_client),
):
    """
    Upload de multiplos documentos  para um processo.
    
    Após upload, dispara background task para verificar conformidade via RAG.
    
    Args:
        processo_id: ID do processo.
        arquivos: Lista de arquivos (multipart/form-data).
        tipos_doc: Lista de tipos (requerimento, cpf, etc.) em mesmo ordem.
        background_tasks: Task runner.
        
    Returns:
        dict: {"sucesso": int, "falhas": int}
    """

    user = await get_current_user(token.credentials, db)

    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo or getattr(processo, "usuario_id", None) != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado ou acesso negado",
        )
    
    if len(arquivos) != len(tipos_doc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Número de arquivos nao coincide com tipos",
        )
    
    sucesso = 0
    for arquivo_texto, tipo_doc in zip(arquivos, tipos_doc):
        try:
            arquivo_bytes = arquivo_texto.encode("latin-1")
            await ProcessoService.save_documento(
                db=db,
                processo_id=processo_id,
                tipo_doc=tipo_doc,
                arquivo_bytes=arquivo_bytes,
                name_arquivo=f"{tipo_doc}.pdf",
            )
            sucesso += 1
        except Exception as e:
            print(f"Erro ao salvar documento {tipo_doc}: {e}")
            continue

    
    await db.commit()

    background_tasks.add_task(
        _verificar_conformidade_background,
        db=db,
        processo_id=processo_id,
        rag_client=rag_client,
    )    
    return {"sucesso": sucesso, "falhas": len(arquivos) - sucesso}



@router.patch("/{processo_id}/status", response_model=ProcessoResponse)
async def update_status_processo(
    processo_id: UUID,
    new_state: str,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """
    Atualiza Status do processo (avaliador).

    Args: 
        processo_id: ID do processo.
        new_state: Novo status (em_analise, aprovado, reprovado).
        
    Returns:
        ProcessoResponse: Processo atualizado.
    """
    from app.models.process import StatusEnum

    try:
        status_enum = StatusEnum(new_state)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status inválido: {new_state}",
        )
    
    processo = await ProcessoService.update_status(
        db=db,
        processo_id=processo_id,
        novo_status=status_enum,
    )

    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado",
        )
    
    await db.commit()

    return ProcessoResponse.from_orm(processo)


async def _verificar_conformidade_background(
    db: AsyncSession,
    processo_id: UUID,
    rag_client: RagClient,
):
    """
    Task de background para verificar conformidade via RAG.
    
    Args:
        db: Sessão de banco.
        processo_id: ID do processo.
        rag_client: Cliente RAG.
    """
    try:
        from app.models.process import StatusEnum

        texto = await ProcessoService.get_documentos_text_concatenado(db=db, processo_id=processo_id)

        if not texto:
            return
        
        result = await rag_client.verificar_conformidade(
            texto_documento=texto,
            tipo_processo="tipo_processo",
        )

        conformidade = result.get("conformidade_pct", 0)
        pendencias = result.get("pendencias", [])


        if conformidade < 100:
            despacho = await rag_client.sugerir_despacho(
                texto_documento=texto,
                pendencias=", ".join(pendencias),
            )
            
            await ProcessoService.save_despacho_automatico(
                db=db,
                processo_id=processo_id,
                despacho=despacho.get("despacho", ""),
            )
            
            await ProcessoService.update_status(
                db=db,
                processo_id=processo_id,
                novo_status=StatusEnum.PENDENTE_PROFESSOR,
            )
        else:
            await ProcessoService.update_status(
                db=db,
                processo_id=processo_id,
                novo_status=StatusEnum.ANALISE_PENDENTE,
            )
        
        await db.commit()
    except Exception as e:
        print(f"Erro em background task: {e}")
        