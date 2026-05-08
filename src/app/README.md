# app/

Breve descrição do propósito de cada diretório dentro de `app/`:

- `core/`: Inicialização e configuração do projeto (env, DB, segurança, dependências, exceções).
- `api/`: Roteamento e agrupamento de endpoints (cada recurso em `routes/`).
- `models/`: Modelos do domínio (ORM).
- `schemas/`: Schemas Pydantic para entrada/saída.
- `services/`: Regras de negócio e orquestração entre repositórios.
- `repositories/`: Acesso a dados e operações de persistência.
- `middleware/`: Middlewares aplicáveis à aplicação (auth, logging, etc.).
- `utils/`: Helpers e utilitários reutilizáveis.
- `tests/`: Casos de teste unitários e de integração.
- `alembic/`: Migrações do banco de dados.

Cada subdiretório contém um `__init__.py` como ponto de entrada do pacote e deve ser preenchido com módulos reais conforme o desenvolvimento avança.
