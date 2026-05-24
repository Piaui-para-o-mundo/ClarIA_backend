from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_session_factory_instance
from app.models.process import AnaliseStatusEnum, Processo, StatusEnum
from app.services.processo_service import ProcessoService
from app.services.rag_service import RagClient


class AnaliseService:
    """Orquestra o processamento automático de análise da IA."""

    @staticmethod
    def _append_log(processo: Processo, mensagem: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        entrada = f"[{timestamp}] {mensagem}"
        if processo.analise_log:
            processo.analise_log = f"{processo.analise_log}\n{entrada}"
        else:
            processo.analise_log = entrada

    @staticmethod
    async def obter_processo_lock(db: AsyncSession, processo_id: UUID) -> Processo | None:
        stmt = (
            select(Processo)
            .where(Processo.id == processo_id)
            .options(selectinload(Processo.documentos))
            .with_for_update(of=Processo)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def executar_analise_automatica(
        db: AsyncSession,
        processo_id: UUID,
        rag_client: RagClient,
    ) -> Processo | None:
        """Executa a análise automática de forma idempotente."""

        processo = await AnaliseService.obter_processo_lock(db=db, processo_id=processo_id)
        if not processo:
            return None

        if processo.analise_status in {
            AnaliseStatusEnum.PROCESSING.value,
            AnaliseStatusEnum.COMPLETED.value,
        }:
            return processo

        if not processo.documentos:
            processo.analise_status = AnaliseStatusEnum.PENDING.value
            processo.status = StatusEnum.AGUARDANDO_DOCUMENTOS
            AnaliseService._append_log(processo, "Análise aguardando documentos para submissão.")
            await db.flush()
            return processo

        processo.analise_status = AnaliseStatusEnum.PROCESSING.value
        processo.status = StatusEnum.EM_ANALISE
        processo.analise_started_em = datetime.now(timezone.utc)
        processo.analise_concluida_em = None
        processo.analise_erro = None
        AnaliseService._append_log(processo, "Análise automática iniciada.")
        await db.flush()

        import os

        # Lê os arquivos do disco para enviar ao RAG
        arquivos_para_enviar = []
        for doc in processo.documentos:
            caminho_real = f"/app/{doc.caminho_arquivo}"
            try:
                if os.path.exists(caminho_real):
                    with open(caminho_real, "rb") as f:
                        conteudo = f.read()
                        arquivos_para_enviar.append((conteudo, doc.nome_arquivo))
            except Exception as e:
                AnaliseService._append_log(processo, f"Erro ao ler arquivo {doc.nome_arquivo}: {e}")

        if not arquivos_para_enviar:
            processo.analise_status = AnaliseStatusEnum.ERROR.value
            processo.analise_erro = "Nenhum arquivo encontrado no disco para análise."
            processo.analise_concluida_em = datetime.now(timezone.utc)
            AnaliseService._append_log(processo, processo.analise_erro)
            await db.flush()
            return processo

        try:
            print(f"[RAG BACKGROUND] Enviando {len(arquivos_para_enviar)} documentos para a IA...")
            AnaliseService._append_log(processo, f"Enviando {len(arquivos_para_enviar)} documentos para a IA...")
            
            # Chama a super-rota da IA que faz tudo de uma vez
            resposta_ia = await rag_client.analisar_processo(
                documentos=arquivos_para_enviar,
                tipo_processo=processo.tipo,
            )

            # O RAG retorna um objeto completo, que salvamos no checklist e resumo
            processo.checklist_ia = json.dumps(resposta_ia, ensure_ascii=False)
            
            # Atualizamos o status do processo para pendente professor, já que a IA terminou
            processo.status = StatusEnum.PENDENTE_PROFESSOR
            processo.analise_status = AnaliseStatusEnum.COMPLETED.value
            processo.analise_concluida_em = datetime.now(timezone.utc)
            processo.analise_erro = None
            
            AnaliseService._append_log(processo, "Análise automática IA concluída com sucesso.")
            await db.flush()
            return processo

        except Exception as exc:
            processo.analise_status = AnaliseStatusEnum.ERROR.value
            processo.analise_concluida_em = datetime.now(timezone.utc)
            processo.analise_erro = str(exc)
            processo.status = StatusEnum.AGUARDANDO_ANALISE
            AnaliseService._append_log(processo, f"Falha na comunicação com RAG: {exc}")
            await db.flush()
            return processo

    @staticmethod
    async def disparar_analise_em_background(processo_id: UUID) -> None:
        """Executa a análise em uma nova sessão para uso em BackgroundTasks."""

        settings = get_settings()
        session_factory = get_session_factory_instance()
        rag_client = RagClient(
            base_url=settings.rag_service_url,
            timeout=settings.rag_service_timeout,
        )

        async with session_factory() as db:
            try:
                print(f"[RAG BACKGROUND] Iniciando task de background para {processo_id}")
                await AnaliseService.executar_analise_automatica(
                    db=db,
                    processo_id=processo_id,
                    rag_client=rag_client,
                )
                await db.commit()
                print(f"[RAG BACKGROUND] Task finalizada e commitada para {processo_id}")
            except Exception as e:
                import traceback
                print(f"[RAG BACKGROUND] ERRO FATAL: {e}")
                traceback.print_exc()
                await db.rollback()
            finally:
                await rag_client.close()
