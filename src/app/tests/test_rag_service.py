from unittest.mock import AsyncMock
import httpx
import pytest
from app.services.rag_service import RagClient

def _response(status_code: int, payload: dict | None = None) -> httpx.Response:
    request = httpx.Request("POST", "http://rag.local/ia/resumo")
    return httpx.Response(status_code=status_code, json=payload or {}, request=request)

@pytest.mark.asyncio
async def test_gerar_resumo_retorna_fallback_legado_quando_api_responder_422():
    client = RagClient(base_url="http://rag.local")
    client.client.post = AsyncMock(
        side_effect=[
            _response(422, {"detail": "Validation error"}),
            _response(200, {"resumo": "Resumo legado"}),
        ]
    )

    resultado = await client.gerar_resumo(
        tipo_processo="progressao_funcional",
        textos_extraidos=[{"nome": "scan001.pdf", "texto": "Conteudo extraido"}],
    )

    assert resultado == {"resumo": "Resumo legado"}
    assert client.client.post.await_count == 2
    assert client.client.post.await_args_list[0].kwargs["json"] == {
        "texto": "",
        "tipo_processo": "progressao_funcional",
        "textos_extraidos": [{"nome": "scan001.pdf", "texto": "Conteudo extraido"}],
    }
    assert client.client.post.await_args_list[1].kwargs["json"] == {
        "texto": "scan001.pdf\nConteudo extraido",
    }
    await client.close()

@pytest.mark.asyncio
async def test_gerar_resumo_nao_retry_sem_texto_legado():
    client = RagClient(base_url="http://rag.local")
    client.client.post = AsyncMock(return_value=_response(422, {"detail": "Validation error"}))

    with pytest.raises(httpx.HTTPStatusError):
        await client.gerar_resumo(
            tipo_processo="progressao_funcional",
            textos_extraidos=[],
        )
    assert client.client.post.await_count == 1
    await client.close()

@pytest.mark.asyncio
async def test_sugerir_despacho_falha_sem_fallback_no_422():
    client = RagClient(base_url="http://rag.local")
    client.client.post = AsyncMock(return_value=_response(422, {"detail": "Validation error"}))

    with pytest.raises(httpx.HTTPStatusError):
        await client.sugerir_despacho(
            checklist_result={
                "aprovado": False,
                "documentos_faltando": ["requerimento", "identificacao"],
            },
            resumo_texto="Resumo executivo",
        )
    assert client.client.post.await_count == 1
    await client.close()
