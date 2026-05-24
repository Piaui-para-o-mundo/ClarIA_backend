# 📘 Integração com o Microserviço de IA (ClarIA RAG)

Este documento descreve os novos endpoints da API de Inteligência Artificial após a reestruturação arquitetural para microsserviços. 

A antiga rota "faz-tudo" (`/ia/analisar`) foi **removida** para dar lugar a uma arquitetura modular, mais leve, escalável e 100% executada em memória (sem uso de I/O em disco).

---

## 🏗️ O Novo Fluxo de Integração (Importante)

Para evitar processar os mesmos PDFs pesados repetidas vezes, o novo fluxo funciona assim:
1. O backend principal envia os PDFs apenas **uma vez** para a rota de `/conformidade` (que deve rodar em background).
2. A IA extrai o texto e retorna o resultado da conformidade **junto com os textos extraídos**.
3. O backend principal salva esses textos (em cache ou no banco de dados).
4. Quando o usuário clica em "Gerar Resumo" ou "Gerar Despacho", o backend não envia mais os arquivos físicos (`.pdf`), apenas envia objetos JSON super leves com os textos, economizando largura de banda, processamento da IA e custos.

---

## 🚏 Endpoints Disponíveis

### 1. Health Check
- **Rota:** `GET /ia/health`
- **Descrição:** Verifica se o serviço de IA e o RAG estão operacionais.
- **Retorno de Sucesso:**
  ```json
  {
    "status": "ok",
    "message": "ClarIA service is operational"
  }
  ```

---

### 2. Verificar Conformidade Documental (Automático)
- **Rota:** `POST /ia/conformidade`
- **Content-Type:** `multipart/form-data`
- **Descrição:** Extrai o texto dos PDFs na memória RAM, classifica os documentos via IA e executa o checklist determinístico. Deve ser acionada automaticamente pelo backend assim que o processo for criado.
- **Payload (Form Data):**
  - `type_process` (String): O tipo do processo (ex: "Progressão Funcional").
  - `files` (List of Files): Os PDFs enviados pelo professor.
- **Retorno de Sucesso:**
  ```json
  {
    "status": "completo",
    "checklist": {
      "aprovado": true,
      "documentos_faltando": []
    },
    "documentos_identificados": [
      {
        "nome": "arquivo1.pdf",
        "tipo_documento": "requerimento",
        "confianca": 0.98
      }
    ],
    "textos_extraidos": [
      {
        "nome": "arquivo1.pdf",
        "texto": "Conteúdo extraído do pdf..."
      }
    ]
  }
  ```
> **🚨 AÇÃO OBRIGATÓRIA PARA O BACKEND:** O backend DEVE capturar o campo `textos_extraidos` retornado e associar ao processo no banco. Esses textos serão o combustível das próximas rotas.

---

### 3. Gerar Resumo Executivo (Sob demanda)
- **Rota:** `POST /ia/resumo`
- **Content-Type:** `application/json`
- **Descrição:** Acionada sob demanda (quando o avaliador pede). Utiliza os textos extraídos na Rota 2 para gerar um painel executivo inteligente sem precisar reprocessar PDFs.
- **Payload (JSON):**
  ```json
  {
    "tipo_processo": "Progressão Funcional",
    "textos_extraidos": [
      {
        "nome": "arquivo1.pdf",
        "texto": "Conteúdo extraído do pdf..."
      }
    ]
  }
  ```
- **Retorno de Sucesso:**
  ```json
  {
    "resumo": {
      "status": "success",
      "modulo": "resumo_executivo",
      "resultado": "O docente cumpriu todos os requisitos estipulados na resolução..."
    }
  }
  ```

---

### 4. Gerar Sugestão de Despacho (Sob demanda)
- **Rota:** `POST /ia/despacho`
- **Content-Type:** `application/json`
- **Descrição:** Acionada sob demanda. Usa o resultado do checklist e o texto do resumo gerado anteriormente para minutar o despacho oficial. Rota extremamente rápida por não processar grandes blocos de texto.
- **Payload (JSON):**
  ```json
  {
    "checklist_result": {
      "aprovado": true,
      "documentos_faltando": []
    },
    "resumo_texto": "O docente cumpriu todos os requisitos estipulados na resolução..."
  }
  ```
> *Nota:* O campo `resumo_texto` pode ser enviado vazio (`""`) caso o avaliador solicite o despacho sem ter gerado o resumo antes. A IA formulará o texto baseada nas pendências.
- **Retorno de Sucesso:**
  ```json
  {
    "despacho": "Em face da análise documental, DEFIRO o pedido formulado pelo docente..."
  }
  ```

---

### 5. Ingestão de Normas
- **Rota:** `POST /ia/ingest`
- **Content-Type:** `multipart/form-data`
- **Descrição:** Usada exclusivamente por administradores para adicionar novas resoluções ou manuais no banco de dados vetorial (ChromaDB) para consulta da IA (Contexto Jurídico).
- **Payload (Form Data):**
  - `file` (File): O arquivo PDF da norma ou manual.
- **Retorno de Sucesso:**
  ```json
  {
    "status": "success",
    "message": {
      "status": "success",
      "arquivo": "resolucao_03_2026.pdf",
      "paginas": 15,
      "chunks_indexados": 45
    }
  }
  ```
