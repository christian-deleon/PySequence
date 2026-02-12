FROM python:3.11-slim AS base

WORKDIR /app

RUN pip install --no-cache-dir "poetry==2.3.2" \
    && poetry config virtualenvs.create false

# ---------------------------------------------------------------------------

FROM base AS deps

COPY pyproject.toml poetry.lock ./
COPY packages/pysequence-sdk/pyproject.toml packages/pysequence-sdk/
COPY packages/pysequence-api/pyproject.toml packages/pysequence-api/
COPY packages/pysequence-client/pyproject.toml packages/pysequence-client/
COPY packages/pysequence-bot/pyproject.toml packages/pysequence-bot/

# ---------------------------------------------------------------------------

FROM deps AS prod

# Install third-party deps first (cached until pyproject.toml changes)
RUN poetry install --without dev --no-directory
RUN playwright install --with-deps chromium

# Copy source and install local packages
COPY packages/pysequence-sdk/src/ packages/pysequence-sdk/src/
COPY packages/pysequence-api/src/ packages/pysequence-api/src/
COPY packages/pysequence-client/src/ packages/pysequence-client/src/
COPY packages/pysequence-bot/src/ packages/pysequence-bot/src/

RUN poetry install --without dev

EXPOSE 8720
ENTRYPOINT ["python", "-m", "pysequence_api"]

# ---------------------------------------------------------------------------

FROM deps AS bot

RUN poetry install --without dev --no-directory
RUN playwright install --with-deps chromium

COPY packages/pysequence-sdk/src/ packages/pysequence-sdk/src/
COPY packages/pysequence-api/src/ packages/pysequence-api/src/
COPY packages/pysequence-client/src/ packages/pysequence-client/src/
COPY packages/pysequence-bot/src/ packages/pysequence-bot/src/

RUN poetry install --without dev

ENTRYPOINT ["python", "-m", "pysequence_bot.telegram"]

# ---------------------------------------------------------------------------

FROM deps AS dev

RUN poetry install --no-directory
RUN playwright install --with-deps chromium

COPY packages/ packages/

RUN poetry install
