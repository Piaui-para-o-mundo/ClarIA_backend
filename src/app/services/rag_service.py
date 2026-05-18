
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
    
    async def ingest_documento(self, pdf_content: bytes, filename: str) -> dict[str, Any]:
        """
        Envia PDF para indexação no ChromaDB do RAG.       Args:
            pdf_content: Conteúdo binário do PDF.
            filename: Nome do arquivo.
            
        Returns:
            dict: Resposta do RAG com índice/ID do documento.
            
        Raises:
            httpx.HTTPError: Se requisição falhar.
        """
        files = {
            "file": (filename, pdf_content, "application/pdf"),
        }
        response = await self.client.post(
            f"{self.base_url}/ia/ingest",
            files=files,
        )
        response.raise_for_status()
        return response.json()
    
    async def gerar_resumo(self, texto_documento: str) -> dict[str, Any]:
        """
        Módulo 1 do RAG: Gera resumo inteligente de texto.
        
        Args:
            texto_documento: Texto do documento.
            
        Returns:
            dict: {"resumo": str, "palavras_chave": list[str], ...}
            
        Raises:
            httpx.HTTPError: Se requisição falhar.
        """
        payload = {"texto": texto_documento}
        response = await self.client.post(
            f"{self.base_url}/ia/resumo",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    
    async def verificar_conformidade(
        self,
        texto_documento: str,
        tipo_processo: str,
    ) -> dict[str, Any]:
        """
        Módulo 2 do RAG: Verifica conformidade documental.
        
        Args:
            texto_documento: Texto do documento.
            tipo_processo: Tipo de processo (progressao_funcional, etc.).
            
        Returns:
            dict: {
                "conformidade_pct": float,
                "pendencias": list[str],
                "detalhes": dict,
            }
            
        Raises:
            httpx.HTTPError: Se requisição falhar.
        """
        payload = {
            "texto": texto_documento,
            "tipo_processo": tipo_processo,
        }
        response = await self.client.post(
            f"{self.base_url}/ia/conformidade",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
    
    async def sugerir_despacho(
        self,
        texto_documento: str,
        pendencias: str,
    ) -> dict[str, Any]:
        """
        Módulo 3 do RAG: Sugere despacho para o avaliador.
        
        Args:
            texto_documento: Texto do documento.
            pendencias: Descrição das pendências.
            
        Returns:
            dict: {"despacho": str, "motivo": str, ...}
            
        Raises:
            httpx.HTTPError: Se requisição falhar.
        """
        payload = {
            "texto": texto_documento,
            "pendencias": pendencias,
        }
        response = await self.client.post(
            f"{self.base_url}/ia/despacho",
            json=payload,
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