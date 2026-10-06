# syntax=docker/dockerfile:1
# Multi-stage, non-root image (see .ai/stacks/docker/README.md).
# FastAPI is ASGI: served by uvicorn behind NGINX (uWSGI is for WSGI apps, see ADR 0002).

FROM python:3.12-slim AS build
WORKDIR /build
COPY requirements.txt pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
 && pip install --no-cache-dir --prefix=/install --no-deps .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /install /usr/local
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live').status == 200 else 1)"]
CMD ["uvicorn", "fastapi_demo.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
