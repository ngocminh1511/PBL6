FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml /app/
COPY labor_rag /app/labor_rag
COPY src/backend /app/src/backend
RUN pip install --no-cache-dir -e '.[api,rag,ocr]'
COPY ontology /app/ontology
COPY data/processed /app/data/processed
COPY docs/reports/appendix_inventory/appendix_references.csv /app/docs/reports/appendix_inventory/
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "src.backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
