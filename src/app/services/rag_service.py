
from typing import Any

import httpx

from app.core.config import get_settings


class RagClient:
    """
    Cliente assincrono  para serviço RAG.
    
    Abstrai a comunicacao HTTP com ClarIA RAG API.  
    Todos os metodos sao corrotinas.
    """

    def __init__(self, base_url: str, timeout: int = 120):
        """
        Inicializa o cliente.

        Args:
            base_url: URL base do serviço RAG.
            timeout: Timeout em segundos para requisicoes (default: 120).
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
    
    async def health_check(self) -> bool:
        """
        Verifica saúde do serviço RAG.
        
        Returns:
            bool: True se RAG está healthy, False caso contrário.
        """
        try:
            response = await self.client.get(f"{self.base_url}/ia/health")
            return response.status_code == 200
        except Exception:
            return False
    


    async def analisar_processo(
        self,
        documentos: list[tuple[bytes, str]],
        tipo_processo: str,
    ) -> dict[str, Any]:
        """
        Envia os PDFs brutos para o serviço RAG analisar de forma completa.

        Usa a super-rota /ia/analisar que faz internamente:
        - Classificação por conteúdo (fuzzy matching)
        - Checklist determinístico
        - Validação cruzada (antifraude)
        - Resumo executivo + Despacho

        Args:
            documentos: Lista de tuplas (bytes_do_pdf, nome_do_arquivo).
            tipo_processo: Tipo do processo (ex: 'afastamento_pos_graduacao').

        Returns:
            dict: Resposta completa do RAG com checklist, resumo e despacho.

        Raises:
            httpx.HTTPError: Se requisição falhar.
        """
        files = [
            ("files", (nome, conteudo, "application/pdf"))
            for conteudo, nome in documentos
        ]
        data = {"type_process": tipo_processo}

        response = await self.client.post(
            f"{self.base_url}/ia/analisar",
            files=files,
            data=data,
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Fecha cliente HTTP."""
        await self.client.aclose()

async def get_rag_client() -> RagClient:
    """
    Dependency injection para RAGClient.
    
    Yields:
        RAGClient: Cliente configurado.
    """
    settings = get_settings()
    client = RagClient(
        base_url=settings.rag_service_url,
        timeout=settings.rag_service_timeout,
    )
    try:
        yield client
    finally:
        await client.close()