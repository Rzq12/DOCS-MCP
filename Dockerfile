FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    QDRANT_URL=http://qdrant:6333 \
    DOCUMENT_PARSER=docling \
    DOCUMENT_OCR=true

COPY pyproject.toml README.md document_server.py ./
COPY src ./src

RUN python -m pip install --no-cache-dir .

EXPOSE 8001

CMD ["python", "document_server.py"]