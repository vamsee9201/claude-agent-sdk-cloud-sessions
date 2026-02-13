FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

RUN useradd -m -s /bin/bash appuser && chown -R appuser:appuser /app
RUN mkdir -p /home/appuser/.claude && chown appuser:appuser /home/appuser/.claude

USER appuser

ENV PORT=8080

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
