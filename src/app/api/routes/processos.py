
from typing import Annotated
from uuid import UUID
import asyncio

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,    
)

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.processo import (
    AnaliseStatusResponse,
    ProcessoCreate,
    ProcessoResponse,
    ProcessoResumo,
)

from app.models.process import AnaliseStatusEnum, StatusEnum
from app.services.analise_service import AnaliseService
from app.services.processo_service import ProcessoService

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

    if "documentos" not in processo.__dict__:
        set_committed_value(processo, "documentos", [])

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
    arquivos: list[UploadFile] = File(...),
    tipos_doc: list[str] = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload de múltiplos documentos para um processo com suporte a paralelismo.
    
    Aceita múltiplos arquivos que são processados em paralelo para melhor performance.
    Após upload, dispara background task para verificar conformidade via RAG.
    
    Args:
        processo_id: ID do processo.
        arquivos: Lista de arquivos (multipart/form-data).
        tipos_doc: Lista de tipos (requerimento, cpf, etc.) em mesmo ordem que arquivos.
        background_tasks: Task runner para background processing.
        token: Token JWT de autenticação.
        db: Sessão de banco de dados.
        rag_client: Cliente RAG para análise.
        
    Returns:
        dict: {"sucesso": int, "falhas": int, "detalhes": list[dict]}
        
    Raises:
        HTTPException: Se processo não encontrado ou acesso negado.
        HTTPException: Se número de arquivos não coincide com tipos.
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
            detail=f"Número de arquivos ({len(arquivos)}) não coincide com tipos ({len(tipos_doc)})",
        )
    
    # Processa upload de documentos em paralelo
    async def processar_documento(arquivo: UploadFile, tipo_doc: str, idx: int):
        """Processa um único documento de forma assíncrona."""
        try:
            # Lê conteúdo do arquivo
            arquivo_bytes = await arquivo.read()
            
            # Valida tamanho (máx 50MB)
            if len(arquivo_bytes) > 50 * 1024 * 1024:
                return {
                    "indice": idx,
                    "tipo": tipo_doc,
                    "nome": arquivo.filename,
                    "sucesso": False,
                    "erro": "Arquivo muito grande (máximo 50MB)"
                }
            
            # Salva documento
            await ProcessoService.save_documento(
                db=db,
                processo_id=processo_id,
                tipo_doc=tipo_doc,
                arquivo_bytes=arquivo_bytes,
                name_arquivo=arquivo.filename or f"{tipo_doc}.pdf",
            )
            
            return {
                "indice": idx,
                "tipo": tipo_doc,
                "nome": arquivo.filename,
                "sucesso": True,
                "erro": None
            }
        except Exception as e:
            return {
                "indice": idx,
                "tipo": tipo_doc,
                "nome": arquivo.filename,
                "sucesso": False,
                "erro": str(e)
            }
        finally:
            # Fecha arquivo
            await arquivo.close()
    
    # Executa upload de todos os documentos em paralelo
    tasks = [
        processar_documento(arquivo, tipo, idx)
        for idx, (arquivo, tipo) in enumerate(zip(arquivos, tipos_doc))
    ]
    
    resultados = await asyncio.gather(*tasks)
    
    # Conta sucessos e falhas
    sucesso = sum(1 for r in resultados if r["sucesso"])
    falhas = len(resultados) - sucesso

    if sucesso > 0:
        await ProcessoService.update_status(
            db=db,
            processo_id=processo_id,
            novo_status=StatusEnum.ANALISE_PENDENTE,
        )
    
    # Commit no banco
    await db.commit()

    if sucesso > 0:
        background_tasks.add_task(
            AnaliseService.disparar_analise_em_background,
            processo_id,
        )
    
    return {
        "sucesso": sucesso,
        "falhas": falhas,
        "detalhes": resultados
    }



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


@router.get("/{processo_id}/analise", response_model=AnaliseStatusResponse)
async def get_status_analise(
    processo_id: UUID,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """Retorna o status atual da análise automática do processo."""

    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado",
        )

    return AnaliseStatusResponse(
        processo_id=processo.id,
        analise_status=processo.analise_status,
        status=processo.status,
        analise_started_em=processo.analise_started_em,
        analise_concluida_em=processo.analise_concluida_em,
        analise_erro=processo.analise_erro,
        analise_log=processo.analise_log,
        resumo_ia=processo.resumo_ia,
        checklist_ia=processo.checklist_ia,
        despacho_automatico=processo.despacho_automatico,
    )


@router.post("/{processo_id}/analise", response_model=AnaliseStatusResponse)
async def iniciar_analise_processo(
    processo_id: UUID,
    background_tasks: BackgroundTasks,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """Dispara a análise automática sem duplicar execuções."""

    processo = await ProcessoService.get_processo(db=db, processo_id=processo_id)
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado",
        )

    if processo.analise_status in {
        AnaliseStatusEnum.PROCESSING.value,
        AnaliseStatusEnum.COMPLETED.value,
    }:
        return AnaliseStatusResponse(
            processo_id=processo.id,
            analise_status=processo.analise_status,
            status=processo.status,
            analise_started_em=processo.analise_started_em,
            analise_concluida_em=processo.analise_concluida_em,
            analise_erro=processo.analise_erro,
            analise_log=processo.analise_log,
            resumo_ia=processo.resumo_ia,
            checklist_ia=processo.checklist_ia,
            despacho_automatico=processo.despacho_automatico,
        )

    background_tasks.add_task(
        AnaliseService.disparar_analise_em_background,
        processo_id,
    )

    return AnaliseStatusResponse(
        processo_id=processo.id,
        analise_status=AnaliseStatusEnum.PENDING.value,
        status=processo.status,
        analise_started_em=processo.analise_started_em,
        analise_concluida_em=processo.analise_concluida_em,
        analise_erro=processo.analise_erro,
        analise_log=processo.analise_log,
        resumo_ia=processo.resumo_ia,
        checklist_ia=processo.checklist_ia,
        despacho_automatico=processo.despacho_automatico,
    )

