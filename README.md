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
