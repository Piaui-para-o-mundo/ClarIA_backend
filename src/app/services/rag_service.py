from typing import Any

import json
import httpx

from app.core.config import get_settings


class RagClient:
    """
    Cliente assíncrono para serviço RAG.
    
    Abstrai a comunicação HTTP com ClarIA RAG API.  
    Todos os métodos são corrotinas.
    """

    def __init__(self, base_url: str, timeout: int = 120):
        """
        Inicializa o cliente.

        Args:
            base_url: URL base do serviço RAG.
            timeout: Timeout em segundos para requisições (default: 120).
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

    async def verificar_conformidade(
        self,
        documentos: list[tuple[bytes, str]],
        type_process: str,
    ) -> dict[str, Any]:
        """
        Solicita verificação de conformidade documental enviando PDFs.
        
        Alinhado com a rota POST /ia/conformidade que espera:
        - files: List[UploadFile] (multipart)
        - type_process: str (form field)
        
        Retorna dict com:
        - status: "completo" | "incompleto"
        - checklist: {...}
        - documentos_identificados: [...]
        - textos_extraidos: [{"nome": str, "texto": str}, ...]
        """
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

    async def gerar_resumo(
        self,
        tipo_processo: str,
        textos_extraidos: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Solicita resumo executivo com base nos textos já extraídos.
        
        Alinhado com a rota POST /ia/resumo (ResumoRequest):
        - texto: str (campo legado, pode ser vazio)
        - tipo_processo: str
        - textos_extraidos: list[dict] com {nome, texto}
        
        Retorna dict com:
        - resumo: {status, modulo, arquivos_analisados, resultado: {...}}
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/ia/resumo",
                json={
                    "texto": "",  # Campo legado, não usado na nova arquitetura
                    "tipo_processo": tipo_processo,
                    "textos_extraidos": textos_extraidos,
                },
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422 and textos_extraidos:
                # Fallback: Junta tudo em uma string para a rota legada
                texto_legado = "\n".join([f"{t.get('nome', '')}\n{t.get('texto', '')}".strip() for t in textos_extraidos])
                resp_legado = await self.client.post(
                    f"{self.base_url}/ia/resumo",
                    json={"texto": texto_legado}
                )
                resp_legado.raise_for_status()
                return resp_legado.json()
            raise

    async def sugerir_despacho(
        self,
        checklist_result: dict[str, Any],
        resumo_texto: str = "",
    ) -> dict[str, Any]:
        """
        Solicita minuta de despacho a partir do checklist e do resumo executivo.
        
        Alinhado com a rota POST /ia/despacho (DespachoRequest):
        - texto: str (resumo executivo ou descrição do processo)
        - pendencias: str (lista de pendências em JSON ou texto)
        
        Retorna dict com corpo_despacho, etc.
        """
        # Montar o texto descritivo do processo para o LLM
        tipo_processo = checklist_result.get("tipo_processo", "não especificado")
        conformidade = checklist_result.get("conformidade_pct", "N/A")
        aprovado = checklist_result.get("aprovado", False)
        
        texto = f"Tipo de processo: {tipo_processo}\n"
        texto += f"Conformidade: {conformidade}%\n"
        texto += f"Aprovado: {'Sim' if aprovado else 'Não'}\n"
        if resumo_texto:
            texto += f"\nResumo Executivo:\n{resumo_texto}\n"
        
        # Extrair pendências do checklist para enviar como string
        pendencias_list = checklist_result.get("documentos_faltando", [])
        if pendencias_list:
            pendencias_str = json.dumps(pendencias_list, ensure_ascii=False)
        else:
            pendencias_str = "Nenhuma pendência identificada."

        try:
            response = await self.client.post(
                f"{self.base_url}/ia/despacho",
                json={
                    "texto": texto,
                    "pendencias": pendencias_str,
                },
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                # Fallback: modelo legado do /ia/despacho
                resp_legado = await self.client.post(
                    f"{self.base_url}/ia/despacho",
                    json={
                        "texto": resumo_texto,
                        "pendencias": "\n".join(pendencias_list) if pendencias_list else "",
                    }
                )
                resp_legado.raise_for_status()
                return resp_legado.json()
            raise

    async def analisar_processo(
        self,
        documentos: list[tuple[bytes, str]],
        tipo_processo: str,
    ) -> dict[str, Any]:
        """
        Executa o fluxo completo da ClarIA RAG:
        1. /ia/conformidade → recebe PDFs e devolve checklist + textos extraídos
        2. /ia/resumo       → trabalha com os textos extraídos em JSON
        3. /ia/despacho     → gera minuta final com base no checklist e resumo

        Args:
            documentos: Lista de tuplas (bytes_do_pdf, nome_do_arquivo).
            tipo_processo: Tipo do processo (ex: 'progressao_funcional').

        Returns:
            dict com: checklist, resumo (string), despacho (string), 
                      documentos_identificados, textos_extraidos
        """
        # ── ETAPA 1: Conformidade ──
        conformidade = await self.verificar_conformidade(
            documentos=documentos,
            type_process=tipo_processo,
        )

        textos_extraidos = conformidade.get("textos_extraidos") or []
        checklist_result = conformidade.get("checklist") or conformidade

        # ── ETAPA 2: Resumo ──
        resumo_response = await self.gerar_resumo(
            tipo_processo=tipo_processo,
            textos_extraidos=textos_extraidos,
        )

        # Extrair a string do resumo — pode estar em vários formatos
        resumo_texto = self._extrair_resumo_texto(resumo_response)

        # ── ETAPA 3: Despacho ──
        despacho_response = await self.sugerir_despacho(
            checklist_result=checklist_result,
            resumo_texto=resumo_texto,
        )

        # Extrair corpo do despacho
        despacho_texto = self._extrair_despacho_texto(despacho_response)

        return {
            "checklist": checklist_result,
            "documentos_identificados": conformidade.get("documentos_identificados", []),
            "textos_extraidos": textos_extraidos,
            "resumo": resumo_texto,    # Sempre string
            "despacho": despacho_texto, # Sempre string
            "raw": {
                "conformidade": conformidade,
                "resumo": resumo_response,
                "despacho": despacho_response,
            },
        }

    @staticmethod
    def _extrair_resumo_texto(resumo_response: Any) -> str:
        """
        Extrai uma STRING de resumo do retorno da API /ia/resumo.
        
        A resposta pode vir em vários formatos:
        - {"resumo": {"resultado": {"tipo_solicitacao": ...}}}
        - {"resumo": {"resultado": "texto livre"}}
        - {"resumo": "texto livre"}
        - "texto livre"
        """
        if isinstance(resumo_response, str):
            return resumo_response

        if not isinstance(resumo_response, dict):
            return str(resumo_response)

        resumo_inner = resumo_response.get("resumo", resumo_response)
        
        if isinstance(resumo_inner, str):
            return resumo_inner

        if isinstance(resumo_inner, dict):
            resultado = resumo_inner.get("resultado", resumo_inner)
            if isinstance(resultado, str):
                return resultado
            if isinstance(resultado, dict):
                return json.dumps(resultado, ensure_ascii=False, indent=2)
        
        return json.dumps(resumo_response, ensure_ascii=False, indent=2)

    @staticmethod
    def _extrair_despacho_texto(despacho_response: Any) -> str:
        """
        Extrai uma STRING de despacho do retorno da API /ia/despacho.
        
        A resposta pode vir em vários formatos:
        - {"corpo_despacho": "texto...", ...}
        - {"despacho": "texto...", ...}
        - "texto livre"
        """
        if isinstance(despacho_response, str):
            return despacho_response

        if not isinstance(despacho_response, dict):
            return str(despacho_response)

        # Tentar extrair de chaves conhecidas
        for key in ("corpo_despacho", "despacho", "texto", "resultado"):
            val = despacho_response.get(key)
            if val and isinstance(val, str):
                return val
        
        # Se nenhuma chave conhecida, serializar tudo
        return json.dumps(despacho_response, ensure_ascii=False, indent=2)

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