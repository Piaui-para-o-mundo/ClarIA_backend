utils/

Breve descrição:

Helpers e utilitários reutilizáveis que não pertencem a uma camada específica.

O que colocar aqui:
- Funções puras de formatação, validação, conversão e helpers de uso geral.
- Peças reutilizáveis chamadas por `services/`, `repositories/` ou `api/`.

Boas práticas:
- Documentar contratos de função; preferir funções puras (sem efeitos colaterais).
- Não colocar lógica de negócio complexa aqui.
