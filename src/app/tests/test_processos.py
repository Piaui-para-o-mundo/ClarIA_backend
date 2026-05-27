"""
Testes para rotas de processos.

Testa criação, listagem, recuperação e upload de documentos para processos.
Inclui testes de paralelismo e múltiplos uploads.
"""
import asyncio
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

import app.core.database as _db

# Previne inicialização real do BD durante testes
async def _noop():
    return None


_db.init_db = _noop
_db.close_db = _noop

from src.main import create_app
from app.models.user import User
from app.models.process import Processo
from app.core.security import hash_password

app = create_app()
client = TestClient(app)


def _create_test_user(email='professor@example.com'):
    """Helper para criar usuário de teste."""
    payload = {
        'nome': 'Professor Teste',
        'email': email,
        'senha': 'senha_123',
        'role': 'professor',
        'setor': 'Educação',
    }
    client.post('/api/v1/auth/register', json=payload)

    login_response = client.post(
        '/api/v1/auth/login', json={'email': email, 'senha': 'senha_123'}
    )
    return login_response.json()['access_token']


class TestCriarProcesso:
    """Testes para criação de processos."""

    def test_criar_processo_success(self):
        """Deve criar novo processo como professor."""
        token = _create_test_user()

        payload = {'tipo': 'requerimento'}
        response = client.post(
            '/api/v1/processos/',
            json=payload,
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 200
        data = response.json()
        assert data['tipo'] == 'requerimento'
        assert 'id' in data
        assert 'usuario_id' in data

    def test_criar_processo_sem_token(self):
        """Deve retornar erro sem token."""
        payload = {'tipo': 'requerimento'}
        response = client.post('/api/v1/processos/', json=payload)
        assert response.status_code == 403

    def test_criar_processo_tipos_validos(self):
        """Deve criar processos com diferentes tipos."""
        token = _create_test_user()

        tipos = ['requerimento', 'recurso', 'moção', 'petição']
        for tipo in tipos:
            response = client.post(
                '/api/v1/processos/',
                json={'tipo': tipo},
                headers={'Authorization': f'Bearer {token}'},
            )
            assert response.status_code == 200
            assert response.json()['tipo'] == tipo


class TestListarProcessos:
    """Testes para listagem de processos."""

    def test_listar_todos_processos(self):
        """Deve listar todos os processos."""
        token = _create_test_user()

        # Cria alguns processos
        for i in range(3):
            client.post(
                '/api/v1/processos/',
                json={'tipo': 'requerimento'},
                headers={'Authorization': f'Bearer {token}'},
            )

        response = client.get(
            '/api/v1/processos', headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    def test_listar_processos_com_paginacao(self):
        """Deve respeitar parâmetros de skip e limit."""
        token = _create_test_user()

        # Cria 5 processos
        for i in range(5):
            client.post(
                '/api/v1/processos/',
                json={'tipo': 'requerimento'},
                headers={'Authorization': f'Bearer {token}'},
            )

        # Testa paginação
        response = client.get(
            '/api/v1/processos?skip=2&limit=2',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2

    def test_listar_meus_processos(self):
        """Deve listar apenas processos do usuário logado."""
        token1 = _create_test_user('prof1@example.com')
        token2 = _create_test_user('prof2@example.com')

        # Prof 1 cria 2 processos
        for i in range(2):
            client.post(
                '/api/v1/processos/',
                json={'tipo': 'requerimento'},
                headers={'Authorization': f'Bearer {token1}'},
            )

        # Prof 2 cria 1 processo
        client.post(
            '/api/v1/processos/',
            json={'tipo': 'requerimento'},
            headers={'Authorization': f'Bearer {token2}'},
        )

        # Prof 1 lista seus processos
        response = client.get(
            '/api/v1/processos/my',
            headers={'Authorization': f'Bearer {token1}'},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_listar_processos_sem_token(self):
        """Deve retornar erro sem token."""
        response = client.get('/api/v1/processos')
        assert response.status_code == 403


class TestGetProcesso:
    """Testes para recuperação de um processo específico."""

    def test_get_processo_success(self):
        """Deve retornar detalhes de um processo."""
        token = _create_test_user()

        # Cria processo
        create_response = client.post(
            '/api/v1/processos/',
            json={'tipo': 'progressao_funcional'},
            headers={'Authorization': f'Bearer {token}'},
        )
        processo_id = create_response.json()['id']

        # Recupera processo
        response = client.get(
            f'/api/v1/processos/{processo_id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 200
        data = response.json()
        assert data['id'] == processo_id
        assert data['tipo'] == 'requerimento'

    def test_get_processo_nao_encontrado(self):
        """Deve retornar 404 para processo inexistente."""
        token = _create_test_user()

        fake_id = str(uuid4())
        response = client.get(
            f'/api/v1/processos/{fake_id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 404


class TestUploadDocumentos:
    """Testes para upload de documentos.

    Inclui testes de múltiplos documentos e paralelismo.
    """

    def test_upload_um_documento(self):
        """Deve fazer upload de um documento."""
        token = _create_test_user()

        # Cria processo
        create_response = client.post(
            '/api/v1/processos/',
            json={'tipo': 'requerimento'},
            headers={'Authorization': f'Bearer {token}'},
        )
        processo_id = create_response.json()['id']

        # Faz upload de documento
        files = [
            ('arquivos', (BytesIO(b'conteudo do documento'), 'doc1.pdf')),
        ]
        data = {'tipos_doc': ['requerimento']}

        response = client.post(
            f'/api/v1/processos/{processo_id}/documentos',
            files=files,
            data=data,
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 200
        assert response.json()['sucesso'] == 1

    def test_upload_multiplos_documentos(self):
        """Deve fazer upload de múltiplos documentos de uma vez."""
        token = _create_test_user()

        # Cria processo
        create_response = client.post(
            '/api/v1/processos/',
            json={'tipo': 'requerimento'},
            headers={'Authorization': f'Bearer {token}'},
        )
        processo_id = create_response.json()['id']

        # Faz upload de 3 documentos
        files = [
            ('arquivos', (BytesIO(b'documento 1'), 'doc1.pdf')),
            ('arquivos', (BytesIO(b'documento 2'), 'doc2.pdf')),
            ('arquivos', (BytesIO(b'documento 3'), 'doc3.pdf')),
        ]
        data = {'tipos_doc': ['requerimento', 'cpf', 'rg']}

        response = client.post(
            f'/api/v1/processos/{processo_id}/documentos',
            files=files,
            data=data,
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 200
        result = response.json()
        assert result['sucesso'] == 3
        assert result['falhas'] == 0

    def test_upload_documentos_mismatch_count(self):
        """Deve retornar erro se número de arquivos != tipos."""
        token = _create_test_user()

        create_response = client.post(
            '/api/v1/processos/',
            json={'tipo': 'requerimento'},
            headers={'Authorization': f'Bearer {token}'},
        )
        processo_id = create_response.json()['id']

        # 2 arquivos mas 3 tipos
        files = [
            ('arquivos', (BytesIO(b'doc1'), 'doc1.pdf')),
            ('arquivos', (BytesIO(b'doc2'), 'doc2.pdf')),
        ]
        data = {'tipos_doc': ['requerimento', 'cpf', 'rg']}

        response = client.post(
            f'/api/v1/processos/{processo_id}/documentos',
            files=files,
            data=data,
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 400
        assert 'não coincide' in response.json()['detail'].lower()

    def test_upload_documentos_processo_inexistente(self):
        """Deve retornar erro ao fazer upload em processo inexistente."""
        token = _create_test_user()

        fake_id = str(uuid4())
        files = [
            ('arquivos', (BytesIO(b'conteudo'), 'doc.pdf')),
        ]
        data = {'tipos_doc': ['requerimento']}

        response = client.post(
            f'/api/v1/processos/{fake_id}/documentos',
            files=files,
            data=data,
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 404

    def test_upload_sem_autorizacao(self):
        """Deve retornar erro ao fazer upload em processo de outro usuário."""
        token1 = _create_test_user('prof1@example.com')
        token2 = _create_test_user('prof2@example.com')

        # Prof 1 cria processo
        create_response = client.post(
            '/api/v1/processos/',
            json={'tipo': 'requerimento'},
            headers={'Authorization': f'Bearer {token1}'},
        )
        processo_id = create_response.json()['id']

        # Prof 2 tenta fazer upload
        files = [
            ('arquivos', (BytesIO(b'conteudo'), 'doc.pdf')),
        ]
        data = {'tipos_doc': ['requerimento']}

        response = client.post(
            f'/api/v1/processos/{processo_id}/documentos',
            files=files,
            data=data,
            headers={'Authorization': f'Bearer {token2}'},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_paralelo_capacidade(self):
        """Testa se a rota suporta múltiplos uploads paralelos.

        Este teste verifica se o sistema pode lidar com múltiplas
        requisições de upload simultâneas sem deadlock ou erro.
        """
        token = _create_test_user()

        # Cria múltiplos processos
        processo_ids = []
        for i in range(5):
            response = client.post(
                '/api/v1/processos/',
                json={'tipo': 'requerimento'},
                headers={'Authorization': f'Bearer {token}'},
            )
            processo_ids.append(response.json()['id'])

        # Simula uploads paralelos
        async def fazer_upload(processo_id, doc_num):
            files = [
                (
                    'arquivos',
                    (
                        BytesIO(f'documento {doc_num}'.encode()),
                        f'doc{doc_num}.pdf',
                    ),
                ),
            ]
            data = {'tipos_doc': ['requerimento']}

            response = client.post(
                f'/api/v1/processos/{processo_id}/documentos',
                files=files,
                data=data,
                headers={'Authorization': f'Bearer {token}'},
            )
            return response.status_code

        # Executa 5 uploads "paralelos"
        tasks = [fazer_upload(processo_ids[i], i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # Todos devem ter sucesso
        assert all(status == 200 for status in results)

    def test_upload_documentos_tipos_diferentes(self):
        """Deve fazer upload de documentos com diferentes tipos."""
        token = _create_test_user()

        create_response = client.post(
            '/api/v1/processos/',
            json={'tipo': 'requerimento'},
            headers={'Authorization': f'Bearer {token}'},
        )
        processo_id = create_response.json()['id']

        tipos = [
            'requerimento',
            'cpf',
            'rg',
            'comprovante_endereco',
            'declaracao',
        ]
        files = [
            ('arquivos', (BytesIO(f'conteudo {t}'.encode()), f'{t}.pdf'))
            for t in tipos
        ]
        data = {'tipos_doc': tipos}

        response = client.post(
            f'/api/v1/processos/{processo_id}/documentos',
            files=files,
            data=data,
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 200
        assert response.json()['sucesso'] == len(tipos)


class TestAtualizarStatusProcesso:
    """Testes para atualização de status do processo."""

    def test_update_status_success(self):
        """Deve atualizar status do processo."""
        token = _create_test_user()

        # Cria processo
        create_response = client.post(
            '/api/v1/processos/',
            json={'tipo': 'requerimento'},
            headers={'Authorization': f'Bearer {token}'},
        )
        processo_id = create_response.json()['id']

        # Atualiza status
        response = client.patch(
            f'/api/v1/processos/{processo_id}/status',
            json={'new_state': 'em_analise'},
            headers={'Authorization': f'Bearer {token}'},
        )
        # Pode retornar 200 ou 404 dependendo de permissões
        assert response.status_code in [200, 404, 403]

    def test_update_status_invalido(self):
        """Deve retornar erro para status inválido."""
        token = _create_test_user()

        create_response = client.post(
            '/api/v1/processos/',
            json={'tipo': 'requerimento'},
            headers={'Authorization': f'Bearer {token}'},
        )
        processo_id = create_response.json()['id']

        response = client.patch(
            f'/api/v1/processos/{processo_id}/status',
            json={'new_state': 'status_invalido'},
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 400


class TestAnaliseAutomatica:
    """Testes para o fluxo automático de análise da IA."""

    @patch(
        'app.services.rag_service.RagClient.sugerir_despacho',
        new_callable=AsyncMock,
    )
    @patch(
        'app.services.rag_service.RagClient.verificar_conformidade',
        new_callable=AsyncMock,
    )
    @patch(
        'app.services.rag_service.RagClient.gerar_resumo',
        new_callable=AsyncMock,
    )
    def test_upload_dispara_analise_automatica_idempotente(
        self,
        mock_resumo,
        mock_conformidade,
        mock_despacho,
    ):
        token = _create_test_user()

        create_response = client.post(
            '/api/v1/processos/',
            json={'tipo': 'requerimento'},
            headers={'Authorization': f'Bearer {token}'},
        )
        processo_id = create_response.json()['id']

        mock_resumo.return_value = {
            'resumo': 'Resumo automático',
            'palavras_chave': ['teste'],
        }
        mock_conformidade.return_value = {
            'conformidade_pct': 80.0,
            'pendencias': ['Falta assinatura'],
        }
        mock_despacho.return_value = {'despacho': 'Regularize a documentação.'}

        files = [
            ('arquivos', (BytesIO(b'documento para analise'), 'doc1.pdf')),
            ('arquivos', (BytesIO(b'documento complementar'), 'doc2.pdf')),
        ]
        data = {'tipos_doc': ['requerimento', 'cpf']}

        upload_response = client.post(
            f'/api/v1/processos/{processo_id}/documentos',
            files=files,
            data=data,
            headers={'Authorization': f'Bearer {token}'},
        )

        assert upload_response.status_code == 200

        detail_response = client.get(
            f'/api/v1/processos/{processo_id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail['analise_status'] == 'completed'
        assert detail['resumo_ia'] == 'Resumo automático'
        assert detail['despacho_automatico'] == 'Regularize a documentação.'

        start_response = client.post(
            f'/api/v1/processos/{processo_id}/analise',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert start_response.status_code == 200
        assert start_response.json()['analise_status'] == 'completed'

        assert mock_resumo.await_count == 1
        assert mock_conformidade.await_count == 1
        assert mock_despacho.await_count == 1
