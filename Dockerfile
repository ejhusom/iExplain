FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY prompts ./prompts
COPY skills ./skills
COPY config ./config
COPY docs ./docs
COPY experiments ./experiments

RUN uv pip install --system .

EXPOSE 8000

CMD ["iexplain", "serve", "--config", "config/app.toml"]
