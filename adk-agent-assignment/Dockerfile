# syntax=docker/dockerfile:1
# Serves all five agents with the ADK API server (or the dev UI via ADK_COMMAND=web).
# Includes git + Gemini CLI for Agent B. No secrets are baked into the image.

# ---- Stage 1: Gemini CLI (Node) ----------------------------------------------------
FROM node:22-bookworm-slim AS gemini-cli
ARG GEMINI_CLI_VERSION=0.66.0
RUN npm install -g "@google/gemini-cli@${GEMINI_CLI_VERSION}" && npm cache clean --force

# ---- Stage 2: Python runtime ---------------------------------------------------------
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    PORT=8080 \
    LOCAL_STATE_DIR=/tmp/adk-state \
    ADK_COMMAND=api_server

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=gemini-cli /usr/local/bin/node /usr/local/bin/node
COPY --from=gemini-cli /usr/local/lib/node_modules/@google/gemini-cli \
     /usr/local/lib/node_modules/@google/gemini-cli
RUN ln -s /usr/local/lib/node_modules/@google/gemini-cli/bundle/gemini.js /usr/local/bin/gemini

WORKDIR /app
# Dependency layer: install runtime + production extras from pyproject (cached until it
# changes). The project itself runs from /app via PYTHONPATH.
COPY pyproject.toml ./
RUN python -c "import tomllib; d = tomllib.load(open('pyproject.toml','rb'))['project']; \
print('\n'.join(d['dependencies'] + d['optional-dependencies']['production']))" \
    > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt

COPY adk_shared ./adk_shared
COPY agents ./agents
COPY configs ./configs
COPY data ./data

RUN useradd --create-home --uid 10001 app \
    && mkdir -p "$LOCAL_STATE_DIR" && chown app "$LOCAL_STATE_DIR"
USER app

EXPOSE 8080
CMD ["sh", "-c", "exec adk \"$ADK_COMMAND\" --host 0.0.0.0 --port \"$PORT\" /app/agents"]
