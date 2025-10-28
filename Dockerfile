FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml README.md ./

# Copy application code
COPY heare_auth ./heare_auth

# Install dependencies
RUN uv pip install --system -e .

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8080/health').raise_for_status()" || exit 1

# Run application
CMD ["uvicorn", "heare_auth.main:app", "--host", "0.0.0.0", "--port", "8080"]
