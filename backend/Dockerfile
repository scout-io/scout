# backend/Dockerfile

FROM python:3.12.2-slim

# Create working directory
WORKDIR /app

# The PROMETHEUS_MULTIPROC_DIR is no longer needed for in-memory metrics.

# Copy requirements and install
COPY requirements.txt .
# Install curl for health-check and other diagnostic uses
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

# Copy your FastAPI code into the container
COPY . /app

# Expose port 8000 within Docker
EXPOSE 8000

# By default, run uvicorn on 0.0.0.0:8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
