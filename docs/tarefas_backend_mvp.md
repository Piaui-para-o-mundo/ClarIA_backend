# 🔧 Subtarefas Backend — MVP ClarIA (Production)

> **Repositório:** `ClarIA_backend` (isolado)  
> **Stack:** Python 3.12 · FastAPI · PostgreSQL 16 · SQLAlchemy Async · Alembic · Docker  
> **Comunicação com RAG:** HTTP interno (o Backend chama a API do `ClarIA_RAG_IA`)  
> **Data:** 2026-05-12

---

## 📐 Arquitetura de Comunicação (3 Serviços Isolados)

```
┌──────────────┐     HTTP/JSON     ┌───────────────┐     HTTP/JSON     ┌──────────────┐
│   Frontend   │ ───────────────►  │    Backend    │ ───────────────►  │   RAG / IA   │
│ (React/Vite) │ ◄───────────────  │   (FastAPI)   │ ◄───────────────  │  (FastAPI)   │
│  :5173       │                   │   :8000       │                   │  :8001       │
└──────────────┘                   └───────┬───────┘                   └──────────────┘
                                           │
                                    ┌──────▼──────┐
                                    │ PostgreSQL  │
                                    │   :5432     │
                                    └─────────────┘
```

**Regra de ouro:** O Backend é o **único** que fala com o banco de dados. O Frontend nunca fala com o RAG diretamente. O Backend orquestra tudo.

---

## Estado Atual do Repositório

| Arquivo | Status | O que tem |
|---------|--------|-----------|
| `app/main.py` | 🟡 Scaffolding | Hello World — apenas 2 rotas de exemplo |
| `requirements.txt` | 🟡 Mínimo | `fastapi`, `uvicorn`, `psycopg2-binary` |
| `Dockerfile` | ✅ Funcional | Python 3.12 + uvicorn com --reload |
| `docker-compose.yaml` | ✅ Funcional | API + PostgreSQL 16 |
| `.gitignore` | ✅ | Configurado |

---

## Épico 1 — Fundação do Projeto

### 1.1 Dependências
- `[ ]` **Atualizar `requirements.txt`** com todas as dependências MVP:
  ```
  fastapi>=0.136.0
  uvicorn[standard]
  sqlalchemy[asyncio]>=2.0
  asyncpg
  alembic
  pydantic>=2.0
  pydantic-settings
  python-jose[cryptography]
  passlib[bcrypt]
  python-multipart
  httpx
  python-dotenv
  ```
  > `httpx` é essencial — é o client HTTP async que chamará a API do RAG

### 1.2 Estrutura de Pastas (Clean Architecture)
- `[ ]` **Criar estrutura de pastas:**
  ```
  app/
  ├── __init__.py
  ├── main.py               ← Entrypoint FastAPI
  ├── config.py             ← Settings (Pydantic BaseSettings)
  ├── core/
  │   ├── __init__.py
  │   ├── database.py       ← Engine SQLAlchemy Async
  │   ├── security.py       ← Hash de senha + JWT
  │   └── dependencies.py   ← Injeção de dependência (get_db, get_current_user)
  ├── models/
  │   ├── __init__.py
  │   ├── usuario.py
  │   ├── processo.py
  │   └── documento.py
  ├── schemas/
  │   ├── __init__.py
  │   ├── auth.py
  │   ├── processo.py
  │   └── documento.py
  ├── routers/
  │   ├── __init__.py
  │   ├── auth.py
  │   ├── processos.py
  │   └── analise.py
  ├── services/
  │   ├── __init__.py
  │   ├── rag_client.py     ← ★ Client HTTP para chamar ClarIA_RAG_IA
  │   └── processo_service.py
  └── utils/
      └── __init__.py
  ```

### 1.3 Configurações
- `[ ]` **Criar `app/config.py`** com Pydantic Settings:
  ```python
  class Settings(BaseSettings):
      DATABASE_URL: str
      SECRET_KEY: str
      ALGORITHM: str = "HS256"
      ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
      RAG_SERVICE_URL: str = "http://localhost:8001"  # ★ URL do serviço RAG
  ```
- `[ ]` **Criar `.env.example`** documentando todas as variáveis
- `[ ]` **Atualizar `docker-compose.yaml`** adicionando variáveis de ambiente:
  - `SECRET_KEY`
  - `RAG_SERVICE_URL` (apontar para o container/host do RAG)

### 1.4 Banco de Dados
- `[ ]` **Criar `core/database.py`** — Engine async com SQLAlchemy:
  - `create_async_engine(DATABASE_URL)`
  - `async_sessionmaker`
  - `get_db()` dependency
- `[ ]` **Inicializar Alembic:**
  ```bash
  alembic init alembic
  ```
  - Configurar `alembic.ini` com `DATABASE_URL`
  - Configurar `env.py` para modo async

---

## Épico 2 — Modelos de Dados (SQLAlchemy)

### 2.1 Modelo `Usuario`
- `[ ]` **Criar `models/usuario.py`:**
  - `id`: UUID, PK
  - `nome`: String, not null
  - `email`: String, unique, not null
  - `senha_hash`: String, not null
  - `role`: Enum (`professor`, `avaliador`), not null
  - `setor`: String, nullable
  - `ativo`: Boolean, default True
  - `criado_em`: DateTime, server_default
  - `atualizado_em`: DateTime, onupdate

### 2.2 Modelo `Processo`
- `[ ]` **Criar `models/processo.py`:**
  - `id`: UUID, PK
  - `numero`: String, unique (formato: `CPPD-001/2026`)
  - `usuario_id`: FK → Usuario
  - `tipo`: String (progressao_funcional, promocao, afastamento_mestrado, etc.)
  - `status`: Enum:
    - `aguardando_analise` — acabou de ser enviado
    - `pendente_professor` — checklist falhou, faltam docs
    - `analise_pendente` — docs OK, na fila do avaliador
    - `concluido` — avaliador finalizou
    - `arquivado`
  - `despacho_automatico`: Text, nullable (preenchido pelo Módulo 1 do RAG)
  - `despacho_avaliador`: Text, nullable (preenchido quando avaliador aprova)
  - `criado_em`: DateTime
  - `atualizado_em`: DateTime

### 2.3 Modelo `Documento`
- `[ ]` **Criar `models/documento.py`:**
  - `id`: UUID, PK
  - `processo_id`: FK → Processo
  - `nome_arquivo`: String
  - `tipo_doc`: String (requerimento, cpf, contracheque, diploma, etc.)
  - `caminho_arquivo`: String (path no disco)
  - `conteudo_extraido`: Text, nullable (texto extraído pelo RAG)
  - `criado_em`: DateTime

### 2.4 Migration Inicial
- `[ ]` **Gerar migration:**
  ```bash
  alembic revision --autogenerate -m "create_initial_tables"
  alembic upgrade head
  ```

---

## Épico 3 — Autenticação e RBAC

### 3.1 Segurança
- `[ ]` **Criar `core/security.py`:**
  - `hash_password(password)` → bcrypt
  - `verify_password(plain, hashed)` → bcrypt
  - `create_access_token(data, expires_delta)` → JWT
  - `decode_token(token)` → dict

### 3.2 Dependencies
- `[ ]` **Criar `core/dependencies.py`:**
  - `get_db()` — Gera async session
  - `get_current_user(token)` — Decodifica JWT, busca usuário no DB
  - `require_role(roles: list[str])` — Decorator que valida role

### 3.3 Rotas de Auth
- `[ ]` **Criar `routers/auth.py`:**
  - `POST /api/v1/auth/register` — Cadastro com validação de email único
  - `POST /api/v1/auth/login` — Retorna JWT
  - `GET /api/v1/auth/me` — Dados do usuário logado

### 3.4 Schemas de Auth
- `[ ]` **Criar `schemas/auth.py`:**
  ```python
  class UserCreate(BaseModel):
      nome: str
      email: EmailStr
      senha: str
      role: Literal["professor", "avaliador"]

  class UserResponse(BaseModel):
      id: UUID
      nome: str
      email: str
      role: str

  class TokenResponse(BaseModel):
      access_token: str
      token_type: str = "bearer"
  ```

---

## Épico 4 — Gestão de Processos

### 4.1 Schemas
- `[ ]` **Criar `schemas/processo.py`:**
  - `ProcessoCreate` — tipo
  - `ProcessoResponse` — todos os campos + lista de documentos
  - `ProcessoResumo` — versão resumida para listagem

### 4.2 Rotas de Processos
- `[ ]` **Criar `routers/processos.py`:**
  - `POST /api/v1/processos` — Cria processo novo (professor)
  - `GET /api/v1/processos` — Lista todos (avaliador)
  - `GET /api/v1/processos/meus` — Lista do professor logado
  - `GET /api/v1/processos/{id}` — Detalhes com documentos
  - `PATCH /api/v1/processos/{id}/status` — Atualiza status (avaliador)

### 4.3 Upload de Documentos
- `[ ]` **Criar rota de upload em `routers/processos.py`:**
  - `POST /api/v1/processos/{id}/documentos` — Upload de múltiplos PDFs
  - Cada arquivo vem com `tipo_doc` (FormData)
  - Salvar arquivo em `uploads/{processo_id}/{tipo_doc}.pdf`
  - Criar registro `Documento` no banco
  - **Após upload completo:** Disparar `BackgroundTask` para chamar o RAG

### 4.4 Service Layer
- `[ ]` **Criar `services/processo_service.py`:**
  - `criar_processo(db, user, data)` → Processo
  - `listar_processos(db, filtros)` → list[Processo]
  - `listar_meus_processos(db, user_id)` → list[Processo]
  - `get_processo(db, id)` → Processo com documentos
  - `atualizar_status(db, id, novo_status)` → Processo

---

## Épico 5 — ★ Client HTTP para o RAG (Integração entre serviços)

> **ESTE É O PONTO DE CONEXÃO.** O Backend chama o RAG via HTTP.

### 5.1 RAG Client
- `[ ]` **Criar `services/rag_client.py`:**
  ```python
  class RAGClient:
      """Cliente HTTP assíncrono para chamar o serviço ClarIA_RAG_IA."""
      
      def __init__(self, base_url: str):
          self.base_url = base_url  # ex: http://localhost:8001
          self.client = httpx.AsyncClient(timeout=120.0)
      
      async def health_check(self) -> bool:
          """GET /ia/health"""
          
      async def ingest_documento(self, pdf_content: bytes, filename: str) -> dict:
          """POST /ia/ingest — Envia PDF para indexação no ChromaDB"""
          
      async def gerar_resumo(self, texto_documento: str) -> dict:
          """POST /ia/resumo — Módulo 1: Resumo inteligente"""
          
      async def verificar_conformidade(
          self, texto_documento: str, tipo_processo: str
      ) -> dict:
          """POST /ia/conformidade — Módulo 2: Conformidade documental"""
          
      async def sugerir_despacho(
          self, texto_documento: str, pendencias: str
      ) -> dict:
          """POST /ia/despacho — Módulo 3: Sugestão de despacho"""
  ```

### 5.2 Injeção de Dependência
- `[ ]` **Criar dependency `get_rag_client()`:**
  ```python
  async def get_rag_client() -> RAGClient:
      return RAGClient(base_url=settings.RAG_SERVICE_URL)
  ```

### 5.3 Contrato com o RAG
- `[ ]` **Documentar contrato de API** entre Backend ↔ RAG:
  - Os endpoints do RAG já existem em `ClarIA_RAG_IA`:
    | Método | Rota RAG | Backend chama quando... |
    |--------|----------|------------------------|
    | GET | `/ia/health` | Health check |
    | POST | `/ia/ingest` | Upload de documento |
    | POST | `/ia/resumo` | Avaliador pede resumo |
    | POST | `/ia/conformidade` | Background task pós-upload |
    | POST | `/ia/despacho` | Avaliador gera despacho |

---

## Épico 6 — Rotas de Análise (Orquestração Backend → RAG)

### 6.1 Rotas
- `[ ]` **Criar `routers/analise.py`:**
  - `GET /api/v1/analise/{processo_id}/resumo`
    - Busca processo no DB
    - Chama `rag_client.gerar_resumo(texto_concatenado_dos_docs)`
    - Retorna JSON estruturado
  - `GET /api/v1/analise/{processo_id}/conformidade`
    - Chama `rag_client.verificar_conformidade(texto, tipo_processo)`
    - Retorna resultado com % de conformidade
  - `POST /api/v1/analise/{processo_id}/despacho`
    - Chama `rag_client.sugerir_despacho(texto, pendencias)`
    - Retorna minuta de despacho
  - `POST /api/v1/analise/{processo_id}/aprovar-despacho`
    - Avaliador aprova/edita o despacho
    - Salva em `processo.despacho_avaliador`
    - Muda status para `concluido`

### 6.2 Background Task (Checklist Automático)
- `[ ]` **Criar lógica de pós-upload:**
  - Quando professor faz upload de todos os docs:
    1. Backend chama `rag_client.verificar_conformidade()`
    2. Se `conformidade_pct < 100`:
       - Chamar `rag_client.sugerir_despacho()` com pendências
       - Salvar despacho de devolução em `processo.despacho_automatico`
       - Status → `pendente_professor`
    3. Se `conformidade_pct == 100`:
       - Status → `analise_pendente`

---

## Épico 7 — Dashboard e Métricas

- `[ ]` **Criar `routers/dashboard.py`:**
  - `GET /api/v1/dashboard/indicadores`
    - Contagem por status
    - Total de processos
    - Processos recentes
  > Para MVP, SQL simples com COUNT/GROUP BY é suficiente

---

## Épico 8 — Seeds e Dados de Teste

- `[ ]` **Criar `scripts/seed_usuarios.py`:**
  - Professor de teste: `professor@uespi.br` / `123456`
  - Avaliador de teste: `avaliador@uespi.br` / `123456`
- `[ ]` **Criar `scripts/seed_processos.py`:**
  - 2-3 processos demo com status variados para testar o frontend

---

## Épico 9 — Entrypoint e CORS

### 9.1 Main
- `[ ]` **Reescrever `app/main.py`:**
  - CORS configurado para aceitar frontend (`http://localhost:5173`)
  - Incluir todos os routers
  - Health check em `GET /health`
  - Evento `on_startup` para criar tabelas (dev) ou verificar conexão

### 9.2 Docker
- `[ ]` **Atualizar `docker-compose.yaml`:**
  - Adicionar variáveis `SECRET_KEY`, `RAG_SERVICE_URL`
  - Considerar adicionar rede Docker para comunicação entre serviços

---

## Épico 10 — Testes

- `[ ]` Teste de conexão com banco
- `[ ]` Teste de registro + login
- `[ ]` Teste de criação de processo
- `[ ]` Teste de upload de documento
- `[ ]` Teste E2E: upload → checklist via RAG → status muda

---

## ⚡ Ordem de Execução Sugerida

| Ordem | Épico | Dependências |
|-------|-------|-------------|
| 1️⃣ | Épico 1 — Fundação | Nenhuma |
| 2️⃣ | Épico 2 — Modelos | Épico 1 |
| 3️⃣ | Épico 3 — Auth | Épicos 1, 2 |
| 4️⃣ | Épico 4 — Processos | Épicos 1, 2, 3 |
| 5️⃣ | Épico 5 — RAG Client | Épico 1 (pode ser paralelo) |
| 6️⃣ | Épico 6 — Análise | Épicos 4, 5 |
| 7️⃣ | Épico 7 — Dashboard | Épico 4 |
| 8️⃣ | Épico 8 — Seeds | Épicos 2, 3 |
| 9️⃣ | Épico 9 — Entrypoint | Todos |
| 🔟 | Épico 10 — Testes | Todos |

---

## 🔗 Contratos de API que o Frontend vai consumir

| Método | Rota | Quem usa |
|--------|------|----------|
| POST | `/api/v1/auth/register` | Tela de Registro |
| POST | `/api/v1/auth/login` | Tela de Login |
| GET | `/api/v1/auth/me` | Layout (nome do usuário) |
| POST | `/api/v1/processos` | Wizard de submissão |
| GET | `/api/v1/processos` | Dashboard Avaliador |
| GET | `/api/v1/processos/meus` | Meus Processos (Professor) |
| GET | `/api/v1/processos/{id}` | Detalhes do Processo |
| POST | `/api/v1/processos/{id}/documentos` | Upload de PDFs |
| GET | `/api/v1/analise/{id}/resumo` | Card de Resumo (Avaliador) |
| GET | `/api/v1/analise/{id}/conformidade` | Badge de Conformidade |
| POST | `/api/v1/analise/{id}/despacho` | Gerar Despacho (Avaliador) |
| POST | `/api/v1/analise/{id}/aprovar-despacho` | Aprovar Despacho |
| GET | `/api/v1/dashboard/indicadores` | Dashboard Métricas |
