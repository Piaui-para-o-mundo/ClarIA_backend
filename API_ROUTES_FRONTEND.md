# Documentação de Rotas da API ClarIA (Backend)

Este documento foi gerado para auxiliar os agentes e desenvolvedores de frontend na integração com o backend FastAPI da aplicação ClarIA.

Aqui estão listadas todas as rotas ativas, juntamente com os payloads, parâmetros aceitos e as respostas esperadas.

---

## 🔐 1. Rotas de Autenticação (`/api/v1/auth`)

Todas as rotas de autenticação lidam com o registro e login dos usuários (Professores e Avaliadores).

### 1.1 Registrar Usuário
- **Rota:** `POST /api/v1/auth/register`
- **Autenticação:** Não necessária.
- **Payload (JSON ou Form-Data):**
  ```json
  {
    "nome": "João Silva",             // string (3 a 150 caracteres)
    "email": "joao@exemplo.com",      // email válido
    "senha": "senha_super_segura",    // string (mín. 8 caracteres)
    "role": "professor",              // string ("professor" ou "avaliador")
    "setor": "DCC"                    // opcional, string (máx 100 caracteres)
  }
  ```
- **Retorno de Sucesso:** Detalhes do usuário cadastrado (sem a senha).

### 1.2 Login
- **Rota:** `POST /api/v1/auth/login`
- **Autenticação:** Não necessária.
- **Payload (JSON):**
  ```json
  {
    "email": "joao@exemplo.com",      // email válido
    "senha": "senha_super_segura"     // string
  }
  ```
- **Retorno de Sucesso:**
  ```json
  {
    "access_token": "eyJhbG...",
    "token_type": "bearer"
  }
  ```
- **Nota:** Guarde o `access_token`. Ele deve ser enviado no cabeçalho das requisições privadas no formato `Authorization: Bearer <seu_token>`.

### 1.3 Perfil do Usuário Logado
- **Rota:** `GET /api/v1/auth/me`
- **Autenticação:** Bearer Token.
- **Payload:** Nenhum.
- **Retorno de Sucesso:** Dados completos do usuário autenticado (`id`, `nome`, `email`, `role`, `setor`, `ativo`).

---

## 📄 2. Rotas de Processos (`/api/v1/processos`)

Rotas para gestão de processos e upload de documentos.

### 2.1 Criar Novo Processo (Apenas Professores)
- **Rota:** `POST /api/v1/processos/`
- **Autenticação:** Bearer Token.
- **Payload (JSON):**
  ```json
  {
    "tipo": "progressao_funcional" // Valores aceitos: "progressao_funcional", "promocao", "afastamento_mestrado", "licenca_premio", "outros"
  }
  ```
- **Retorno de Sucesso:** Objeto completo do Processo criado.

### 2.2 Listar Todos os Processos (Avaliadores)
- **Rota:** `GET /api/v1/processos/`
- **Autenticação:** Bearer Token.
- **Parâmetros de Query (Opcionais):** 
  - `skip` (int): default `0`
  - `limit` (int): default `50`
- **Exemplo:** `GET /api/v1/processos/?skip=0&limit=10`
- **Retorno de Sucesso:** Lista com o resumo dos processos.

### 2.3 Listar Meus Processos (Professores)
- **Rota:** `GET /api/v1/processos/my`
- **Autenticação:** Bearer Token.
- **Parâmetros de Query (Opcionais):** 
  - `skip` (int): default `0`
  - `limit` (int): default `50`
- **Retorno de Sucesso:** Lista com o resumo dos processos que pertencem ao usuário logado.

### 2.4 Detalhes de um Processo
- **Rota:** `GET /api/v1/processos/{processo_id}`
- **Autenticação:** Bearer Token.
- **Parâmetros de Rota:** `processo_id` (UUID)
- **Retorno de Sucesso:** Objeto completo do Processo, incluindo os Documentos associados.

### 2.5 Fazer Upload de Documentos
- **Rota:** `POST /api/v1/processos/{processo_id}/documentos`
- **Autenticação:** Bearer Token.
- **Parâmetros de Rota:** `processo_id` (UUID)
- **Payload (`multipart/form-data`):**
  - O envio requer múltiplos arquivos sendo atrelados simultaneamente.
  - Campos a serem enviados no Form Data:
    - `arquivos` (List[File]): Múltiplos arquivos PDF. (Máx. 50MB por arquivo)
    - `tipos_doc` (List[String]): Ex: "requerimento", "cpf". O tamanho desta lista deve ser igual ao número de arquivos enviados, representando seus respectivos tipos.
- **Retorno de Sucesso:**
  ```json
  {
    "sucesso": 2,
    "falhas": 0,
    "detalhes": [
      {
        "indice": 0,
        "tipo": "requerimento",
        "nome": "arquivo1.pdf",
        "sucesso": true,
        "erro": null
      }
    ]
  }
  ```

### 2.6 Atualizar Status do Processo (Avaliadores)
- **Rota:** `PATCH /api/v1/processos/{processo_id}/status`
- **Autenticação:** Bearer Token.
- **Parâmetros de Rota:** `processo_id` (UUID)
- **Parâmetros de Query:** 
  - `new_state` (string): O novo status (Ex: `em_analise`, `aprovado`, `reprovado`, etc.)
- **Exemplo:** `PATCH /api/v1/processos/{processo_id}/status?new_state=aprovado`
- **Retorno de Sucesso:** Objeto completo do Processo atualizado.

---

## 🤖 3. Rotas de Análise com RAG (Inteligência Artificial) (`/api/v1/analise`)

Estas rotas acionam o motor de RAG para análises, resumos e sugestão de despachos.

### 3.1 Gerar Resumo do Processo
- **Rota:** `GET /api/v1/analise/{processo_id}/resumo`
- **Autenticação:** Bearer Token.
- **Parâmetros de Rota:** `processo_id` (UUID)
- **Retorno de Sucesso:**
  ```json
  {
    "resumo": "Resumo do documento gerado pela IA...",
    "palavra_chave": ["promoção", "docente", "documentos"]
  }
  ```

### 3.2 Verificar Conformidade
- **Rota:** `GET /api/v1/analise/{processo_id}/conformidade`
- **Autenticação:** Bearer Token.
- **Parâmetros de Rota:** `processo_id` (UUID)
- **Retorno de Sucesso:**
  ```json
  {
    "conformidade_pct": 85.5,
    "pendencias": ["Falta documento RG", "Assinatura ilegível no requerimento"]
  }
  ```

### 3.3 Sugerir Despacho
- **Rota:** `GET /api/v1/analise/{processo_id}/despacho`
- **Autenticação:** Bearer Token.
- **Parâmetros de Rota:** `processo_id` (UUID)
- **Retorno de Sucesso:**
  ```json
  {
    "despacho": "Sugere-se o deferimento com base na documentação x...",
    "motivo": "Análise das normas XPTO."
  }
  ```

### 3.4 Aprovar / Editar Despacho e Concluir
- **Rota:** `POST /api/v1/analise/{processo_id}/aprovar-despacho`
- **Autenticação:** Bearer Token.
- **Parâmetros de Rota:** `processo_id` (UUID)
- **Parâmetros de Query:**
  - `despacho_editado` (string): O texto final do despacho aprovado/editado pelo avaliador.
- **Exemplo:** `POST /api/v1/analise/{processo_id}/aprovar-despacho?despacho_editado=Aprovado+conforme+regras`
- **Retorno de Sucesso:**
  ```json
  {
    "status": "concluido"
  }
  ```

---

## 💡 Observações para o Frontend

1. **Autenticação e Headers:** Com exceção de `register` e `login`, todas as chamadas precisam do header: `Authorization: Bearer {token}`.
2. **Campos Multipart (Upload):** Na rota de upload, a estruturação tem que garantir a mesma ordem de inserção nos campos de _form-data_ para os arrays `arquivos` (arquivos nativos) e `tipos_doc` (textos associados a cada arquivo).
3. **Erros Padronizados:** Caso as requisições falhem, o FastAPI retonará um status code pertinente (400, 401, 403, 404, 422) acompanhado do campo `detail` no JSON informando o motivo da recusa.
