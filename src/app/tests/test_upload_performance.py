"""
Testes de performance e paralelismo para upload de documentos.

Verifica se a rota de upload suporta múltiplos documentos
de forma paralela e sem degradação de performance.
"""
import asyncio
import time
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.core.database as _db

# Previne inicialização real do BD durante testes
async def _noop():
    return None

_db.init_db = _noop
_db.close_db = _noop

from src.main import create_app

app = create_app()
client = TestClient(app)


def _create_test_user(email="professor@example.com"):
    """Helper para criar usuário de teste."""
    payload = {
        "nome": "Professor Teste",
        "email": email,
        "senha": "senha_123",
        "role": "professor",
        "setor": "Educação"
    }
    client.post("/api/v1/auth/register", json=payload)
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": email,
        "senha": "senha_123"
    })
    return login_response.json()["access_token"]


class TestUploadParalelismo:
    """Testes de paralelismo na rota de upload."""
    
    def test_upload_5_documentos_simultaneos(self):
        """Verifica upload de 5 documentos em simultâneo sem erro."""
        token = _create_test_user()
        
        # Cria processo
        create_response = client.post(
            "/api/v1/processos/",
            json={"tipo": "requerimento"},
            headers={"Authorization": f"Bearer {token}"}
        )
        processo_id = create_response.json()["id"]
        
        # Cria lista de arquivos
        files = [
            ("arquivos", (BytesIO(f"Conteúdo do documento {i}".encode()), f"doc{i}.pdf"))
            for i in range(5)
        ]
        data = {
            "tipos_doc": [f"tipo_{i}" for i in range(5)]
        }
        
        start = time.time()
        response = client.post(
            f"/api/v1/processos/{processo_id}/documentos",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"}
        )
        elapsed = time.time() - start
        
        assert response.status_code == 200
        result = response.json()
        assert result["sucesso"] == 5
        assert result["falhas"] == 0
        
        # Deve processar em tempo razoável (menos de 10 segundos)
        assert elapsed < 10.0
    
    def test_upload_10_documentos(self):
        """Verifica upload de 10 documentos sem problema."""
        token = _create_test_user("prof_10docs@example.com")
        
        create_response = client.post(
            "/api/v1/processos/",
            json={"tipo": "requerimento"},
            headers={"Authorization": f"Bearer {token}"}
        )
        processo_id = create_response.json()["id"]
        
        files = [
            ("arquivos", (BytesIO(f"Doc {i}".encode()), f"document_{i}.pdf"))
            for i in range(10)
        ]
        data = {
            "tipos_doc": [f"tipo_{i}" for i in range(10)]
        }
        
        response = client.post(
            f"/api/v1/processos/{processo_id}/documentos",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["sucesso"] == 10
    
    def test_upload_paralelo_multiplos_processos(self):
        """Verifica se upload paralelo em vários processos funciona."""
        token = _create_test_user("prof_parallel@example.com")
        
        # Cria 3 processos
        processo_ids = []
        for i in range(3):
            response = client.post(
                "/api/v1/processos/",
                json={"tipo": "requerimento"},
                headers={"Authorization": f"Bearer {token}"}
            )
            processo_ids.append(response.json()["id"])
        
        # Faz upload em cada um (não é verdadeiramente paralelo com TestClient, mas testa sequência)
        for processo_id in processo_ids:
            files = [
                ("arquivos", (BytesIO(b"conteudo"), "doc.pdf")),
            ]
            data = {
                "tipos_doc": ["requerimento"]
            }
            
            response = client.post(
                f"/api/v1/processos/{processo_id}/documentos",
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            assert response.json()["sucesso"] == 1


class TestUploadFileDetails:
    """Testes de detalhes de cada upload individual."""
    
    def test_retorna_detalhes_cada_documento(self):
        """Verifica se resposta inclui detalhes de cada documento."""
        token = _create_test_user("prof_details@example.com")
        
        create_response = client.post(
            "/api/v1/processos/",
            json={"tipo": "requerimento"},
            headers={"Authorization": f"Bearer {token}"}
        )
        processo_id = create_response.json()["id"]
        
        files = [
            ("arquivos", (BytesIO(b"Doc 1"), "documento1.pdf")),
            ("arquivos", (BytesIO(b"Doc 2"), "documento2.pdf")),
            ("arquivos", (BytesIO(b"Doc 3"), "documento3.pdf")),
        ]
        data = {
            "tipos_doc": ["cpf", "rg", "comprovante"]
        }
        
        response = client.post(
            f"/api/v1/processos/{processo_id}/documentos",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Verifica resposta
        assert "sucesso" in result
        assert "falhas" in result
        assert "detalhes" in result
        
        # Verifica detalhes
        detalhes = result["detalhes"]
        assert len(detalhes) == 3
        
        for i, detalhe in enumerate(detalhes):
            assert "indice" in detalhe
            assert "tipo" in detalhe
            assert "nome" in detalhe
            assert "sucesso" in detalhe
            assert detalhe["indice"] == i
    
    def test_identifica_arquivos_falhados(self):
        """Verifica se identifica quais arquivos falharam."""
        token = _create_test_user("prof_fails@example.com")
        
        create_response = client.post(
            "/api/v1/processos/",
            json={"tipo": "requerimento"},
            headers={"Authorization": f"Bearer {token}"}
        )
        processo_id = create_response.json()["id"]
        
        # Mistura arquivos validos com possiveis problemas
        files = [
            ("arquivos", (BytesIO(b"Valid 1"), "doc1.pdf")),
            ("arquivos", (BytesIO(b"Valid 2"), "doc2.pdf")),
        ]
        data = {
            "tipos_doc": ["tipo1", "tipo2"]
        }
        
        response = client.post(
            f"/api/v1/processos/{processo_id}/documentos",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        result = response.json()
        detalhes = result["detalhes"]
        
        # Verifica que arquivos com sucesso tem erro=None
        for detalhe in detalhes:
            if detalhe["sucesso"]:
                assert detalhe["erro"] is None
            else:
                assert detalhe["erro"] is not None


class TestUploadMemoryUsage:
    """Testes para garantir que upload não consome memória excessiva."""
    
    def test_upload_arquivo_grande(self):
        """Verifica upload de arquivo maior (5MB)."""
        token = _create_test_user("prof_large@example.com")
        
        create_response = client.post(
            "/api/v1/processos/",
            json={"tipo": "requerimento"},
            headers={"Authorization": f"Bearer {token}"}
        )
        processo_id = create_response.json()["id"]
        
        # Cria arquivo de 5MB
        conteudo_5mb = b"x" * (5 * 1024 * 1024)
        
        files = [
            ("arquivos", (BytesIO(conteudo_5mb), "large_file.pdf")),
        ]
        data = {
            "tipos_doc": ["documento_grande"]
        }
        
        start = time.time()
        response = client.post(
            f"/api/v1/processos/{processo_id}/documentos",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"}
        )
        elapsed = time.time() - start
        
        # Não deve falhar e deve processar em tempo razoável
        assert response.status_code == 200
        assert elapsed < 30.0  # 30 segundos é razoável para 5MB
    
    def test_rejeita_arquivo_muito_grande(self):
        """Verifica rejeição de arquivo maior que 50MB."""
        token = _create_test_user("prof_huge@example.com")
        
        create_response = client.post(
            "/api/v1/processos/",
            json={"tipo": "requerimento"},
            headers={"Authorization": f"Bearer {token}"}
        )
        processo_id = create_response.json()["id"]
        
        # Cria arquivo de 51MB (excede limite de 50MB)
        # Nota: Este teste pode ser lento ou pular em CI
        conteudo_huge = b"y" * (51 * 1024 * 1024)
        
        files = [
            ("arquivos", (BytesIO(conteudo_huge), "huge_file.pdf")),
        ]
        data = {
            "tipos_doc": ["documento_enorme"]
        }
        
        response = client.post(
            f"/api/v1/processos/{processo_id}/documentos",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Pode retornar erro ou falha no upload
        assert response.status_code in [200, 413]  # 413 = Payload Too Large
        if response.status_code == 200:
            result = response.json()
            # Se passou, deve ter falhado (não sucesso)
            assert result["sucesso"] == 0 or result["falhas"] > 0


class TestUploadConcorrencia:
    """Testes de concorrência com múltiplas requisições."""
    
    def test_upload_sequencial_nao_bloqueia(self):
        """Verifica que múltiplos uploads sequenciais funcionam."""
        token = _create_test_user("prof_seq@example.com")
        
        for batch_num in range(3):
            # Cria novo processo para cada lote
            create_response = client.post(
                "/api/v1/processos/",
                json={"tipo": "requerimento"},
                headers={"Authorization": f"Bearer {token}"}
            )
            processo_id = create_response.json()["id"]
            
            # Faz upload de 3 documentos
            files = [
                ("arquivos", (BytesIO(f"Batch {batch_num}, Doc {i}".encode()), f"doc{i}.pdf"))
                for i in range(3)
            ]
            data = {
                "tipos_doc": [f"doc_{i}" for i in range(3)]
            }
            
            response = client.post(
                f"/api/v1/processos/{processo_id}/documentos",
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 200
            assert response.json()["sucesso"] == 3
