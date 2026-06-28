FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e . && pip install --no-cache-dir uvicorn

COPY src/ src/

EXPOSE 8000

CMD ["uvicorn", "jimini.main:app", "--host", "0.0.0.0", "--port", "8000"]
