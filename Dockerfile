FROM python:3.12-slim

# uv: fast, reproducible dependency installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1

# Install dependencies first for better layer caching
COPY pyproject.toml requirements.txt ./
RUN uv pip install --system -r requirements.txt

# Copy the application code
COPY foreign_freelance_radar.py ./

# Results and Telegram session files live on mounted volumes
RUN mkdir -p output sessions

ENTRYPOINT ["python3", "foreign_freelance_radar.py"]
CMD ["--limit", "10", "--per-source", "10", "--min-score", "35", "--dry-run"]
