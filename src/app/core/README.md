core/

Breve descrição:

Contém a configuração e inicialização da aplicação.

Baseado em: `src/app/core/config.py`, `src/app/core/connection.py`.

O que colocar aqui:
- `config.py`: carregamento de variáveis de ambiente (preferir `pydantic.BaseSettings`).
- `connection.py`: engine do SQLAlchemy, `SessionLocal` e `Base` para modelos.
- `dependencies.py` (opcional): factories/dependencies para endpoints (ex: `get_db`).
- `security.py`: funções de hashing, geração/validação de tokens.
- `exceptions.py`: exceções da aplicação e mapeamento para respostas HTTP.

Objetivo:
- Centralizar infraestrutura e dependências compartilhadas.
