FROM python:3.9-slim

WORKDIR /app

# Instalar dependências
RUN pip install --no-cache-dir openai==0.28.1 litellm==0.11.0 uvicorn==0.23.2 pydantic==1.10.8 python-dotenv backoff

# Copiar arquivos
COPY . /app

# Comando para iniciar o proxy
CMD python -m litellm --config config.yaml --port ${PORT:-7860} --host 0.0.0.0
