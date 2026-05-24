
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
        """Envia um documento para indexacao no servico RAG."""
        files = {
            "file": (filename, pdf_content, "application/pdf"),
        }
        response = await self.client.post(
            f"{self.base_url}/ia/ingest",
            files=files,
        )
        response.raise_for_status()
        return response.json()

    async def gerar_resumo(
        self,
        tipo_processo: str,
        textos_extraidos: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Solicita resumo executivo com base nos textos já extraídos."""
        response = await self.client.post(
            f"{self.base_url}/ia/resumo",
            json={
                "tipo_processo": tipo_processo,
                "textos_extraidos": textos_extraidos,
            },
        )
        response.raise_for_status()
        return response.json()

    async def verificar_conformidade(
        self,
        documentos: list[tuple[bytes, str]],
        type_process: str,
    ) -> dict[str, Any]:
        """Solicita verificação de conformidade documental enviando PDFs apenas uma vez."""
        files = [
            ("files", (nome, conteudo, "application/pdf"))
            for conteudo, nome in documentos
        ]

        response = await self.client.post(
            f"{self.base_url}/ia/conformidade",
            files=files,
            data={"type_process": type_process},
        )
        response.raise_for_status()
        return response.json()

    async def sugerir_despacho(
        self,
        checklist_result: dict[str, Any],
        resumo_texto: str = "",
    ) -> dict[str, Any]:
        """Solicita minuta de despacho a partir do checklist e do resumo executivo."""
        response = await self.client.post(
            f"{self.base_url}/ia/despacho",
            json={
                "checklist_result": checklist_result,
                "resumo_texto": resumo_texto,
            },
        )
        response.raise_for_status()
        return response.json()

    async def analisar_processo(
        self,
        documentos: list[tuple[bytes, str]],
        tipo_processo: str,
    ) -> dict[str, Any]:
        """
        Executa o fluxo novo da ClarIA RAG:
        - `/ia/conformidade` recebe os PDFs e devolve o checklist + textos extraídos
        - `/ia/resumo` trabalha só com os textos extraídos em JSON
        - `/ia/despacho` gera a minuta final com base no checklist e no resumo

        Args:
            documentos: Lista de tuplas (bytes_do_pdf, nome_do_arquivo).
            tipo_processo: Tipo do processo (ex: 'afastamento_pos_graduacao').

        Returns:
            dict: Resposta completa do RAG com checklist, resumo e despacho.

        Raises:
            httpx.HTTPError: Se requisição falhar.
        """
        conformidade = await self.verificar_conformidade(
            documentos=documentos,
            type_process=tipo_processo,
        )

        textos_extraidos = conformidade.get("textos_extraidos") or []
        checklist_result = conformidade.get("checklist") or conformidade

        resumo = await self.gerar_resumo(
            tipo_processo=tipo_processo,
            textos_extraidos=textos_extraidos,
        )

        resumo_texto = resumo.get("resumo") if isinstance(resumo, dict) else resumo

        despacho = await self.sugerir_despacho(
            checklist_result=checklist_result,
            resumo_texto=resumo_texto or "",
        )

        return {
            "checklist": checklist_result,
            "documentos_identificados": conformidade.get("documentos_identificados", []),
            "textos_extraidos": textos_extraidos,
            "resumo": resumo_texto,
            "despacho": {
                "corpo_despacho": despacho.get("despacho") if isinstance(despacho, dict) else despacho,
                "raw": despacho,
            },
            "raw": {
                "conformidade": conformidade,
                "resumo": resumo,
                "despacho": despacho,
            },
        }

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