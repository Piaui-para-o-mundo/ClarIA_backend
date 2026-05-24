FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app/src

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements
COPY requirements.txt .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia código
COPY . .

# Expose porta
EXPOSE 8000

# Comando padrão
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]