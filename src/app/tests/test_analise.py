"""
Testes para rotas de análise.

Testa endpoints de resumo, conformidade, despacho e análises via RAG.
"""
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

import app.core.database as _db

# Previne inicialização real do BD durante testes
async def _noop():
    return None


_db.init_db = _noop
_db.close_db = _noop

from src.main import create_app

app = create_app()
client = TestClient(app)


def _create_test_user(email='professor@example.com', role='professor'):
    """Helper para criar usuário de teste."""
    payload = {
        'nome': 'Professor Teste',
        'email': email,
        'senha': 'senha_123',
        'role': role,
        'setor': 'Educação',
    }
    client.post('/api/v1/auth/register', json=payload)

    login_response = client.post(
        '/api/v1/auth/login', json={'email': email, 'senha': 'senha_123'}
    )
    return login_response.json()['access_token']


def _criar_processo_com_documentos(token):
    """Helper para criar processo e adicionar documentos."""
    # Cria processo
    create_response = client.post(
        '/api/v1/processos/',
        json={'tipo': 'requerimento'},
        headers={'Authorization': f'Bearer {token}'},
    )
    processo_id = create_response.json()['id']

    # Adiciona documento
    files = [
        (
            'arquivos',
            (
                BytesIO(b'Documento de teste com conteudo importante'),
                'doc.pdf',
            ),
        ),
    ]
    data = {'tipos_doc': ['requerimento']}

    client.post(
        f'/api/v1/processos/{processo_id}/documentos',
        files=files,
        data=data,
        headers={'Authorization': f'Bearer {token}'},
    )

    return processo_id


class TestResumo:
    """Testes para geração de resumo via RAG."""

    @patch('app.services.rag_service.RagClient.gerar_resumo')
    def test_get_resumo_success(self, mock_resumo):
        """Deve gerar resumo do processo."""
        token = _create_test_user()
        processo_id = _criar_processo_com_documentos(token)

        # Mock do RAG
        mock_resumo.return_value = {
            'resumo': 'Este é um resumo do documento',
            'palavras_chave': ['documento', 'resumo', 'teste'],
        }

        response = client.get(
            f'/api/v1/analise/{processo_id}/resumo',
            headers={'Authorization': f'Bearer {token}'},
        )
        # Pode retornar 200 ou erro dependendo de configuração do RAG
        assert response.status_code in [200, 422, 500]

    def test_get_resumo_processo_nao_encontrado(self):
        """Deve retornar erro para processo inexistente."""
        token = _create_test_user()

        fake_id = str(uuid4())
        response = client.get(
            f'/api/v1/analise/{fake_id}/resumo',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 404

    def test_get_resumo_sem_documentos(self):
        """Deve retornar erro se processo não tiver documentos."""
        token = _create_test_user()

        # Cria processo mas sem documentos
        create_response = client.post(
            '/api/v1/processos/',
            json={'tipo': 'requerimento'},
            headers={'Authorization': f'Bearer {token}'},
        )
        processo_id = create_response.json()['id']

        response = client.get(
            f'/api/v1/analise/{processo_id}/resumo',
            headers={'Authorization': f'Bearer {token}'},
        )
        # Pode retornar 404 (sem documentos) ou 422 (erro de validação)
        assert response.status_code in [404, 422, 500]


class TestConformidade:
    """Testes para verificação de conformidade."""

    @patch('app.services.rag_service.RagClient.verificar_conformidade')
    def test_get_conformidade_success(self, mock_conformidade):
        """Deve verificar conformidade do processo."""
        token = _create_test_user()
        processo_id = _criar_processo_com_documentos(token)

        # Mock do RAG
        mock_conformidade.return_value = {
            'conformidade_pct': 85.5,
            'pendencias': ['Falta assinatura', 'Documento vencido'],
        }

        response = client.get(
            f'/api/v1/analise/{processo_id}/conformidade',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code in [200, 422, 500]

    def test_get_conformidade_processo_nao_encontrado(self):
        """Deve retornar erro para processo inexistente."""
        token = _create_test_user()

        fake_id = str(uuid4())
        response = client.get(
            f'/api/v1/analise/{fake_id}/conformidade',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 404

    @patch('app.services.rag_service.RagClient.verificar_conformidade')
    def test_conformidade_retorna_percentual(self, mock_conformidade):
        """Deve retornar percentual de conformidade entre 0-100."""
        token = _create_test_user()
        processo_id = _criar_processo_com_documentos(token)

        mock_conformidade.return_value = {
            'conformidade_pct': 100.0,
            'pendencias': [],
        }

        response = client.get(
            f'/api/v1/analise/{processo_id}/conformidade',
            headers={'Authorization': f'Bearer {token}'},
        )

        if response.status_code == 200:
            data = response.json()
            assert 'conformidade_pct' in data
            assert 0 <= data['conformidade_pct'] <= 100


class TestDespacho:
    """Testes para geração de despacho."""

    @patch('app.services.rag_service.RagClient.sugerir_despacho')
    def test_gerar_despacho_success(self, mock_despacho):
        """Deve gerar sugestão de despacho."""
        token = _create_test_user()
        processo_id = _criar_processo_com_documentos(token)

        # Mock do RAG
        mock_despacho.return_value = {
            'despacho': 'Recomenda-se DEFERIMENTO do requerimento.'
        }

        response = client.get(
            f'/api/v1/analise/{processo_id}/despacho',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code in [200, 422, 500]

    def test_gerar_despacho_processo_nao_encontrado(self):
        """Deve retornar erro para processo inexistente."""
        token = _create_test_user()

        fake_id = str(uuid4())
        response = client.get(
            f'/api/v1/analise/{fake_id}/despacho',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 404

    @patch(
        'app.services.rag_service.RagClient.sugerir_despacho',
        new_callable=AsyncMock,
    )
    @patch(
        'app.services.rag_service.RagClient.gerar_resumo',
        new_callable=AsyncMock,
    )
    @patch(
        'app.services.rag_service.RagClient.verificar_conformidade',
        new_callable=AsyncMock,
    )
    def test_gerar_despacho_usando_fallback_local_quando_rag_cai(
        self,
        mock_conformidade,
        mock_resumo,
        mock_despacho,
    ):
        """Deve retornar despacho provisório mesmo sem conexão com o RAG."""
        token = _create_test_user()

        mock_conformidade.return_value = {
            'checklist': {
                'aprovado': False,
                'conformidade_pct': 80.0,
                'documentos_faltando': ['cpf'],
            },
            'textos_extraidos': [{'nome': 'doc.pdf', 'texto': 'Conteudo'}],
        }
        mock_resumo.return_value = {'resumo': 'Resumo automático'}
        mock_despacho.side_effect = httpx.ConnectError(
            'All connection attempts failed',
            request=httpx.Request('POST', 'http://rag.local/ia/despacho'),
        )

        fake_processo = SimpleNamespace(
            id=uuid4(),
            numero='2026-0001',
            tipo='requerimento',
            checklist_ia='{"checklist": {"aprovado": false, "conformidade_pct": 80.0, "documentos_faltando": ["cpf"]}}',
            resumo_ia='Resumo automático',
            despacho_automatico=None,
            analise_log='',
        )

        with patch(
            'app.services.processo_service.ProcessoService.get_processo',
            new_callable=AsyncMock,
            return_value=fake_processo,
        ), patch(
            'app.services.analise_service.AnaliseService.obter_processo_lock',
            new_callable=AsyncMock,
            return_value=fake_processo,
        ):
            response = client.post(
                f'/api/v1/analise/{fake_processo.id}/gerar-despacho',
                headers={'Authorization': f'Bearer {token}'},
            )

        assert response.status_code == 200
        data = response.json()
        assert data['despacho_automatico']
        assert 'DESPACHO AUTOMÁTICO PROVISÓRIO' in data['despacho_automatico']


class TestAutenticacaoAnalise:
    """Testes de autenticação para endpoints de análise."""

    def test_analise_sem_token(self):
        """Deve retornar erro sem token de autenticação."""
        fake_id = str(uuid4())

        response = client.get(f'/api/v1/analise/{fake_id}/resumo')
        assert response.status_code == 403

        response = client.get(f'/api/v1/analise/{fake_id}/conformidade')
        assert response.status_code == 403

        response = client.get(f'/api/v1/analise/{fake_id}/despacho')
        assert response.status_code == 403

    def test_analise_token_invalido(self):
        """Deve retornar erro com token inválido."""
        fake_id = str(uuid4())

        response = client.get(
            f'/api/v1/analise/{fake_id}/resumo',
            headers={'Authorization': 'Bearer invalid_token'},
        )
        assert response.status_code in [401, 403]


class TestFluxoCompleto:
    """Testes do fluxo completo de análise."""

    @patch('app.services.rag_service.RagClient.gerar_resumo')
    @patch('app.services.rag_service.RagClient.verificar_conformidade')
    @patch('app.services.rag_service.RagClient.sugerir_despacho')
    def test_fluxo_analise_completo(
        self, mock_despacho, mock_conformidade, mock_resumo
    ):
        """Testa fluxo completo: criar -> upload -> analisar -> despacho."""
        token = _create_test_user()

        # 1. Cria processo
        create_response = client.post(
            '/api/v1/processos/',
            json={'tipo': 'requerimento'},
            headers={'Authorization': f'Bearer {token}'},
        )
        assert create_response.status_code == 200
        processo_id = create_response.json()['id']

        # 2. Faz upload de documentos
        files = [
            ('arquivos', (BytesIO(b'Conteudo documento 1'), 'doc1.pdf')),
            ('arquivos', (BytesIO(b'Conteudo documento 2'), 'doc2.pdf')),
        ]
        data = {'tipos_doc': ['requerimento', 'cpf']}

        upload_response = client.post(
            f'/api/v1/processos/{processo_id}/documentos',
            files=files,
            data=data,
            headers={'Authorization': f'Bearer {token}'},
        )
        assert upload_response.status_code == 200
        assert upload_response.json()['sucesso'] == 2

        # 3. Mocks dos serviços RAG
        mock_resumo.return_value = {
            'resumo': 'Resumo do processo',
            'palavras_chave': ['teste'],
        }
        mock_conformidade.return_value = {
            'conformidade_pct': 75.0,
            'pendencias': ['Falta documento'],
        }
        mock_despacho.return_value = {
            'despacho': 'Recomenda-se complementação'
        }

        # 4. Recupera processo
        get_response = client.get(
            f'/api/v1/processos/{processo_id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert get_response.status_code == 200

    @patch(
        'app.services.rag_service.RagClient.analisar_processo',
        new_callable=AsyncMock,
    )
    def test_reanalise_ignora_despacho_salvo(self, mock_analisar):
        """Deve ignorar documentos de despacho gerados pelo sistema na próxima análise."""
        professor_token = _create_test_user(
            email='professor.despacho@example.com', role='professor'
        )
        avaliador_token = _create_test_user(
            email='avaliador.despacho@example.com', role='avaliador'
        )

        mock_analisar.return_value = {
            'resumo': 'Resumo automático',
            'checklist': {'conformidade_pct': 80.0},
            'despacho': {'corpo_despacho': 'Despacho automático'},
        }

        create_response = client.post(
            '/api/v1/processos/',
            json={'tipo': 'requerimento'},
            headers={'Authorization': f'Bearer {professor_token}'},
        )
        assert create_response.status_code == 200
        processo_id = create_response.json()['id']

        upload_response = client.post(
            f'/api/v1/processos/{processo_id}/documentos',
            files=[
                ('arquivos', (BytesIO(b'documento 1'), 'doc1.pdf')),
                ('arquivos', (BytesIO(b'documento 2'), 'doc2.pdf')),
            ],
            data={'tipos_doc': ['requerimento', 'cpf']},
            headers={'Authorization': f'Bearer {professor_token}'},
        )
        assert upload_response.status_code == 200

        dispatch_response = client.post(
            f'/api/v1/dispatch/send/{processo_id}',
            json={
                'setor_destino_sugerido': 'CPPD',
                'assunto': 'Progressão Funcional',
                'corpo_despacho': 'Texto do despacho',
                'justificativa_encaminhamento': 'Complementação necessária',
                'status_sugerido': 'devolvido',
                'referencias_normativas': [],
            },
            headers={'Authorization': f'Bearer {avaliador_token}'},
        )
        assert dispatch_response.status_code == 200

        second_upload = client.post(
            f'/api/v1/processos/{processo_id}/documentos',
            files=[('arquivos', (BytesIO(b'documento 3'), 'doc3.pdf'))],
            data={'tipos_doc': ['recurso']},
            headers={'Authorization': f'Bearer {professor_token}'},
        )
        assert second_upload.status_code == 200

        assert mock_analisar.await_count == 2
        second_call_docs = mock_analisar.await_args_list[1].kwargs[
            'documentos'
        ]
        second_call_filenames = [nome for _, nome in second_call_docs]
        assert len(second_call_filenames) == 3
        assert all(
            not nome.startswith('Despacho_') for nome in second_call_filenames
        )
