FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=environment_ca,target=/tmp/environment-ca.pem,required=false \
    if [ -f /tmp/environment-ca.pem ]; then export PIP_CERT=/tmp/environment-ca.pem SSL_CERT_FILE=/tmp/environment-ca.pem UV_SYSTEM_CERTS=true; fi; \
    pip install --no-cache-dir uv && uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN --mount=type=secret,id=environment_ca,target=/tmp/environment-ca.pem,required=false \
    if [ -f /tmp/environment-ca.pem ]; then export SSL_CERT_FILE=/tmp/environment-ca.pem UV_SYSTEM_CERTS=true; fi; \
    uv sync --frozen --no-dev && useradd --uid 10001 --create-home agentix && chmod -R a+rX /app
USER agentix
EXPOSE 8000
CMD ["sh", "-c", ".venv/bin/alembic upgrade head && exec .venv/bin/uvicorn agentix.main:app --host 0.0.0.0 --port 8000"]
