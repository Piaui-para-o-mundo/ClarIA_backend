api/routes/

Breve descrição:

Cada arquivo define um `APIRouter` para um recurso específico.

Exemplos esperados:
- `auth.py`: endpoints de login/logout, refresh token.
- `users.py`: CRUD de usuários.
- `chats.py`: endpoints de criação e listagem de chats.

Boas práticas:
- Manter handlers pequenos; delegar lógica para `services/`.
- Validar entrada com `schemas/`.
