 # ClarIA Backend

Backend da aplicação ClarIA — API em `FastAPI` com PostgreSQL (via Docker Compose).

Resumo do que estamos trabalhando
- Testes automatizados para todas as rotas principais (autenticação, processos, análise e upload).
- Rota de upload de documentos refatorada para aceitar `UploadFile` e processar múltiplos arquivos em paralelo com `asyncio.gather()`.
- Integração rápida para testes manuais: um frontend estático simples (`clarIA_frontend/index.html`) usando HTMX.

Problema / "dor" do projeto
- Entrada de arquivos e processamento paralelo: precisamos garantir upload confiável, validação de tipos e limites de tamanho enquanto processamos múltiplos arquivos concorrentemente.
- Integração frontend ↔ backend: formularios HTML enviam `application/x-www-form-urlencoded` por padrão; as rotas precisavam aceitar tanto JSON quanto form-encoded para facilitar testes manuais via HTMX.
- Testabilidade: a aplicação usa SQLAlchemy async e dependências assíncronas — escrever testes que isolam DB e clientes externos (RAG) requer mocks e fixtures específicos.

Por que estas tecnologias (rationale)
- FastAPI: alta produtividade, tipagem, documentação automática (`/docs`) e bom suporte async — ideal para endpoints IO-bound (uploads, DB, clientes externos).
- SQLAlchemy (async) + PostgreSQL: modelo relacional robusto e escalável; SQLAlchemy dá controle do ORM e compatibilidade com Alembic para migrações.
- Alembic: versionamento de schema (migrations) para mudanças seguras no banco.
- Docker + Docker Compose: ambiente reprodutível (DB + API) — facilita CI e desenvolvimento local com a mesma configuração.
- HTMX (no frontend de teste): permite montar um frontend leve para validar endpoints rapidamente sem uma SPA completa.

Arquitetura e separação de responsabilidades
- `app/api/routes`: define rotas e validações de entrada. Rota de upload delega lógica a `services`.
- `app/services`: regras de negócio (salvar documentos, orquestrar análise/RAG, enfileiramento de verificações).
- `app/models` + `app/schemas`: modelos ORM e Pydantic para validação/serialização.
- `app/core`: configuração, conexão com DB, segurança, dependências compartilhadas.
- `app/utils`/`scripts`: ferramentas de apoio (seeders, utilitários).

Como rodar localmente (desenvolvimento)
1. Copie `.env` se necessário e ajuste variáveis (veja `env.example`).

2. Build e sobe containers (API + Postgres):
```bash
docker-compose up --build
```

3. Endpoints úteis
- API: http://localhost:8000
- Swagger/OpenAPI: http://localhost:8000/docs

4. Rodar apenas testes (local, sem containers)
- Instale dependências no seu ambiente Python (use virtualenv/venv):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov
```
- Alguns testes requerem que o pacote `src` esteja no `PYTHONPATH`:
```bash
export PYTHONPATH=.
pytest -q src/app/tests/
```

5. Rodar o backend localmente sem Docker (opcional):
```bash
export PYTHONPATH=.
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Dicas rápidas/Debug
- CORS: se usar o frontend estático em outra porta (ex: 8001), adicione a origem em `src/main.py` (desenvolvimento) — já incluímos `http://localhost:8001` por conveniência.
- Form vs JSON: as rotas de `auth` aceitam agora JSON ou dados de formulário; para testes via HTMX (forms) prefira enviar `role` com valores válidos: `professor` ou `avaliador`.

Testes e qualidade
- Há testes unitários/funcionais em `src/app/tests/`. Começamos a adicionar testes para `auth`, `processos`, `analise` e upload/performance.
- Recomendo rodar os testes localmente antes de abrir PRs; os testes usam mocks para clientes externos (RAG) e fixtures para isolar DB quando apropriado.

Próximos passos planejados
- Completar cobertura dos endpoints restantes e refinar mocks (RAG client) para reduzir flakiness.
- Melhorar a página de testes HTMX (UI) para mapear tipos de documento automaticamente aos arquivos selecionados.
- Adicionar CI (GitHub Actions) que execute lint + pytest em PRs.

Arquivos importantes
- [src/main.py](src/main.py#L1-L120)
- [src/app/api/routes/auth.py](src/app/api/routes/auth.py#L1-L240)
- [src/app/api/routes/processos.py](src/app/api/routes/processos.py#L1-L240)
- [src/app/tests](src/app/tests/README_TESTES.md#L1-L10)

Se quiser, eu ajeito o `README` com comandos específicos para macOS/Linux ou adiciono exemplos de requests curl e um checklist para rodar os testes no CI.

Execução rápida (frontend estático + backend)
-------------------------------------------
Se quiser servir o frontend estático na porta 3000 e o backend na 8000 simultaneamente durante desenvolvimento:

1. Servir frontend estático (diretório do projeto):

```bash
python -m http.server 3000
```

2. Rodar backend FastAPI com `uvicorn`:

```bash
export PYTHONPATH=.
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Com isso:
- Frontend: http://localhost:3000/
- Backend / Docs: http://localhost:8000/docs


