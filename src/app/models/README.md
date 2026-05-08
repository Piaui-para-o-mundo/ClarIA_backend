models/

Breve descrição:

Modelos do domínio (tipicamente SQLAlchemy ORM) que representam tabelas e entidades.

Baseado em: `src/app/core/connection.py` (variável `Base`).

O que colocar aqui:
- Modelos que estendem `Base` (colunas, relacionamentos, métodos úteis).
- Migrations e scripts relacionados ao modelo não devem ficar aqui (usar `alembic/`).

Boas práticas:
- Separar validação (schemas) da persistência (models).
- Manter modelos focados em persistência; lógica complexa em `services/`.
