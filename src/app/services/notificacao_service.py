"""Serviço para operações de notificações in-app."""

from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notificacao import Notificacao


class NotificacaoService:
    """Gerencia criação, listagem e leitura de notificações."""

    @staticmethod
    async def criar(
        db: AsyncSession,
        *,
        usuario_id: UUID,
        processo_id: UUID | None = None,
        tipo: str = "info",
        titulo: str,
        mensagem: str,
    ) -> Notificacao:
        """Cria uma nova notificação para o usuário."""
        notificacao = Notificacao(
            usuario_id=usuario_id,
            processo_id=processo_id,
            tipo=tipo,
            titulo=titulo,
            mensagem=mensagem,
        )
        db.add(notificacao)
        await db.flush()
        return notificacao

    @staticmethod
    async def listar(
        db: AsyncSession,
        usuario_id: UUID,
        *,
        apenas_nao_lidas: bool = False,
        limit: int = 20,
    ) -> list[Notificacao]:
        """Lista notificações do usuário, opcionalmente apenas não lidas."""
        stmt = (
            select(Notificacao)
            .where(Notificacao.usuario_id == usuario_id)
            .order_by(Notificacao.criado_em.desc())
            .limit(limit)
        )
        if apenas_nao_lidas:
            stmt = stmt.where(Notificacao.lida == False)  # noqa: E712

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def contar_nao_lidas(db: AsyncSession, usuario_id: UUID) -> int:
        """Conta o número de notificações não lidas."""
        stmt = (
            select(func.count())
            .select_from(Notificacao)
            .where(Notificacao.usuario_id == usuario_id)
            .where(Notificacao.lida == False)  # noqa: E712
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    async def marcar_como_lida(db: AsyncSession, notificacao_id: UUID) -> Notificacao | None:
        """Marca uma notificação específica como lida."""
        stmt = select(Notificacao).where(Notificacao.id == notificacao_id)
        result = await db.execute(stmt)
        notificacao = result.scalars().first()

        if notificacao:
            notificacao.lida = True
            await db.flush()

        return notificacao

    @staticmethod
    async def marcar_todas_como_lidas(db: AsyncSession, usuario_id: UUID) -> int:
        """Marca todas as notificações do usuário como lidas. Retorna a quantidade atualizada."""
        stmt = (
            update(Notificacao)
            .where(Notificacao.usuario_id == usuario_id)
            .where(Notificacao.lida == False)  # noqa: E712
            .values(lida=True)
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount
