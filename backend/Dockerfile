# backend/Dockerfile

FROM python:3.12.2-slim

# Create working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install system dependencies and uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

# Install Python packages with uv (much faster than pip)
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application code (this layer will be rebuilt when code changes)
COPY . /app

# Expose port 8000 within Docker
EXPOSE 8000

# By default, run uvicorn on 0.0.0.0:8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
