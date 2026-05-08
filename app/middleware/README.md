middleware/

Breve descrição:

Middlewares que atuam por requisição (autenticação, logging, CORS extras).

O que colocar aqui:
- Middlewares que inspecionam a `Request` e possivelmente modificam `Response`.
- Implementações leves que chamam `services/` ou verificam tokens.

Boas práticas:
- Evitar lógica de negócio extensa em middlewares; usar serviços quando necessário.
- Manter middlewares idempotentes e com bom tratamento de exceções.
