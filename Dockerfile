# Versão completamente nova - 26/05/2025
FROM python:3.9-slim

# Criar diretório de trabalho
WORKDIR /app

# Atualizar pip e instalar dependências do sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Instalar todas as dependências Python necessárias
# Usando uma abordagem em camadas para evitar problemas de cache
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir httpx
RUN pip install --no-cache-dir openai==0.28.1
RUN pip install --no-cache-dir "litellm>=0.1.31"
RUN pip install --no-cache-dir uvicorn==0.23.2 pydantic==1.10.8 python-dotenv backoff

# Verificar se httpx está instalado (diagnóstico )
RUN pip list | grep httpx

# Copiar arquivos de configuração
COPY . /app

# Comando para iniciar o proxy
CMD python -m litellm --config config.yaml --port ${PORT:-7860} --host 0.0.0.0



