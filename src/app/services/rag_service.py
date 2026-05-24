
from typing import Any
import json
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
        self, tipo_processo: str, textos_extraidos: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Solicita resumo executivo usando os textos extraidos (sob demanda).

        Payload conforme DOC_API_RAG.md: { tipo_processo, textos_extraidos }
        """
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
        tipo_processo: str,
    ) -> dict[str, Any]:
        """
        Envia os PDFs para `/ia/conformidade` conforme DOC (multipart/form-data).

        Args:
            documentos: lista de tuples (bytes, filename)
            tipo_processo: string identificando o tipo do processo

        Retorna o JSON com checklist, textos_extraidos, etc.
        """
        files = [
            ("files", (nome, conteudo, "application/pdf"))
            for conteudo, nome in documentos
        ]
        data = {"type_process": tipo_processo}

        response = await self.client.post(
            f"{self.base_url}/ia/conformidade",
            files=files,
            data=data,
        )
        response.raise_for_status()
        return response.json()

    async def sugerir_despacho(
        self, checklist_result: dict[str, Any], resumo_texto: str = ""
    ) -> dict[str, Any]:
        """
        Solicita minuta de despacho com base no checklist e resumo executivo.

        Payload conforme DOC: { checklist_result, resumo_texto }
        """
        payload = {
            "checklist_result": checklist_result,
            "resumo_texto": resumo_texto,
        }
        response = await self.client.post(
            f"{self.base_url}/ia/despacho",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

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
        # Etapa 1: /ia/conformidade (envia PDFs e recebe checklist + textos_extraidos)
        conformidade = await self.verificar_conformidade(documentos=documentos, tipo_processo=tipo_processo)

        textos_extraidos = conformidade.get("textos_extraidos") or []
        checklist_result = conformidade.get("checklist") or conformidade

        # Etapa 2: /ia/resumo (sob demanda, usa textos_extraidos)
        resumo_response = await self.gerar_resumo(tipo_processo=tipo_processo, textos_extraidos=textos_extraidos)

        # Extrair texto do resumo em forma de string
        resumo_texto = ""
        if isinstance(resumo_response, dict):
            resumo_texto = resumo_response.get("resumo") or resumo_response.get("resultado") or ""
            if isinstance(resumo_texto, dict):
                resumo_texto = json.dumps(resumo_texto, ensure_ascii=False)
        elif isinstance(resumo_response, str):
            resumo_texto = resumo_response

        # Etapa 3: /ia/despacho (gera minuta a partir do checklist + resumo)
        despacho_response = await self.sugerir_despacho(checklist_result=checklist_result, resumo_texto=resumo_texto)

        # Extrair corpo do despacho (suporta várias chaves)
        despacho_texto = ""
        if isinstance(despacho_response, dict):
            despacho_texto = despacho_response.get("despacho") or despacho_response.get("corpo_despacho") or despacho_response.get("texto") or ""
            if isinstance(despacho_texto, dict):
                despacho_texto = json.dumps(despacho_texto, ensure_ascii=False)
        elif isinstance(despacho_response, str):
            despacho_texto = despacho_response

        return {
            "checklist": checklist_result,
            "documentos_identificados": conformidade.get("documentos_identificados", []),
            "textos_extraidos": textos_extraidos,
            "resumo": resumo_texto,
            "despacho": despacho_texto,
            "raw": {
                "conformidade": conformidade,
                "resumo": resumo_response,
                "despacho": despacho_response,
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