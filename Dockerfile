FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENV=production

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY my-project ./my-project
COPY scripts ./scripts

WORKDIR /app/my-project

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
