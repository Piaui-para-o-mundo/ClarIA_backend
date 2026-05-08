api/

Breve descrição:

Agrupa os routers da API e a composição dos endpoints.

Baseado em: `src/app/api/routes`.

O que colocar aqui:
- `routes/`: módulos por recurso (ex: `auth.py`, `users.py`, `chats.py`).
- `router.py`: função/objeto que agrega os routers e exporta para `main.py`.

Objetivo:
- Organização de contratos HTTP e separação por recursos.
