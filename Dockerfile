FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AI_DEMEMORY_ROOT=/memory

WORKDIR /app
COPY . /app
RUN python -m pip install --no-cache-dir .

VOLUME ["/memory"]
ENTRYPOINT ["ai-dememory"]
CMD ["mcp", "--stdio"]
