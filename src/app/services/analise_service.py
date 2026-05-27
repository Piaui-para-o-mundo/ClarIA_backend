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
                # ─── DESPACHO AUTOMÁTICO PARA PROCESSOS COM PENDÊNCIAS ───
                # Quando a conformidade é parcial, gera automaticamente o despacho
                # de pendência, o PDF e notifica o professor, sem intervenção do avaliador.
                AnaliseService._append_log(
                    processo,
                    f"Conformidade parcial ({conformidade_pct:.2f}%). Iniciando geração automática de despacho.",
                )

                setor_destino_mvp = "FUESPI-PI/GAB/PHB/TSC"

                try:
                    # 1. Gera o texto do despacho via IA
                    resumo_texto = ""  # Resumo ainda não foi gerado nesta fase
                    despacho_response = await rag_client.sugerir_despacho(
                        checklist_result=checklist_result,
                        resumo_texto=resumo_texto,
                        integridade_result=conformidade.get("integridade"),
                    )

                    # Adiciona setor_destino ao JSON do despacho
                    if isinstance(despacho_response, dict):
                        despacho_response["setor_destino_sugerido"] = setor_destino_mvp

                    processo.despacho_automatico = json.dumps(despacho_response, ensure_ascii=False)
                    AnaliseService._append_log(processo, "Despacho automático gerado com sucesso pela IA.")

                    # 2. Extrai o corpo do despacho para o PDF
                    corpo_despacho = rag_client._extrair_texto(
                        despacho_response, ("corpo_despacho", "despacho", "texto", "resultado")
                    )

                    # 3. Gera o PDF oficial
                    try:
                        from app.api.routes.dispatch import (
                            _build_dispatch_context,
                            _render_dispatch_html,
                            _generate_pdf,
                        )
                        from datetime import datetime as dt_pdf

                        context = _build_dispatch_context(
                            processo=processo,
                            setor_destino_sugerido=setor_destino_mvp,
                            assunto=f"DESPACHO DE PENDÊNCIA — Processo Nº {processo.numero}",
                            corpo_despacho=corpo_despacho,
                            numero_despacho=f"{dt_pdf.now().year}/CPPD/{processo.numero.split('/')[-1] if '/' in processo.numero else '001'}",
                        )

                        html = _render_dispatch_html(context)
                        pdf_bytes = _generate_pdf(html)

                        # 4. Salva o PDF como documento do processo
                        await ProcessoService.save_documento(
                            db=db,
                            processo_id=str(processo.id),
                            tipo_doc="despacho_pendencia",
                            arquivo_bytes=pdf_bytes,
                            name_arquivo=f"Despacho_Pendencia_{processo.numero.replace('/', '_')}.pdf",
                        )
                        AnaliseService._append_log(processo, "PDF do despacho de pendência gerado e salvo.")

                    except Exception as pdf_exc:
                        # Se falhar PDF, continua sem travar — o texto já foi salvo
                        AnaliseService._append_log(
                            processo,
                            f"Aviso: falha ao gerar PDF do despacho automático: {pdf_exc}",
                        )
                        print(f"[DESPACHO AUTO] Falha PDF: {pdf_exc}", flush=True)

                    # 5. Cria notificação in-app para o professor
                    try:
                        from app.services.notificacao_service import NotificacaoService

                        docs_faltando = checklist_result.get("documentos_faltando", [])
                        nomes_faltando = ", ".join(
                            (
                                item if isinstance(item, str)
                                else item.get("descricao") or item.get("tipo_documento", "Documento")
                            )
                            for item in docs_faltando[:3]
                        )
                        sufixo = f" e mais {len(docs_faltando) - 3}" if len(docs_faltando) > 3 else ""

                        await NotificacaoService.criar(
                            db,
                            usuario_id=processo.usuario_id,
                            processo_id=processo.id,
                            tipo="despacho_automatico",
                            titulo=f"Pendências no Processo {processo.numero}",
                            mensagem=(
                                f"O processo {processo.numero} atingiu {conformidade_pct:.0f}% de conformidade. "
                                f"Documentos pendentes: {nomes_faltando}{sufixo}. "
                                f"Um despacho foi gerado automaticamente. Acesse o processo para mais detalhes."
                            ),
                        )
                        AnaliseService._append_log(processo, "Notificação de pendência criada para o professor.")

                    except Exception as notif_exc:
                        AnaliseService._append_log(
                            processo,
                            f"Aviso: falha ao criar notificação: {notif_exc}",
                        )
                        print(f"[DESPACHO AUTO] Falha notificação: {notif_exc}", flush=True)

                except Exception as despacho_exc:
                    # Se falhar a geração do despacho, continua — o status será PENDENTE_PROFESSOR de qualquer forma
                    AnaliseService._append_log(
                        processo,
                        f"Falha ao gerar despacho automático: {despacho_exc}",
                    )
                    print(f"[DESPACHO AUTO] Falha geral: {despacho_exc}", flush=True)

                processo.status = StatusEnum.PENDENTE_PROFESSOR
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
                processo.resumo_ia = rag_client._extrair_texto(
                    resumo_response, ("resumo", "texto", "conteudo", "analise", "resultado")
                )
                AnaliseService._append_log(processo, "Resumo manual concluído com sucesso.")
            except httpx.HTTPError as exc:
                processo.resumo_ia = "Erro de comunicação com a API do RAG."
                AnaliseService._append_log(processo, f"Falha no RAG ao gerar resumo: {exc}")
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
            # Salva o JSON completo da IA (contém corpo_despacho + setor_destino_sugerido + status_sugerido)
            processo.despacho_automatico = json.dumps(despacho_response, ensure_ascii=False)
            AnaliseService._append_log(processo, "Despacho manual concluído com sucesso.")
        except httpx.HTTPError as exc:
            processo.despacho_automatico = "Erro de comunicação com a API do RAG."
            AnaliseService._append_log(processo, f"Falha no RAG ao gerar despacho: {exc}")

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