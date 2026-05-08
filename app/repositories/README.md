repositories/

Breve descrição:

Camada de acesso a dados — abstrai queries e operações de persistência.

O que colocar aqui:
- Funções ou classes para CRUD contra models/DB.
- Isolar detalhes do ORM (SQLAlchemy) para facilitar testes e trocas futuras.

Boas práticas:
- Retornar objetos de domínio ou DTOs simples; não expor sessões globais.
- Tratar transações e erros de persistência de forma consistente.
