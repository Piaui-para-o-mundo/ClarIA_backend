# JurisAI Backend

Backend em FastAPI com PostgreSQL usando Docker Compose.

## Pré-requisitos

- Docker
- Docker Compose

## Como rodar o projeto

1. Na raiz do projeto, suba os containers com build:

```bash
docker-compose up --build
```

2. A API ficará disponível em:

- http://localhost:8000
- Documentação Swagger: http://localhost:8000/docs

3. O banco PostgreSQL ficará disponível em:

- Host: localhost
- Porta: 5432
- Database: appdb
- User: postgres
- Password: postgres

## Comandos úteis

- Subir em background:

```bash
docker-compose up -d --build
```

- Ver logs da API:

```bash
docker-compose logs -f api
```

- Parar containers:

```bash
docker-compose down
```

- Parar e remover volume do banco (apaga dados):

```bash
docker-compose down -v
```

## Estrutura principal

- `app/main.py`: entrada da API FastAPI
- `Dockerfile`: build da imagem da aplicação
- `docker-compose.yaml`: orquestra API + PostgreSQL
- `requirements.txt`: dependências Python


## Arquitetura
Modelo de estrutura sugerida para a aplicação:
- Exemplo de arquitetura
```
app/
│
├── main.py
│
├── core/                     # Configurações globais
│   ├── config.py
│   ├── security.py
│   ├── database.py
│   ├── dependencies.py
│   ├── exceptions.py
│   └── logging.py
│
├── api/                      # Camada HTTP
│   ├── v1/
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   └── chats.py
│   │   │
│   │   └── api.py
│   │
│   └── middleware/
│       ├── auth.py
│       └── tenant.py
│
├── domain/                   # Regra de negócio PURA
│   ├── entities/
│   │   ├── user.py
│   │   ├── chat.py
│   │   └── organization.py
│   │
│   ├── repositories/
│   │   ├── user_repository.py
│   │   └── chat_repository.py
│   │
│   └── services/
│       └── auth_service.py
│
├── application/              # Casos de uso
│   ├── use_cases/
│   │   ├── auth/
│   │   │   ├── login.py
│   │   │   └── register.py
│   │   │
│   │   ├── users/
│   │   │   ├── create_user.py
│   │   │   └── list_users.py
│   │   │
│   │   └── chats/
│   │       ├── send_message.py
│   │       └── finish_chat.py
│   │
│   ├── dto/
│   │   ├── user_dto.py
│   │   └── chat_dto.py
│   │
│   └── interfaces/
│       └── unit_of_work.py
│
├── infrastructure/           # Banco, APIs externas, etc
│   ├── database/
│   │   ├── models/
│   │   │   ├── user_model.py
│   │   │   └── chat_model.py
│   │   │
│   │   ├── repositories/
│   │   │   ├── sql_user_repository.py
│   │   │   └── sql_chat_repository.py
│   │   │
│   │   ├── session.py
│   │   └── base.py
│   │
│   ├── external/
│   │   ├── whatsapp/
│   │   ├── email/
│   │   ├── push/
│   │   └── openai/
│   │
│   └── queue/
│       └── redis.py
│
├── shared/
│   ├── utils/
│   ├── constants/
│   └── schemas/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
└── migrations/
```
