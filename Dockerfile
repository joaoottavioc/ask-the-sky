FROM python:3.11-slim
WORKDIR /app

ENV POETRY_VERSION=1.8.3 \
    POETRY_PACKAGE_MODE=none \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# (sem POETRY_VIRTUALENVS_CREATE=false)

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Manifests primeiro
COPY pyproject.toml poetry.lock* ./

# Se o lock estiver desatualizado, re-geramos dentro do container
RUN poetry lock || true

# 👇 instala TUDO do projeto (grupo main + dev)
RUN poetry install --no-interaction --no-ansi --no-root --with dev

# Código
COPY ["src/", "src/"]
COPY ["app.py", "app.py"]
COPY assets/ assets/
COPY .streamlit/ .streamlit/
# COPY [".streamlit/", ".streamlit/"]  # se tiver

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000 8501
ENV ROLE=backend
ENV API_URL=http://localhost:8000

ENTRYPOINT ["/entrypoint.sh"]
