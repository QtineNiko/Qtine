FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system --gid 10001 qtine \
    && useradd --system --uid 10001 --gid qtine --home-dir /app qtine

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=qtine:qtine . .
RUN mkdir -p data/logs data/uploads plugins adapters \
    && chown -R qtine:qtine data plugins adapters

USER qtine
EXPOSE 4990

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4990/health', timeout=3)"

CMD ["gunicorn", "--worker-class", "gthread", "--workers", "1", "--threads", "8", "--timeout", "120", "--graceful-timeout", "30", "--keep-alive", "5", "--access-logfile", "-", "--error-logfile", "-", "--bind", "0.0.0.0:4990", "wsgi:application"]
