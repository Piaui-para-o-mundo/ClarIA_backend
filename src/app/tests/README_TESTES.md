# Testes do Sistema ClarIA Backend

## 📋 Visão Geral

Este diretório contém a suíte de testes completa para o backend do ClarIA. Os testes cobrem todas as rotas da API, incluindo autenticação, gerenciamento de processos, análise via RAG e upload de documentos com suporte a paralelismo.

## 📁 Estrutura de Testes

### test_auth.py
Testes para o módulo de autenticação:
- ✅ Registro de usuários
- ✅ Validação de emails únicos
- ✅ Login com credenciais
- ✅ Recuperação de dados do usuário
- ✅ Validação de tokens JWT

### test_processos.py
Testes para gerenciamento de processos:
- ✅ Criação de processos
- ✅ Listagem geral de processos
- ✅ Listagem de processos do usuário
- ✅ Recuperação de processo específico
- ✅ Upload de um ou múltiplos documentos
- ✅ Validação de autorizações
- ✅ Atualização de status

### test_analise.py
Testes para análise de documentos via RAG:
- ✅ Geração de resumos
- ✅ Verificação de conformidade
- ✅ Geração de despacho
- ✅ Validação de autenticação
- ✅ Fluxo completo de análise

### test_upload_performance.py
Testes de performance e paralelismo:
- ✅ Upload de 5 documentos simultâneos
- ✅ Upload de 10 documentos
- ✅ Upload paralelo em múltiplos processos
- ✅ Detalhes de sucesso/falha por documento
- ✅ Tratamento de arquivos grandes (5MB)
- ✅ Rejeição de arquivos acima do limite (50MB)
- ✅ Concorrência de uploads sequenciais

## 🚀 Como Executar

### Instalação de Dependências

```bash
# Instalar dependências de teste
pip install -r requirements.txt
```

### Executar Todos os Testes

```bash
# Com saída verbosa
pytest src/app/tests/ -v

# Com cobertura de código
pytest src/app/tests/ --cov=app --cov-report=html

# Com saída detalhada e parar no primeiro erro
pytest src/app/tests/ -vv -x
```

### Executar Testes Específicos

```bash
# Apenas testes de autenticação
pytest src/app/tests/test_auth.py -v

# Apenas testes de processos
pytest src/app/tests/test_processos.py -v

# Apenas testes de análise
pytest src/app/tests/test_analise.py -v

# Apenas testes de performance
pytest src/app/tests/test_upload_performance.py -v
```

### Executar um Teste Específico

```bash
# Teste específico de upload
pytest src/app/tests/test_processos.py::TestUploadDocumentos::test_upload_multiplos_documentos -v

# Teste de paralelismo
pytest src/app/tests/test_upload_performance.py::TestUploadParalelismo::test_upload_10_documentos -v
```

## 📊 Cobertura de Testes

Rotas cobertas:

| Rota | Método | Testes |
|------|--------|--------|
| `/api/v1/auth/register` | POST | ✅ 3 |
| `/api/v1/auth/login` | POST | ✅ 3 |
| `/api/v1/auth/me` | GET | ✅ 3 |
| `/api/v1/processos` | GET | ✅ 3 |
| `/api/v1/processos` | POST | ✅ 3 |
| `/api/v1/processos/my` | GET | ✅ 1 |
| `/api/v1/processos/{id}` | GET | ✅ 2 |
| `/api/v1/processos/{id}/documentos` | POST | ✅ 12 |
| `/api/v1/processos/{id}/status` | PATCH | ✅ 2 |
| `/api/v1/analise/{id}/resumo` | GET | ✅ 3 |
| `/api/v1/analise/{id}/conformidade` | GET | ✅ 3 |
| `/api/v1/analise/{id}/despacho` | GET | ✅ 2 |

**Total: 45+ testes**

## 🔄 Upload com Paralelismo

### O que mudou?

A rota de upload foi refatorada para suportar verdadeiro processamento paralelo:

**Antes:**
```python
# Processamento sequencial
for arquivo, tipo in zip(arquivos, tipos):
    await processar(arquivo, tipo)
```

**Depois:**
```python
# Processamento paralelo
tasks = [processar(arquivo, tipo) for arquivo, tipo in zip(...)]
resultados = await asyncio.gather(*tasks)
```

### Capacidades

1. **Múltiplos Documentos**: Aceita lista de arquivos via `UploadFile[]`
2. **Processamento Paralelo**: Usa `asyncio.gather()` para processar simultaneamente
3. **Informações Detalhadas**: Retorna sucesso/erro para cada documento
4. **Validação de Tamanho**: Máximo 50MB por arquivo
5. **Liberação de Recursos**: Fecha arquivos após processar
6. **Background Processing**: Conformidade verificada sem bloquear resposta

### Exemplos de Resposta

#### Sucesso
```json
{
  "sucesso": 3,
  "falhas": 0,
  "detalhes": [
    {
      "indice": 0,
      "tipo": "cpf",
      "nome": "cpf.pdf",
      "sucesso": true,
      "erro": null
    },
    {
      "indice": 1,
      "tipo": "rg",
      "nome": "rg.pdf",
      "sucesso": true,
      "erro": null
    },
    {
      "indice": 2,
      "tipo": "comprovante",
      "nome": "comprovante.pdf",
      "sucesso": true,
      "erro": null
    }
  ]
}
```

#### Com Falhas
```json
{
  "sucesso": 2,
  "falhas": 1,
  "detalhes": [
    {
      "indice": 0,
      "tipo": "cpf",
      "nome": "cpf.pdf",
      "sucesso": true,
      "erro": null
    },
    {
      "indice": 1,
      "tipo": "rg",
      "nome": "rg.pdf",
      "sucesso": false,
      "erro": "Arquivo muito grande (máximo 50MB)"
    }
  ]
}
```

## 🧪 Testes de Performance

Os testes verificam que:
- ✅ 5 documentos processam em <10 segundos
- ✅ 10 documentos processam sem erro
- ✅ Arquivo de 5MB processa em <30 segundos
- ✅ Arquivo >50MB é rejeitado
- ✅ Múltiplos uploads sequenciais não bloqueiam

## 📝 Notas Importantes

1. **TestClient vs Servidor Real**: Os testes usam `TestClient` do FastAPI. Para testes de carga real, considere usar ferramentas como `locust` ou `ab`.

2. **Mock do RAG**: Os testes de análise usam `@patch` para mockar o cliente RAG, já que não há servidor RAG em desenvolvimento.

3. **Banco de Dados**: Os testes desabilitam a inicialização real do BD com `_noop()` para evitar dependências de configuração.

4. **Async/Await**: Os testes usam `asyncio` para simular operações paralelas (limitado por `TestClient` não suportar paralelismo real).

## 🐛 Troubleshooting

### Erro: "No module named 'app'"
```bash
# Adicione o diretório src ao PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/path/to/src"
pytest src/app/tests/
```

### Erro de Autenticação em Testes
Certifique-se de que as funções de teste que usam `token` chamam `_create_test_user()` primeiro para registrar e fazer login.

### Erro de Timeout em Testes de Upload
Se os testes de upload de arquivos grandes falharem com timeout, aumente o timeout do pytest:
```bash
pytest src/app/tests/test_upload_performance.py -v --timeout=60
```

## 📚 Referências

- [Documentação FastAPI Testing](https://fastapi.tiangolo.com/advanced/testing-dependencies/)
- [Pytest Documentation](https://docs.pytest.org/)
- [AsyncIO Best Practices](https://docs.python.org/3/library/asyncio.html)

## ✅ Checklist de Qualidade

- [x] Todos os testes passam
- [x] Cobertura >80% do código de rotas
- [x] Testes de edge cases
- [x] Testes de autenticação e autorização
- [x] Testes de paralelismo
- [x] Testes de performance
- [x] Documentação completa

---

**Última atualização**: 19 de maio de 2026
