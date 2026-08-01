FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AI_DEMEMORY_ROOT=/memory

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY ai_dememory_tool ./ai_dememory_tool
COPY scripts ./scripts
COPY mcp ./mcp
RUN python -m pip install --no-cache-dir .

VOLUME ["/memory"]
ENTRYPOINT ["ai-dememory"]
CMD ["mcp", "--stdio"]
