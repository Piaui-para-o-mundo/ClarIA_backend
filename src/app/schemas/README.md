schemas/

Breve descrição:

Schemas Pydantic usados para validação e serialização de requests/responses.

O que colocar aqui:
- `*.py` com classes `BaseModel` para `Create`, `Read`, `Update` as entradas/saídas.
- Conversões e validações específicas para payloads HTTP.

Boas práticas:
- Usar schemas separados para entrada (ex: `UserCreate`) e saída (ex: `UserRead`).
- Evitar lógica de negócios em schemas; focar validação e geração de erros.
