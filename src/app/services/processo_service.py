
import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.documento import Documento
from app.models.process import Processo, StatusEnum
from app.models.user import User

from app.services.rag_service import RagClient


class ProcessoService:
    """Serviço para operacoes de processos."""

    UPLOAD_DIR = Path("uploads")

    @classmethod
    async def _get_upload_path(cls, processo_id: str, tipo_doc: str) -> Path:
        """
        Retorna path onde o documento sera salvo

        Args:
            processo_id (str): ID do processo
            tipo_doc: Tipo de documento.
        
        Returns: 
            Path: Path relativo do arquivo.
        """

        dir_path = cls.UPLOAD_DIR / processo_id
        dir_path.mkdir(parents=True, exist_ok=True)

        timestamp = uuid4().hex[:8]
        filename = f"{tipo_doc}_{timestamp}.pdf"

        return dir_path / filename
    
    @staticmethod
    async def criar_processo(db: AsyncSession, user: User, tipe: str) -> Processo:
        """
        Cria novo processo




        Args:
            db (AsyncSession): Sessao do banco de dados.
            user (User): Usuario que esta criando o processo.
            tipe (str): Tipo do processo.

        Returns:
            Processo: O processo criado.
        """

        # Gera numero unico: CPPD-XXXX/2026
        # Em producao, usar sequence do DB ou service dedicado

        numero = f"CPPD-{uuid4().hex[:3].upper()}/{2026}"

        processo = Processo(
            numero=numero,
            user_id=user.id,
            status=StatusEnum.AGUARDANDO_DOCUMENTOS,
        )

        db.add(processo)
        await db.flush()

        return processo

    @staticmethod
    async def listar_processos(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 10,
    ) -> list[Processo]:
        """
        Lista todos os processos (para avaliador).
        
        Args:
            db: Session de banco.
            skip: Offset de paginação.
            limit: Limite de resultados.
            
        Returns:
            list[Processo]: Processos paginados.
        """

        stmt = (
            select(Processo)
            .offset(skip)
            .limit(limit)
            .order_by(Processo.created_at.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def listar_processos_user(
         db: AsyncSession,
        usuario_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Processo]:
        """
        Lista processos do usuário (professor).
        
        Args:
            db: Session de banco.
            usuario_id: ID do usuário.
            skip: Offset de paginação.
            limit: Limite de resultados.
            
        Returns:
            list[Processo]: Processos do usuário.
        """
        stmt = (
            select(Processo)
            .where(Processo.usuario_id == usuario_id)
            .offset(skip)
            .limit(limit)
            .order_by(Processo.criado_em.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_processo(
        db: AsyncSession,
        processo_id: str,
    ) -> Processo | None    :
        """
        Retorna processo por ID, com documentos relacionados.

        Args:
            db: Session de banco.
            processo_id: ID do processo.
        """
        stmt = (
            select(Processo)
            .where(Processo.id == processo_id)
            .options(selectinload(Processo.documentos))
        )

        result = await db.execute(stmt)
        return result.scalars().first()

    
    @staticmethod
    async def save_documento(
        db: AsyncSession,
        processo_id: str,
        tipo_doc: str,
        arquivo_bytes: bytes,
        name_arquivo: str,
    ) -> Documento:
        """
        Salva documento no disco e registra no DB

        Args:
            db: Session de banco.
            processo_id: ID do processo.
            tipo_doc: Tipo do documento (ex: "comprovante_pagamento").
            arquivo_bytes: Conteudo do arquivo em bytes.
            name_arquivo: Nome original do arquivo (para referencia).

        Returns:
            Documento: O documento salvo.
        """

        caminho = ProcessoService._get_upload_path(processo_id, tipo_doc)
        with open(caminho, "wb") as f:
            f.write(arquivo_bytes)
        
        documento = Documento(
            processo_id=processo_id,
            name_arquivo=name_arquivo,
            tipo_doc=tipo_doc,
            caminho=str(caminho),
        )

        db.add(documento)
        await db.flush()
        return documento

    
    @staticmethod
    async def update_status(
        db: AsyncSession,
        processo_id: str,
        novo_status: StatusEnum,
    ) -> Processo | None:
        """
        Atualiza status do processo.
        
        Args:
            db: Session de banco.
            processo_id: ID do processo.
            novo_status: Novo status.
            
        Returns:
            Processo | None: Processo atualizado.
        """

        stmt = select(Processo).where(Processo.id == processo_id)
        result = await db.execute(stmt)
        processo = result.scalars().first()

        if processo:
            processo.status = novo_status
            await db.flush()
        
        return processo
    
    @staticmethod
    async def save_despacho_automatico(
        db: AsyncSession,
        processo_id: str,
        despacho: str,
    ) -> Processo | None:
        """
        Salva despacho automatico gerado pelo RAG.

        Args:
            db: Session de banco.
            processo_id: ID do processo.
            despacho: Texto do despacho gerado.
        """

        stmt = select(Processo).where(Processo.id == processo_id)
        result = await db.execute(stmt)
        processo = result.scalars().first()

        if processo:
            processo.despacho_automatico = despacho
            await db.flush()
        
        return processo

    @staticmethod
    async def get_documentos_text_concatenado(
        db: AsyncSession,
        processo_id: str,
    ) -> str:
        """
        Concatena conteudo de todos os documentos para analise.

        Args:
            db: Session de banco.
            processo_id: ID do processo.

        Returns:
            str: Conteudo concatenado dos documentos.
        """

        stmt = select(Documento).where(Documento.processo_id == processo_id)
        result = await db.execute(stmt)
        documentos = result.scalars().all()
        
        textos = [
            f"[{d.tipo_doc}]\n{d.conteudo_extraido or ""}"
            for d in documentos
        ]

        return "\n\n".join(textos)
    

    