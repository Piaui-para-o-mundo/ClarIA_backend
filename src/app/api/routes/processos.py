
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


@router.get("/", response_model=list[ProcessoResumo])
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
    
    # Executa upload de todos os documentos de forma sequencial
    # (Evita o SAWarning de concorrência na mesma sessão do banco de dados)
    resultados = []
    for idx, (arquivo, tipo) in enumerate(zip(arquivos, tipos_doc)):
        res = await processar_documento(arquivo, tipo, idx)
        resultados.append(res)
    
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

    # Dispara background task para análise completa na IA
    background_tasks.add_task(
        _analisar_ia_background,
        processo_id=processo_id,
        rag_client=rag_client,
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


async def _analisar_ia_background(
    processo_id: UUID,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """
    Task de background para análise completa via RAG (super-rota).
    Cria a própria sessão no banco para garantir que a conexão não seja fechada
    pelo fim da requisição HTTP principal.
    """
    from app.core.database import _session_factory
    import sys
    print(f"==================================================")
    print(f"[RAG BACKGROUND] Iniciando task para processo {processo_id}", flush=True)

    try:
        async with _session_factory() as db:
            from app.models.process import StatusEnum
            from app.models.documento import Documento
            from sqlalchemy import select

            # 1. Pega os metadados dos documentos do banco
            stmt = select(Documento).where(Documento.processo_id == str(processo_id))
            result = await db.execute(stmt)
            documentos = result.scalars().all()

            if not documentos:
                print("[RAG BACKGROUND] Nenhum documento encontrado no banco.", flush=True)
                return

            docs_para_envio = []
            for doc in documentos:
                try:
                    with open(doc.caminho_arquivo, "rb") as f:
                        conteudo = f.read()
                    docs_para_envio.append((conteudo, doc.nome_arquivo))
                except Exception as e:
                    print(f"[RAG BACKGROUND] Erro lendo arquivo {doc.nome_arquivo}: {e}", flush=True)

            if not docs_para_envio:
                print("[RAG BACKGROUND] Falha ao ler o binário dos documentos no disco.", flush=True)
                return

            # 2. Pega o tipo do processo para as regras do RAG
            processo = await ProcessoService.get_processo(db=db, processo_id=str(processo_id))
            if not processo:
                print("[RAG BACKGROUND] Processo não encontrado na base de dados.", flush=True)
                return

            print(f"[RAG BACKGROUND] Enviando {len(docs_para_envio)} documentos para o ClarIA_RAG_IA (URL: {rag_client.base_url})...", flush=True)
            
            # 3. Manda tudo pra super-rota
            result_ia = await rag_client.analisar_processo(
                documentos=docs_para_envio,
                tipo_processo=processo.tipo,
            )
            
            print("[RAG BACKGROUND] Resposta do RAG recebida com sucesso!", flush=True)

            # 4. Grava resultados
            resumo = result_ia.get("resumo", {})
            if resumo and "resultado" in resumo:
                processo.resumo_ia = resumo["resultado"].get("resumo", "")
            
            import json
            processo.checklist_ia = json.dumps(result_ia.get("checklist", {}), ensure_ascii=False)
            
            despacho_dict = result_ia.get("despacho", {})
            if despacho_dict and "resultado" in despacho_dict:
                processo.despacho_automatico = despacho_dict["resultado"]

            # Se reprovado pelo checklist, fica pendente para professor ou para análise
            checklist = result_ia.get("checklist", {})
            if not checklist.get("aprovado", False):
                processo.status = StatusEnum.PENDENTE_PROFESSOR
            else:
                processo.status = StatusEnum.ANALISE_PENDENTE

            await db.commit()
            print(f"[RAG BACKGROUND] Processo {processo_id} atualizado com análise IA com sucesso.", flush=True)

    except Exception as e:
        import traceback
        print(f"[RAG BACKGROUND] Erro CRÍTICO em _analisar_ia_background: {e}", flush=True)
        traceback.print_exc()
        print(f"==================================================", flush=True)
        
