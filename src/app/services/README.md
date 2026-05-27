services/

Breve descrição:

Contém a lógica de negócio e orquestração entre repositórios e outros componentes.

O que colocar aqui:
- Funções/classe que implementam regras (autenticação, criação de chat, notificações).
- Orquestração de várias operações atômicas (pode usar transações do DB).

Boas práticas:
- Manter serviços testáveis (sem efeitos colaterais escondidos).
- Serviços chamam `repositories/` para persistência e `utils/` para helpers.
