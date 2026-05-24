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

        try:
            texto_documento = await ProcessoService.get_documentos_text_concatenado(
                db=db,
                processo_id=processo_id,
            )

            if not texto_documento.strip():
                raise ValueError("Nenhum texto encontrado nos documentos para análise.")

            print(f"[ANALISE BACKGROUND] Chamando /ia/resumo para processo {processo_id}", flush=True)
            AnaliseService._append_log(processo, "Enviando texto consolidado para a IA.")
            resumo = await rag_client.gerar_resumo(texto_documento)
            print(f"[ANALISE BACKGROUND] Chamando /ia/conformidade para processo {processo_id}", flush=True)
            conformidade = await rag_client.verificar_conformidade(
                texto_documento=texto_documento,
                tipo_processo=processo.tipo,
            )

            conformidade_pct = float(conformidade.get("conformidade_pct", 0) or 0)
            pendencias = conformidade.get("pendencias", []) or []
            processo.resumo_ia = resumo.get("resumo") or json.dumps(resumo, ensure_ascii=False)
            processo.checklist_ia = json.dumps(conformidade, ensure_ascii=False)

            if conformidade_pct < 100:
                print(f"[ANALISE BACKGROUND] Chamando /ia/despacho para processo {processo_id}", flush=True)
                despacho = await rag_client.sugerir_despacho(
                    texto_documento=texto_documento,
                    pendencias=", ".join(map(str, pendencias)),
                )
                processo.despacho_automatico = despacho.get("despacho") or json.dumps(
                    despacho,
                    ensure_ascii=False,
                )
                processo.status = StatusEnum.PENDENTE_PROFESSOR
                AnaliseService._append_log(
                    processo,
                    f"Conformidade parcial ({conformidade_pct:.2f}%). Despacho sugerido gerado.",
                )
            else:
                processo.status = StatusEnum.ANALISE_PENDENTE
                AnaliseService._append_log(
                    processo,
                    f"Conformidade total ({conformidade_pct:.2f}%). Análise concluída.",
                )
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

        print(
            f"[ANALISE BACKGROUND] Iniciando processo {processo_id} via {settings.rag_service_url}",
            flush=True,
        )

        async with session_factory() as db:
            try:
                await AnaliseService.executar_analise_automatica(
                    db=db,
                    processo_id=processo_id,
                    rag_client=rag_client,
                )
                await db.commit()
                print(f"[ANALISE BACKGROUND] Processo {processo_id} finalizado.", flush=True)
            except Exception as exc:
                await db.rollback()
                print(
                    f"[ANALISE BACKGROUND] Falha no processo {processo_id}: {exc}",
                    flush=True,
                )
            finally:
                await rag_client.close()
