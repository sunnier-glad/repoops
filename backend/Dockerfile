FROM python:3.12-slim

WORKDIR /app
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/alembic.ini /app/backend/alembic.ini
COPY backend/app /app/backend/app

RUN pip install --no-cache-dir /app/backend

WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
