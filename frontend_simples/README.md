# ClarIA - Frontend Simples

Este é um frontend estático construído com HTML, CSS e JavaScript puro (Vanilla JS) para consumir a API do ClarIA.

## Como Executar

### 1. Servir os arquivos
Como os navegadores restringem requisições de arquivos locais (`file://`), você deve servir esta pasta usando um servidor HTTP simples.

Se você tem **Python** instalado:
```bash
# Entre na pasta do frontend
cd frontend_simples
# Rode o servidor na porta 8001 (permitida no CORS do backend)
python3 -m http.server 8001
```

Se você tem **Node.js** instalado:
```bash
# Instale o serve globalmente (se não tiver)
npm install -g serve
# Rode o servidor
serve -l 8001 .
```

### 2. Acessar
Abra no seu navegador: [http://localhost:8001](http://localhost:8001)

## Funcionalidades
- **Autenticação:** Registro e Login de usuários (Professor/Avaliador).
- **Dashboard:** Visualização de processos de acordo com o papel do usuário.
- **Criação:** Professores podem iniciar novos requerimentos.
- **Upload:** Envio de documentos PDF vinculados a tipos específicos.
- **IA:** Integração com os módulos de Resumo, Conformidade e Despacho da IA.

## Configuração do Backend
Por padrão, este frontend tenta conectar-se ao backend em `http://localhost:8000/api/v1`. Certifique-se de que o backend está rodando e que a origem `http://localhost:8001` está permitida no CORS (veja `src/main.py`).
