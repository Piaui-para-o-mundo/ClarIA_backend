from fastapi.testclient import TestClient

import app.core.database as _db


async def _noop():
    return None


_db.init_db = _noop
_db.close_db = _noop

from src.app.api.routes.dispatch import _build_dispatch_context
from src.main import create_app


app = create_app()
client = TestClient(app)


def test_dispatch_preview_renders_html():
    payload = {
        'setor_destino_sugerido': 'DGP/DAOS',
        'assunto': 'Progressão Funcional',
        'corpo_despacho': 'DESPACHO\nLinha 2',
        'referencias_normativas': [
            'Regulamento de Progressão Funcional da UESPI'
        ],
        'justificativa_encaminhamento': 'Pendencias documentais identificadas.',
        'status_sugerido': 'devolvido',
    }

    response = client.post('/api/v1/dispatch/preview', json=payload)

    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    assert 'Progressão Funcional' in response.text
    assert 'DGP/DAOS' in response.text
    assert 'Pendencias documentais identificadas.' in response.text


def test_shared_dispatch_context_uses_same_template_data():
    class Usuario:
        nome = 'Jéssica Silva'
        setor = 'Departamento Acadêmico'
        matricula = '123456'

    class Processo:
        numero = 'CPPD-35A/2026'
        tipo = 'afastamento'
        usuario = Usuario()

    context = _build_dispatch_context(
        Processo(),
        setor_destino_sugerido='CPPD / GABINETE',
        assunto='Despacho do Processo nº CPPD-35A/2026',
        corpo_despacho='Linha 1\n\nLinha 2',
        processo_numero='CPPD-35A/2026',
        numero_despacho='PREVIEW/2026',
    )

    assert context['processo_numero'] == 'CPPD-35A/2026'
    assert context['setor_destino_sugerido'] == 'CPPD / GABINETE'
    assert context['assunto'] == 'Despacho do Processo nº CPPD-35A/2026'
    assert context['corpo_despacho'] == 'Linha 1\n\nLinha 2'
    assert context['professor_nome'] == 'Jéssica Silva'
    assert context['professor_setor'] == 'Departamento Acadêmico'
    assert context['professor_matricula'] == '123456'
    assert context['numero_despacho'] == 'PREVIEW/2026'


def test_shared_dispatch_context_replaces_body_placeholders():
    class Usuario:
        nome = 'Jéssica Silva'
        setor = 'Departamento Acadêmico'
        matricula = '123456'

    class Processo:
        numero = 'CPPD-35A/2026'
        tipo = 'afastamento'
        usuario = Usuario()

    context = _build_dispatch_context(
        Processo(),
        setor_destino_sugerido='CPPD / GABINETE',
        assunto='Despacho do Processo nº CPPD-35A/2026',
        corpo_despacho=(
            'PROCESSO Nº: [numero_processo]\n'
            'Requerente: [nome_requerente], [cargo]\n'
            'Matrícula: [matricula]\n'
            'Lotação: [lotacao]\n'
            'Documento assinado eletronicamente por [AUTORIDADE], em [DATA_ATUAL].'
        ),
        processo_numero='CPPD-35A/2026',
        numero_despacho='PREVIEW/2026',
        emitido_em='25/05/2026',
    )

    assert '[numero_processo]' not in context['corpo_despacho']
    assert '[nome_requerente]' not in context['corpo_despacho']
    assert '[cargo]' not in context['corpo_despacho']
    assert '[matricula]' not in context['corpo_despacho']
    assert '[lotacao]' not in context['corpo_despacho']
    assert '[AUTORIDADE]' not in context['corpo_despacho']
    assert '[DATA_ATUAL]' not in context['corpo_despacho']
    assert 'CPPD-35A/2026' in context['corpo_despacho']
    assert 'Jéssica Silva' in context['corpo_despacho']
    assert 'Departamento Acadêmico' in context['corpo_despacho']
    assert '25/05/2026' in context['corpo_despacho']
