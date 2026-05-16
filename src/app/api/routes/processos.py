
from typing import Annotated

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

from fastapi.security import OAuth2PasswordBearer
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
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

@router.post("/", response_model=ProcessoResponse)
async def criar_processo(
    processo_data: ProcessoCreate,
    token: Annotated[str, Depends(oauth2_scheme)],
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
    user = await get_current_user(token, db)

    processo = await ProcessoService.criar_processo(
        db=db,
        user=user,
        tipe=processo_data.tipo,
    )
    await db.commit()

    return ProcessoResponse.from_orm(processo)


@router.get("", response_model=list[processoResumo])
async def listar_processos(
    skip: int = 0,
    limit: int = 50,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
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

@router.get("/my", response_model=list[processoResumo])
async def list_my_processos(
    skip: int = 0,
    limit: int = 50,
    token: Annotated[str, Depends(oauth2_scheme)] = None,
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

    user = await get_current_user(token, db)

    processos = await ProcessoService.listar_processos_user(
        db=db,
        usuario_id=user.id,
        skip=skip,
        limit=limit,
    )

    return [ProcessoResumo.from_orm(p) for p in processos]

@router.get("/{processo_id}", response_model=ProcessoResponse)
async def get_processo(
    processo_id: int,
    token: Annotated[str, Depends(oauth2_scheme)],
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
    processo_id: int,
    arquivos: list[UploadFile] = File(...),
    tipos_doc: list[str] = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    token: Annotated[str, Depends(oauth2_scheme)] = None,
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

    user = await get_current_user(token, db)

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
    for arquivo, tipo_doc in zip(arquivos, tipos_doc):
        try:
            conteudo = await arquivo.read()
            await ProcessoService.save_documento(
                db=db,
                processo_id=processo_id,
                tipo_doc=tipo_doc,
                arquivo_bytes=conteudo,
                name_arquivo=arquivo.filename,
            )
            sucesso += 1
        except Exception as e:
            print(f"Erro ao salvar documento {arquivo.filename}: {e}")
            continue

    
    await db.commit()

    background_tasks.add_task(
        _verificar_conformidade_background,
        db=db,
        processo_id=processo_id,
        rag_client=rag_client,
    )    
    return {"sucesso": sucesso, "falhas": len(arquivos) - sucesso}