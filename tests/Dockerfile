FROM python:3.10-slim

WORKDIR /app

# Build from repo root: docker compose build test (context ., dockerfile tests/Dockerfile)
COPY tests/requirements.txt tests/
COPY transformations/requirements.txt transformations/
RUN pip install --no-cache-dir -r tests/requirements.txt -r transformations/requirements.txt

CMD ["pytest", "tests/", "-v"]
