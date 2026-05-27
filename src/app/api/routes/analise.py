from typing import Annotated, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.process import AnaliseStatusEnum, StatusEnum
from app.services.processo_service import ProcessoService

router = APIRouter(prefix='/api/v1/analise', tags=['analise'])
bearer_scheme = HTTPBearer()


class AprovarDespachoRequest(BaseModel):
    despacho_editado: str
    assunto: Optional[str] = None
    setor_destino: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# ROTA 1 — Resultado da análise IA (lê do banco, sem chamar o RAG)
# ─────────────────────────────────────────────────────────────────────────────
@router.get('/{processo_id}/resultado')
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

    processo = await ProcessoService.get_processo(
        db=db, processo_id=processo_id
    )

    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Processo não encontrado',
        )

    analise_status = processo.analise_status or AnaliseStatusEnum.PENDING.value

    # Se estiver pendente ou em processamento, informe 202 para o frontend
    if analise_status in {
        AnaliseStatusEnum.PENDING.value,
        AnaliseStatusEnum.PROCESSING.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail={
                'mensagem': 'Análise de IA ainda em processamento. Tente novamente em alguns instantes.',
                'analise_status': analise_status,
            },
        )

    # Para status finais ('completed' ou 'error') sempre retornar 200 com os dados,
    # deixando o frontend decidir como exibir (erro tratado como informação).
    # Parseia o despacho se existir (pode ser JSON da IA ou texto legado)
    import json as _json

    despacho_raw = processo.despacho_automatico or ''
    despacho_parsed = {}
    try:
        despacho_parsed = _json.loads(despacho_raw)
    except (ValueError, TypeError):
        pass

    return {
        'processo_id': str(processo.id),
        'numero': processo.numero,
        'status': processo.status,
        'analise_status': analise_status,
        'analise_erro': processo.analise_erro,
        'resumo_ia': processo.resumo_ia,
        'checklist_ia': processo.checklist_ia,
        'despacho_automatico': despacho_parsed.get(
            'corpo_despacho', despacho_raw
        ),
        'corpo_despacho': despacho_parsed.get('corpo_despacho', despacho_raw),
        'setor_destino_sugerido': despacho_parsed.get(
            'setor_destino_sugerido', 'CPPD'
        ),
        'status_sugerido': despacho_parsed.get('status_sugerido', ''),
        'assunto_despacho': despacho_parsed.get('assunto', ''),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ROTA 2 — Geração de Resumo sob demanda
# ─────────────────────────────────────────────────────────────────────────────
@router.post('/{processo_id}/gerar-resumo')
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

    processo = await ProcessoService.get_processo(
        db=db, processo_id=processo_id
    )
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Processo não encontrado.',
        )

    if not processo.checklist_ia:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='A análise de conformidade ainda não foi concluída. Aguarde o processamento automático.',
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
                detail='Processo não encontrado.',
            )
        return {
            'processo_id': str(processo_atualizado.id),
            'resumo_ia': processo_atualizado.resumo_ia,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Erro ao gerar resumo: {str(e)}',
        )
    finally:
        await rag_client.close()


# ─────────────────────────────────────────────────────────────────────────────
# ROTA 3 — Geração de Despacho sob demanda
# ─────────────────────────────────────────────────────────────────────────────
@router.post('/{processo_id}/gerar-despacho')
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

    processo = await ProcessoService.get_processo(
        db=db, processo_id=processo_id
    )
    if not processo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Processo não encontrado.',
        )

    if not processo.checklist_ia:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='A análise de conformidade ainda não foi concluída. Aguarde o processamento automático.',
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
                detail='Processo não encontrado.',
            )
        # Parseia o JSON salvo para retornar campos estruturados ao frontend
        import json as _json

        despacho_raw = processo_atualizado.despacho_automatico or ''
        try:
            despacho_obj = _json.loads(despacho_raw)
        except (ValueError, TypeError):
            despacho_obj = {'corpo_despacho': despacho_raw}

        return {
            'processo_id': str(processo_atualizado.id),
            'despacho_automatico': despacho_obj.get(
                'corpo_despacho', despacho_raw
            ),
            'corpo_despacho': despacho_obj.get('corpo_despacho', despacho_raw),
            'setor_destino_sugerido': despacho_obj.get(
                'setor_destino_sugerido', 'CPPD'
            ),
            'status_sugerido': despacho_obj.get('status_sugerido', ''),
            'assunto': despacho_obj.get('assunto', ''),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Erro ao gerar despacho: {str(e)}',
        )
    finally:
        await rag_client.close()


# ─────────────────────────────────────────────────────────────────────────────
# ROTA 4 — Avaliador aprova/edita o despacho e envia ao professor
# ─────────────────────────────────────────────────────────────────────────────
@router.post('/{processo_id}/aprovar-despacho')
async def aprovar_despacho(
    processo_id: UUID,
    payload: AprovarDespachoRequest,
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """
    Avaliador aprova ou edita o despacho.
    Gera o PDF oficial e retorna o processo para o professor (PENDENTE_PROFESSOR).
    """
    despacho_editado = payload.despacho_editado
    user = await get_current_user(token.credentials, db)
    if not user or getattr(user, 'role', None) != 'avaliador':
        raise HTTPException(
            status_code=403,
            detail='Apenas avaliadores podem assinar o despacho.',
        )

    processo = await ProcessoService.get_processo(
        db=db, processo_id=processo_id
    )
    if not processo:
        raise HTTPException(status_code=404, detail='Processo não encontrado.')

    # 1. Salva o texto final no banco
    processo.despacho_avaliador = despacho_editado

    # 2. Gera o PDF Oficial (Papel Timbrado)
    from app.api.routes.dispatch import (
        _build_dispatch_context,
        _render_dispatch_html,
        _generate_pdf,
    )
    import json as _json

    usuario = getattr(processo, 'usuario', None)

    # Extrai dados da IA para preencher campos que o frontend não enviou
    despacho_ia = {}
    if processo.despacho_automatico:
        try:
            despacho_ia = _json.loads(processo.despacho_automatico)
        except (ValueError, TypeError):
            pass

    setor_destino = (
        payload.setor_destino
        or despacho_ia.get('setor_destino_sugerido')
        or 'CPPD'
    )
    assunto = (
        payload.assunto
        or despacho_ia.get('assunto')
        or f'Despacho do Processo Nº {processo.numero}'
    )

    context = _build_dispatch_context(
        processo=processo,
        setor_destino_sugerido=setor_destino,
        assunto=f'DESPACHO DO PROCESSO Nº {processo.numero}',
        corpo_despacho=despacho_editado,
        numero_despacho=f"{datetime.now().year}/CPPD/{processo.numero.split('/')[-1] if '/' in processo.numero else '001'}",
    )

    try:
        html = _render_dispatch_html(context)
        pdf_bytes = _generate_pdf(html)

        # 3. Salva o PDF como documento oficial do processo
        await ProcessoService.save_documento(
            db=db,
            processo_id=str(processo_id),
            tipo_doc='despacho_assinado',
            arquivo_bytes=pdf_bytes,
            name_arquivo=f"Despacho_Assinado_{processo.numero.replace('/', '_')}.pdf",
        )
    except Exception as e:
        print(f'[ERRO GERAÇÃO PDF] {e}')
        # Se falhar PDF, continuamos para não travar o fluxo, mas logamos

    # 4. Atualiza Status para PENDENTE_PROFESSOR (Regra de Negócio: volta para o dono)
    await ProcessoService.update_status(
        db=db,
        processo_id=processo_id,
        novo_status=StatusEnum.PENDENTE_PROFESSOR,
    )

    await db.commit()

    return {
        'status': 'enviado_ao_professor',
        'processo_id': str(processo_id),
        'mensagem': 'Despacho assinado e PDF gerado com sucesso. Processo devolvido ao professor.',
    }
