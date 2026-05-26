from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import httpx
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
    def _gerar_despacho_fallback(processo: Processo, checklist_result: dict, resumo_texto: str) -> str:
        """Gera um despacho mínimo quando o serviço RAG não está disponível."""

        conformidade = checklist_result.get("conformidade_pct")
        documentos_faltando = checklist_result.get("documentos_faltando") or []
        aprovado = bool(checklist_result.get("aprovado"))

        linhas = [
            "DESPACHO AUTOMÁTICO PROVISÓRIO",
            f"Processo: {processo.numero}",
            f"Tipo: {processo.tipo}",
        ]

        if conformidade is not None:
            linhas.append(f"Conformidade: {conformidade}%")

        if aprovado:
            linhas.append("Conclusão: documentação suficiente para prosseguimento.")
        else:
            linhas.append("Conclusão: documentação pendente de complementação.")

        if documentos_faltando:
            faltantes = ", ".join(str(item) for item in documentos_faltando)
            linhas.append(f"Pendências: {faltantes}")

        if resumo_texto:
            linhas.append("")
            linhas.append("Resumo executivo:")
            linhas.append(resumo_texto.strip())

        return "\n".join(linhas).strip()

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
        """Executa a análise automática de forma idempotente (apenas conformidade)."""

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
        AnaliseService._append_log(processo, "Análise automática iniciada (etapa 1).")
        await db.flush()

        try:
            documentos = processo.documentos

            if not documentos:
                raise ValueError("Nenhum documento encontrado para análise.")

            docs_para_rag = []
            import os
            for doc in documentos:
                if doc.caminho_arquivo and os.path.exists(doc.caminho_arquivo):
                    with open(doc.caminho_arquivo, "rb") as f:
                        docs_para_rag.append((f.read(), doc.nome_arquivo))
            
            if not docs_para_rag:
                raise ValueError("Não foi possível ler o conteúdo dos PDFs no disco.")

            print(f"[ANALISE BACKGROUND] Iniciando Etapa 1: Conformidade para {processo_id}", flush=True)
            AnaliseService._append_log(processo, "Enviando PDFs para /ia/conformidade...")
            
            # Etapa 1: Conformidade (Rápida, Regex/Cache + LLM Classificador)
            conformidade = await rag_client.verificar_conformidade(
                documentos=docs_para_rag,
                type_process=processo.tipo,
            )
            checklist_result = conformidade.get("checklist") or conformidade
            
            # O checklist_ia salva os textos extraídos para que a função gerar_resumo() não precise re-extrair os PDFs do disco.
            processo.checklist_ia = json.dumps(conformidade, ensure_ascii=False)
            
            # Determina status final do processo baseado no checklist
            aprovado = bool(checklist_result.get("aprovado"))
            conformidade_pct = checklist_result.get("conformidade_pct")
            if conformidade_pct is None:
                conformidade_pct = 100.0 if aprovado else 0.0
            else:
                conformidade_pct = float(conformidade_pct or 0)
                
            AnaliseService._append_log(processo, "Checklist concluído. Resumo e despacho pendentes de solicitação manual.")
            
            if conformidade_pct < 100:
                processo.status = StatusEnum.PENDENTE_PROFESSOR
                AnaliseService._append_log(
                    processo,
                    f"Conformidade parcial ({conformidade_pct:.2f}%).",
                )
            else:
                processo.status = StatusEnum.ANALISE_PENDENTE
                AnaliseService._append_log(
                    processo,
                    f"Conformidade total ({conformidade_pct:.2f}%).",
                )
                
            processo.analise_status = AnaliseStatusEnum.COMPLETED.value
            processo.analise_concluida_em = datetime.now(timezone.utc)
            processo.analise_erro = None

            AnaliseService._append_log(processo, "Análise automática IA (etapa 1) concluída com sucesso.")
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
    async def gerar_resumo(
        db: AsyncSession,
        processo_id: UUID,
        rag_client: RagClient,
    ) -> Processo | None:
        """Gera o resumo sob demanda a partir dos textos extraídos na conformidade."""
        processo = await AnaliseService.obter_processo_lock(db=db, processo_id=processo_id)
        if not processo:
            return None

        if not processo.checklist_ia:
            raise ValueError("Conformidade ainda não foi verificada.")

        conformidade = json.loads(processo.checklist_ia)
        checklist_result = conformidade.get("checklist") or conformidade

        # Etapa 2: Resumo
        print(f"[ANALISE MANUAL] Iniciando Etapa 2: Resumo para {processo_id}", flush=True)
        
        textos_extraidos = conformidade.get("textos_extraidos") or []
        if textos_extraidos:
            try:
                resumo_response = await rag_client.gerar_resumo(
                    tipo_processo=processo.tipo,
                    textos_extraidos=textos_extraidos,
                )
                processo.resumo_ia = rag_client._extrair_resumo_texto(resumo_response)
                AnaliseService._append_log(processo, "Resumo manual concluído com sucesso.")
            except httpx.HTTPStatusError as exc:
                processo.resumo_ia = "Erro na API do RAG."
                AnaliseService._append_log(processo, f"Erro HTTP no RAG ao gerar resumo: {exc.response.status_code} - {exc.response.text}")
            except httpx.RequestError as exc:
                processo.resumo_ia = "Serviço RAG indisponível ou ocorreu um timeout."
                AnaliseService._append_log(processo, f"Erro de conexão/timeout no RAG ao gerar resumo: {exc}")
        else:
            processo.resumo_ia = "Não foi possível gerar o resumo pois não há textos extraídos dos documentos."
            AnaliseService._append_log(processo, "Resumo falhou: Falta de textos extraídos.")
        
        # COMITA IMEDIATAMENTE para o frontend exibir o resumo
        await db.commit()
        return processo

    @staticmethod
    async def gerar_despacho(
        db: AsyncSession,
        processo_id: UUID,
        rag_client: RagClient,
    ) -> Processo | None:
        """Gera o despacho sob demanda a partir do checklist e resumo (se existir)."""
        processo = await AnaliseService.obter_processo_lock(db=db, processo_id=processo_id)
        if not processo:
            return None

        if not processo.checklist_ia:
            raise ValueError("Conformidade ainda não foi verificada.")

        conformidade = json.loads(processo.checklist_ia)
        checklist_result = conformidade.get("checklist") or conformidade

        # Etapa 3: Despacho
        print(f"[ANALISE MANUAL] Iniciando Etapa 3: Despacho para {processo_id}", flush=True)

        resumo_texto = processo.resumo_ia or ""
        try:
            despacho_response = await rag_client.sugerir_despacho(
                checklist_result=checklist_result,
                resumo_texto=resumo_texto,
                integridade_result=conformidade.get("integridade")
            )
            processo.despacho_automatico = rag_client._extrair_despacho_texto(despacho_response)
            AnaliseService._append_log(processo, "Despacho manual concluído com sucesso.")
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as exc:
            processo.despacho_automatico = AnaliseService._gerar_despacho_fallback(
                processo=processo,
                checklist_result=checklist_result,
                resumo_texto=resumo_texto,
            )
            AnaliseService._append_log(
                processo,
                f"RAG indisponível, despacho provisório gerado localmente: {exc}",
            )
        except httpx.HTTPStatusError as exc:
            processo.despacho_automatico = AnaliseService._gerar_despacho_fallback(
                processo=processo,
                checklist_result=checklist_result,
                resumo_texto=resumo_texto,
            )
            AnaliseService._append_log(
                processo,
                f"Erro na API do RAG ({exc.response.status_code}), despacho provisório gerado localmente.",
            )

        await db.commit()
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
        print(
            f"[ANALISE BACKGROUND] Task recebida e sessão de análise aberta para processo {processo_id}",
            flush=True,
        )

        async with session_factory() as db:
            try:
                print(
                    f"[ANALISE BACKGROUND] Executando análise automática do processo {processo_id}",
                    flush=True,
                )
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