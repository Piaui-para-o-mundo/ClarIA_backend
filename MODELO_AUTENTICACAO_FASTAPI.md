# Modelo de Autenticação com FastAPI

Este arquivo serve como guia para criar uma base de autenticação com:

- tabela de usuários
- router de login
- controle de roles `admin` e `professor`
- proteção de rotas com dependências do FastAPI

## 1. Estrutura sugerida

Organize os arquivos assim:

```text
src/
  app/
    domain/
      entities/
        user.py
      services/
        access_policy.py
      value_objects/
        role.py
    core/
      config.py
      connection.py
      security.py
      dependencies.py
    models/
      user.py
    schemas/
      auth.py
      user.py
    services/
      auth_service.py
      user_service.py
    api/
      routes/
        auth.py
        users.py
        protected.py
```

## 1.1 Camada de domínio

A camada de domínio concentra as regras centrais do negócio, sem depender de FastAPI, SQLAlchemy ou detalhes de banco.

### O que entra aqui

- entidades do negócio, como `User`
- regras de autorização e validação de papel
- objetos de valor, como `Role`
- políticas de acesso, como "professor pode acessar X, admin pode acessar tudo"

### O que não entra aqui

- rotas HTTP
- modelos ORM
- schemas Pydantic
- queries de banco
- código de autenticação específico de framework

### Exemplo de responsabilidade

```python
class AccessPolicy:
    def can_manage_users(self, role: str) -> bool:
        return role == "admin"

    def can_access_teacher_area(self, role: str) -> bool:
        return role in {"admin", "professor"}
```

### Sugestão de organização interna

- `domain/entities/`: regras e atributos da entidade principal
- `domain/value_objects/`: valores imutáveis e validados
- `domain/services/`: regras puras que envolvem mais de uma entidade

## 2. Modelo de usuário

Crie um modelo ORM com os campos mínimos:

- `id`: chave primária
- `name`: nome do usuário
- `email`: único
- `hashed_password`: senha criptografada
- `role`: controla permissões
- `is_active`: usuário ativo ou inativo
- `created_at`: data de criação

### Exemplo de roles

- `admin`: pode gerenciar usuários, turmas, permissões e recursos sensíveis
- `professor`: pode acessar rotas pedagógicas e recursos limitados à sua função

### Sugestão de enum

```python
from enum import Enum


class UserRole(str, Enum):
    admin = "admin"
    professor = "professor"
```

## 3. Regras da tabela

Defina estas regras no banco e no model:

- `email` deve ser único
- `role` deve aceitar apenas valores válidos
- `hashed_password` nunca deve armazenar senha em texto puro
- `is_active` deve permitir bloquear acesso sem apagar o usuário

## 4. Schemas Pydantic

Separe entrada e saída.

### Schemas de usuário

- `UserCreate`: nome, email, senha, role opcional
- `UserRead`: id, nome, email, role, is_active, created_at
- `UserUpdate`: campos editáveis

### Schemas de autenticação

- `LoginRequest`: email e senha
- `TokenResponse`: access token e tipo do token

## 5. Segurança

Em `core/security.py`, crie funções para:

- gerar hash de senha
- validar senha
- criar e validar JWT

Regras importantes:

- nunca retornar `hashed_password` em responses
- use `OAuth2PasswordBearer` ou dependência equivalente
- trate senha inválida e usuário inexistente com erro 401

## 6. Serviço de autenticação

Em `services/auth_service.py`, centralize a lógica:

- buscar usuário por email
- validar senha
- gerar token JWT
- retornar dados do usuário logado

### Fluxo de login

1. receber `email` e `senha`
2. buscar usuário no banco
3. validar `is_active`
4. comparar senha digitada com `hashed_password`
5. gerar token com `sub`, `user_id` e `role`

## 7. Router de login

Em `api/routes/auth.py`, crie rotas como:

- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/logout` se necessário no seu fluxo

### Exemplo de contrato do login

```json
{
  "email": "usuario@exemplo.com",
  "senha": "123456"
}
```

### Exemplo de resposta

```json
{
  "access_token": "token.jwt.aqui",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "name": "Jeiel",
    "email": "usuario@exemplo.com",
    "role": "admin"
  }
}
```

## 8. Dependências de acesso

Crie dependências reutilizáveis em `core/dependencies.py`.

### Dependência base

- `get_current_user`: lê o token e carrega o usuário autenticado

### Dependências por role

- `require_admin`: permite apenas `admin`
- `require_professor_or_admin`: permite `professor` e `admin`

### Exemplo de regra

```python
def require_admin(current_user):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito ao admin")
```

## 9. Regras de autorização

Use estas decisões como padrão:

- `admin` pode criar, editar e excluir usuários
- `admin` pode alterar roles
- `professor` pode listar seus próprios dados e acessar rotas de trabalho
- `professor` não pode criar outro `admin`
- usuários inativos não podem autenticar

## 10. Exemplo de rotas protegidas

### Rota só para admin

- `POST /users`
- `DELETE /users/{id}`
- `PATCH /users/{id}/role`

### Rota para professor e admin

- `GET /classes`
- `GET /lessons`
- `POST /attendance`

## 11. Checklist de implementação

- [ ] criar o model `User`
- [ ] criar migration da tabela de usuários
- [ ] criar schemas de entrada e saída
- [ ] implementar hash de senha
- [ ] implementar login com JWT
- [ ] criar dependência `get_current_user`
- [ ] criar dependência `require_admin`
- [ ] criar dependência `require_professor_or_admin`
- [ ] proteger rotas com roles
- [ ] testar login com usuário ativo e inativo

## 12. Recomendação prática

Se quiser manter simples no início, siga esta ordem:

1. criar tabela de usuários
2. criar cadastro de usuário
3. criar login
4. criar `get_current_user`
5. adicionar regras de role
6. proteger rotas específicas

## 13. Exemplo de organização da lógica

### `models/user.py`

- representa a tabela

### `schemas/user.py`

- valida entrada e saída

### `services/auth_service.py`

- valida credenciais e gera token

### `api/routes/auth.py`

- expõe endpoints HTTP

### `core/dependencies.py`

- controla acesso por autenticação e role

## 14. Observação final

Esse modelo serve como base. Se o projeto crescer, vale separar ainda mais em:

- `auth/`
- `users/`
- `permissions/`

para deixar o código mais fácil de manter.