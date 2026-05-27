import asyncio
import json
from typing import Any, AsyncGenerator
import httpx

from app.core.config import get_settings


class RagClient:
    """
    Cliente assíncrono para serviço RAG.

    Abstrai a comunicação HTTP com ClarIA RAG API.
    Todos os métodos são corrotinas.
    """

    def __init__(self, base_url: str, timeout: int = 120):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))

    async def _post_with_retry(
        self, endpoint: str, max_retries: int = 3, **kwargs
    ) -> dict[str, Any]:
        """Faz um POST com retentativas em erros de rede ou servidor (5xx)."""
        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    f'{self.base_url}{endpoint}', **kwargs
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # Não retenta em caso de erro 4xx (problema na requisição), apenas 5xx
                if e.response.status_code < 500 or attempt == max_retries - 1:
                    raise
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == max_retries - 1:
                    raise
            await asyncio.sleep(2**attempt)

    async def health_check(self) -> bool:
        try:
            response = await self.client.get(f'{self.base_url}/ia/health')
            return response.status_code == 200
        except Exception:
            return False

    async def verificar_conformidade(
        self,
        documentos: list[tuple[bytes, str]],
        type_process: str,
    ) -> dict[str, Any]:
        files = [
            ('files', (nome, conteudo, 'application/pdf'))
            for conteudo, nome in documentos
        ]
        # Não usaremos _post_with_retry aqui pois arquivos grandes não devem ser re-enviados sem critério
        response = await self.client.post(
            f'{self.base_url}/ia/conformidade',
            files=files,
            data={'type_process': type_process},
        )
        response.raise_for_status()
        return response.json()

    async def gerar_resumo(
        self, tipo_processo: str, textos_extraidos: list[dict[str, Any]]
    ) -> dict[str, Any]:
        try:
            return await self._post_with_retry(
                '/ia/resumo',
                json={
                    'texto': '',
                    'tipo_processo': tipo_processo,
                    'textos_extraidos': textos_extraidos,
                },
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422 and textos_extraidos:
                # Fallback: Junta tudo em uma string para a rota legada
                texto_legado = '\n'.join(
                    [
                        f"{t.get('nome', '')}\n{t.get('texto', '')}".strip()
                        for t in textos_extraidos
                    ]
                )
                return await self._post_with_retry(
                    '/ia/resumo', json={'texto': texto_legado}
                )
            raise

    async def sugerir_despacho(
        self,
        checklist_result: dict[str, Any],
        resumo_texto: str = '',
        integridade_result: dict[str, Any] = None,
    ) -> dict[str, Any]:
        tipo_processo = checklist_result.get(
            'tipo_processo', 'não especificado'
        )
        conformidade = checklist_result.get('conformidade_pct', 'N/A')
        aprovado = checklist_result.get('aprovado', False)
        tramitacao = checklist_result.get('tramitacao_prevista', [])

        texto_partes = [
            f'Tipo de processo: {tipo_processo}',
            f'Conformidade: {conformidade}%',
            f"Aprovado: {'Sim' if aprovado else 'Não'}",
        ]
        if tramitacao:
            texto_partes.append(
                f"Fluxo de Tramitação: {' -> '.join(tramitacao)}"
            )
        if resumo_texto:
            texto_partes.append(f'\nResumo Executivo:\n{resumo_texto}')

        texto_completo = '\n'.join(texto_partes) + '\n'

        pendencias_list = checklist_result.get('documentos_faltando', [])
        if integridade_result and not integridade_result.get('aprovado', True):
            pendencias_list.extend(
                [
                    {
                        'tipo_documento': erro.get('documento', ''),
                        'descricao': erro.get('descricao', ''),
                        'observacao': erro.get('sugestao', ''),
                    }
                    for erro in integridade_result.get('erros', [])
                ]
            )

        import re

        if resumo_texto:
            match = re.search(
                r'PONTOS? DE ATENÇÃO:(.*?)(?:\n\n|\Z)',
                resumo_texto,
                re.IGNORECASE | re.DOTALL,
            )
            if match:
                pontos = match.group(1).strip()
                if pontos and not pontos.lower().startswith(
                    ('nenhum', 'não há', 'n/a')
                ):
                    pendencias_list.append(
                        {
                            'tipo_documento': 'Análise Técnica',
                            'descricao': 'Inconsistências encontradas.',
                            'observacao': pontos,
                        }
                    )

        pendencias_str = (
            json.dumps(pendencias_list, ensure_ascii=False)
            if pendencias_list
            else 'Nenhuma pendência.'
        )

        return await self._post_with_retry(
            '/ia/despacho',
            json={'texto': texto_completo, 'pendencias': pendencias_str},
        )

    async def analisar_processo(
        self, documentos: list[tuple[bytes, str]], tipo_processo: str
    ) -> dict[str, Any]:
        conformidade = await self.verificar_conformidade(
            documentos, tipo_processo
        )
        textos = conformidade.get('textos_extraidos') or []
        checklist = conformidade.get('checklist') or conformidade

        resumo_resp = await self.gerar_resumo(tipo_processo, textos)
        resumo_texto = self._extrair_texto(
            resumo_resp,
            ('resumo', 'texto', 'conteudo', 'analise', 'resultado'),
        )

        despacho_resp = await self.sugerir_despacho(
            checklist, resumo_texto, conformidade.get('integridade')
        )
        despacho_texto = self._extrair_texto(
            despacho_resp, ('corpo_despacho', 'despacho', 'texto', 'resultado')
        )

        return {
            'checklist': checklist,
            'documentos_identificados': conformidade.get(
                'documentos_identificados', []
            ),
            'textos_extraidos': textos,
            'resumo': resumo_texto,
            'despacho': despacho_texto,
            'raw': {
                'conformidade': conformidade,
                'resumo': resumo_resp,
                'despacho': despacho_resp,
            },
        }

    @staticmethod
    def _extrair_texto(response: Any, chaves: tuple[str, ...]) -> str:
        """Função unificada para extrair o valor string mais provável de um objeto JSON aninhado."""
        if isinstance(response, str):
            res_str = response
        elif not isinstance(response, dict):
            res_str = str(response)
        else:
            res_str = None
            # Busca direta no primeiro nível
            for key in chaves:
                if isinstance(response.get(key), str):
                    res_str = response[key]
                    break

            # Busca no segundo nível se houver sub-dicionários
            if not res_str:
                for val in response.values():
                    if isinstance(val, dict):
                        for key in chaves:
                            if isinstance(val.get(key), str):
                                res_str = val[key]
                                break
                    if res_str:
                        break

            if not res_str:
                res_str = json.dumps(response, ensure_ascii=False, indent=2)

        res_str = res_str.strip()
        if res_str.startswith('{') and res_str.endswith('}'):
            try:
                temp_obj = json.loads(res_str)
                return RagClient._extrair_texto(temp_obj, chaves)
            except Exception:
                pass

        return res_str

    async def close(self) -> None:
        await self.client.aclose()


async def get_rag_client() -> AsyncGenerator[RagClient, None]:
    settings = get_settings()
    client = RagClient(
        base_url=settings.rag_service_url, timeout=settings.rag_service_timeout
    )
    try:
        yield client
    finally:
        await client.close()
