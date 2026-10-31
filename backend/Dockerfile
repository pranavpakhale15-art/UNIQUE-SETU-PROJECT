FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install --no-install-recommends -y libmagic1 && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 appuser
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY . .
RUN mkdir -p /app/private_uploads && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers ${WEB_CONCURRENCY:-2} --bind 0.0.0.0:${PORT:-8000}"]
